import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Editor } from './Editor';
import { invoiceManifest, makeDoc, mockDtf, unmockDtf } from '../test-utils';

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
