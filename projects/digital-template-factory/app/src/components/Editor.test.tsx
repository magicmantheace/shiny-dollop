import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Editor } from './Editor';
import { fixtureTokens, invoiceManifest, makeDoc, mockDtf, unmockDtf } from '../test-utils';
import type { DocumentRecord } from '../../shared/types';

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (err: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (err: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function docWithClientName(clientName: string): DocumentRecord {
  return makeDoc({ data: { ...makeDoc().data, clientName } });
}

afterEach(() => {
  unmockDtf();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('Editor', () => {
  it('loads the document and manifest, and renders fields plus preview', async () => {
    const dtf = mockDtf();
    dtf.documents.get.mockResolvedValue(makeDoc());
    render(<Editor docId="doc-1" onBack={() => {}} />);

    expect(await screen.findByRole('heading', { name: /Simple Invoice/ })).toBeInTheDocument();
    expect(screen.getByLabelText(/Client name/)).toHaveValue('Acme Corp');
    // Live preview iframe fed by the local pure renderer.
    expect(
      screen.getByTitle('Preview of Simple Invoice'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Approximate preview/)).toBeInTheDocument();
  });

  it('sends field edits to the backend', async () => {
    const dtf = mockDtf();
    dtf.documents.get.mockResolvedValue(makeDoc());
    const user = userEvent.setup();
    render(<Editor docId="doc-1" onBack={() => {}} />);

    const clientName = await screen.findByLabelText(/Client name/);
    await user.clear(clientName);
    await user.type(clientName, 'Globex');

    await waitFor(() => {
      expect(dtf.documents.updateField).toHaveBeenCalledWith({
        id: 'doc-1',
        key: 'clientName',
        value: 'Globex',
      });
    });
  });

  it('toggles the export panel', async () => {
    const dtf = mockDtf();
    dtf.documents.get.mockResolvedValue(makeDoc());
    dtf.templates.get.mockResolvedValue(invoiceManifest);
    const user = userEvent.setup();
    render(<Editor docId="doc-1" onBack={() => {}} />);

    await screen.findByRole('heading', { name: /Simple Invoice/ });
    expect(screen.queryByRole('heading', { name: 'Export' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Export' }));
    expect(await screen.findByRole('heading', { name: 'Export' })).toBeInTheDocument();
  });

  it('preserves newer local edits when an earlier save response arrives (regression)', async () => {
    const dtf = mockDtf();
    dtf.documents.get.mockResolvedValue(makeDoc());
    const saves: Array<{ value: unknown; d: Deferred<DocumentRecord> }> = [];
    dtf.documents.updateField.mockImplementation(
      (input: { id: string; key: string; value: unknown }) => {
        const d = deferred<DocumentRecord>();
        saves.push({ value: input.value, d });
        return d.promise;
      },
    );
    const user = userEvent.setup();
    render(<Editor docId="doc-1" onBack={() => {}} />);

    const clientName = await screen.findByLabelText(/Client name/);
    // Type `a` then `ab`-style sequence: clear (save "") then type "a"
    // (save "a") while BOTH saves are still in flight.
    await user.clear(clientName);
    await user.type(clientName, 'a');
    expect(saves.map((s) => s.value)).toEqual(['', 'a']);
    expect(clientName).toHaveValue('a');

    // The EARLIER save's response arrives now, carrying the "" snapshot.
    // It must not snap the field back to "" — the "a" edit is newer.
    saves[0]!.d.resolve(docWithClientName(''));
    await waitFor(() => {
      expect(dtf.documents.updateField).toHaveBeenCalledTimes(2);
    });
    // Flush the resolved promise through React before asserting.
    await new Promise((r) => setTimeout(r, 0));
    expect(clientName).toHaveValue('a');

    // The newer save's response then acknowledges "a" — value stays.
    saves[1]!.d.resolve(docWithClientName('a'));
    await new Promise((r) => setTimeout(r, 0));
    expect(clientName).toHaveValue('a');
  });

  it('preserves pending field edits when a token save response arrives (regression)', async () => {
    const dtf = mockDtf();
    dtf.documents.get.mockResolvedValue(makeDoc());
    const fieldSaves: Array<Deferred<DocumentRecord>> = [];
    dtf.documents.updateField.mockImplementation(() => {
      const d = deferred<DocumentRecord>();
      fieldSaves.push(d);
      return d.promise;
    });
    const tokenSaves: Array<Deferred<DocumentRecord>> = [];
    dtf.documents.updateTokens.mockImplementation(() => {
      const d = deferred<DocumentRecord>();
      tokenSaves.push(d);
      return d.promise;
    });
    const user = userEvent.setup();
    render(<Editor docId="doc-1" onBack={() => {}} />);

    const clientName = await screen.findByLabelText(/Client name/);
    await user.clear(clientName);
    await user.type(clientName, 'a');
    expect(fieldSaves).toHaveLength(2);
    expect(clientName).toHaveValue('a');

    // Change the Background hex token: only the complete valid hex value
    // is forwarded, so exactly one token save starts, still in flight.
    const bg = screen.getByLabelText('Background');
    await user.clear(bg);
    await user.type(bg, '#112233');
    expect(tokenSaves).toHaveLength(1);

    // The token response carries a data snapshot that PREDATES the field
    // edits (clientName is still the loaded "Acme Corp" there). It must
    // acknowledge the token without reverting the pending field edit.
    tokenSaves[0]!.resolve(
      makeDoc({ tokens: { ...fixtureTokens, bg: '#112233' } }),
    );
    await new Promise((r) => setTimeout(r, 0));
    expect(clientName).toHaveValue('a');

    // Drain the field saves so no promise is left dangling.
    fieldSaves[0]!.resolve(docWithClientName(''));
    fieldSaves[1]!.resolve(docWithClientName('a'));
    await new Promise((r) => setTimeout(r, 0));
    expect(clientName).toHaveValue('a');
  });

  it('shows a load error when the document cannot be fetched', async () => {
    mockDtf({ documents: { get: vi.fn().mockRejectedValue(new Error('DOC_NOT_FOUND')) } });
    render(<Editor docId="missing" onBack={() => {}} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('DOC_NOT_FOUND');
  });

  it('goes back when the Back button is clicked', async () => {
    const dtf = mockDtf();
    dtf.documents.get.mockResolvedValue(makeDoc());
    const onBack = vi.fn();
    const user = userEvent.setup();
    render(<Editor docId="doc-1" onBack={onBack} />);

    // Wait for the async load: the loading view's button is replaced when
    // the document arrives, so grab a fresh reference afterwards.
    await screen.findByLabelText(/Client name/);
    await user.click(screen.getByRole('button', { name: '← Back' }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
