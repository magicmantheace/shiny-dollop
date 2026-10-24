import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Gallery } from './Gallery';
import { mockDtf, templateSummaries, unmockDtf } from '../test-utils';

afterEach(() => {
  unmockDtf();
  vi.restoreAllMocks();
});

describe('Gallery', () => {
  it('renders three templates from the mocked backend with field counts', async () => {
    mockDtf();
    render(<Gallery onOpenDocument={() => {}} />);

    for (const t of templateSummaries) {
      expect(await screen.findByText(t.name)).toBeInTheDocument();
      expect(screen.getByText(t.description)).toBeInTheDocument();
      expect(screen.getByText(t.version)).toBeInTheDocument();
    }
    // Field counts appear in each card's metadata.
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    // One "New document" button per card.
    expect(screen.getAllByRole('button', { name: /New document from/ })).toHaveLength(3);
  });

  it('creates a document and opens it when "New document" is clicked', async () => {
    const dtf = mockDtf();
    dtf.documents.create.mockResolvedValue({
      id: 'doc-99',
      templateId: 'weekly-planner',
      data: {},
      tokens: {},
      version: 1,
      updatedAt: '2026-10-23T15:00:00.000Z',
    });
    const onOpenDocument = vi.fn();
    const user = userEvent.setup();
    render(<Gallery onOpenDocument={onOpenDocument} />);

    const btn = await screen.findByRole('button', {
      name: 'New document from Weekly Planner',
    });
    await user.click(btn);

    await waitFor(() => {
      expect(dtf.documents.create).toHaveBeenCalledWith({
        templateId: 'weekly-planner',
      });
    });
    expect(onOpenDocument).toHaveBeenCalledWith('doc-99');
  });

  it('shows a load error with retry when the backend fails', async () => {
    mockDtf({ templates: { list: vi.fn().mockRejectedValue(new Error('IPC_TIMEOUT')) } });
    const user = userEvent.setup();
    render(<Gallery onOpenDocument={() => {}} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('IPC_TIMEOUT');
    const retry = screen.getByRole('button', { name: 'Retry' });
    await user.click(retry);
    expect(await screen.findByRole('alert')).toHaveTextContent('IPC_TIMEOUT');
  });

  it('opens the import dialog from the Import template button', async () => {
    mockDtf();
    const user = userEvent.setup();
    render(<Gallery onOpenDocument={() => {}} />);

    await user.click(await screen.findByRole('button', { name: 'Import template' }));
    expect(await screen.findByRole('dialog', { name: 'Import template' })).toBeInTheDocument();
  });
});
