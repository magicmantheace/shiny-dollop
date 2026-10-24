import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { HistoryView } from '../views/HistoryView';
import { installMock, ok } from './mockStorageAnalyzer';

describe('HistoryView', () => {
  it('lists past scans with state badges and selects one on click', async () => {
    installMock();
    const onSelectScan = vi.fn();
    render(<HistoryView onSelectScan={onSelectScan} onError={vi.fn()} />);

    const item = await screen.findByRole('button', { name: /view results for scan of/i });
    expect(item).toHaveTextContent('complete');
    expect(item).toHaveTextContent('C:\\data');
    expect(item).toHaveTextContent('42 files');

    fireEvent.click(item);
    expect(onSelectScan).toHaveBeenCalledWith(1);
  });

  it('sorts newest first', async () => {
    installMock({
      scan: {
        start: vi.fn(async () => ok({ scanId: 'x' })),
        cancel: vi.fn(async () => ok({ ok: true })),
        status: vi.fn(async () => ok({ state: 'running', files: 0, dirs: 0, bytes: 0, startedAt: 'x', finishedAt: null })),
        list: vi.fn(async () =>
          ok({
            scans: [
              {
                id: 1,
                rootPath: 'C:\\old',
                state: 'complete',
                files: 1,
                bytes: 1,
                startedAt: '2026-10-20T10:00:00.000Z',
                finishedAt: '2026-10-20T10:01:00.000Z',
              },
              {
                id: 2,
                rootPath: 'C:\\new',
                state: 'failed',
                files: 2,
                bytes: 2,
                startedAt: '2026-10-23T10:00:00.000Z',
                finishedAt: '2026-10-23T10:01:00.000Z',
              },
            ],
          }),
        ),
      },
    } as never);
    render(<HistoryView onSelectScan={vi.fn()} onError={vi.fn()} />);

    const items = await screen.findAllByRole('button', { name: /view results for scan of/i });
    expect(items[0]).toHaveTextContent('C:\\new');
    expect(items[0]).toHaveTextContent('failed');
    expect(items[1]).toHaveTextContent('C:\\old');
  });

  it('shows an empty state when there are no scans', async () => {
    installMock({
      scan: {
        start: vi.fn(async () => ok({ scanId: 'x' })),
        cancel: vi.fn(async () => ok({ ok: true })),
        status: vi.fn(async () => ok({ state: 'running', files: 0, dirs: 0, bytes: 0, startedAt: 'x', finishedAt: null })),
        list: vi.fn(async () => ok({ scans: [] })),
      },
    } as never);
    render(<HistoryView onSelectScan={vi.fn()} onError={vi.fn()} />);

    expect(await screen.findByText(/no scans yet/i)).toBeInTheDocument();
  });
});
