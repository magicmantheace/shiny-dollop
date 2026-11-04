import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DocumentsList } from './DocumentsList';
import { mockDtf, unmockDtf } from '../test-utils';
import { upsertRecentDoc } from '../recentDocs';

afterEach(() => {
  unmockDtf();
  vi.restoreAllMocks();
  localStorage.clear();
});

function seed() {
  upsertRecentDoc({
    id: 'doc-1',
    templateId: 'simple-invoice',
    templateName: 'Simple Invoice',
    updatedAt: '2026-10-23T15:00:00.000Z',
  });
  upsertRecentDoc({
    id: 'doc-2',
    templateId: 'checklist',
    templateName: 'Checklist',
    updatedAt: '2026-10-22T09:30:00.000Z',
  });
}

describe('DocumentsList', () => {
  it('lists recent documents with template name and updated date', () => {
    mockDtf();
    seed();
    render(<DocumentsList onOpenDocument={() => {}} />);

    expect(screen.getByRole('button', { name: 'Simple Invoice' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Checklist' })).toBeInTheDocument();
    // Updated dates render (locale-dependent, so match loosely).
    expect(screen.getAllByText(/Updated /)).toHaveLength(2);
  });

  it('opens the document when its name is clicked', async () => {
    mockDtf();
    seed();
    const onOpenDocument = vi.fn();
    const user = userEvent.setup();
    render(<DocumentsList onOpenDocument={onOpenDocument} />);

    await user.click(screen.getByRole('button', { name: 'Simple Invoice' }));
    expect(onOpenDocument).toHaveBeenCalledWith('doc-1');
  });

  it('deletes with inline confirmation and calls the backend', async () => {
    const dtf = mockDtf();
    seed();
    const user = userEvent.setup();
    render(<DocumentsList onOpenDocument={() => {}} />);

    await user.click(
      screen.getByRole('button', { name: 'Delete document Simple Invoice' }),
    );
    // Inline confirmation appears instead of a native dialog.
    await user.click(screen.getByRole('button', { name: 'Confirm delete' }));

    await waitFor(() => {
      expect(dtf.documents.delete).toHaveBeenCalledWith({ id: 'doc-1' });
    });
    expect(screen.queryByRole('button', { name: 'Simple Invoice' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Checklist' })).toBeInTheDocument();
  });

  it('shows a backend error when deletion fails', async () => {
    mockDtf({
      documents: { delete: vi.fn().mockRejectedValue(new Error('DOC_LOCKED')) },
    });
    seed();
    const user = userEvent.setup();
    render(<DocumentsList onOpenDocument={() => {}} />);

    await user.click(
      screen.getByRole('button', { name: 'Delete document Simple Invoice' }),
    );
    await user.click(screen.getByRole('button', { name: 'Confirm delete' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('DOC_LOCKED');
    // Entry stays put on failure.
    expect(screen.getByRole('button', { name: 'Simple Invoice' })).toBeInTheDocument();
  });

  it('shows documents that exist only in the backend (evicted from the recent index)', async () => {
    mockDtf({
      documents: {
        list: vi.fn().mockResolvedValue([
          {
            id: 'doc-backend-only',
            templateId: 'weekly-planner',
            templateName: 'Weekly Planner',
            updatedAt: '2026-10-20T09:30:00.000Z',
          },
        ]),
      },
    });
    seed();
    render(<DocumentsList onOpenDocument={() => {}} />);

    expect(
      await screen.findByRole('button', { name: 'Weekly Planner' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Simple Invoice' })).toBeInTheDocument();
  });

  it('shows an empty state when there are no recent documents', () => {
    mockDtf();
    render(<DocumentsList onOpenDocument={() => {}} />);
    expect(screen.getByText(/No documents yet/)).toBeInTheDocument();
  });
});
