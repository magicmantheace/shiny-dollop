import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ScanView } from '../views/ScanView';
import { defaultStatus, installMock, ok } from './mockStorageAnalyzer';

describe('ScanView', () => {
  it('renders live progress from scan.progress events', async () => {
    const { captures } = installMock();
    render(
      <ScanView scanId={1} onViewResults={vi.fn()} onNewScan={vi.fn()} onError={vi.fn()} />,
    );

    // Initial status load.
    expect(await screen.findByText(/scanning/i)).toBeInTheDocument();

    captures.progress[0]?.({
      scanId: 1,
      files: 1234,
      dirs: 56,
      bytes: 7 * 1024 * 1024,
      currentPath: 'C:\\data\\video.mp4',
    });

    await waitFor(() => {
      expect(screen.getByText('1,234')).toBeInTheDocument();
      expect(screen.getByText('56')).toBeInTheDocument();
      expect(screen.getByText('7 MB')).toBeInTheDocument();
      expect(screen.getByTitle('C:\\data\\video.mp4')).toHaveTextContent('C:\\data\\video.mp4');
    });
  });

  it('ignores progress events for other scans', async () => {
    const { captures } = installMock();
    render(
      <ScanView scanId={1} onViewResults={vi.fn()} onNewScan={vi.fn()} onError={vi.fn()} />,
    );

    await screen.findByText(/scanning/i);
    captures.progress[0]?.({
      scanId: 2,
      files: 999,
      dirs: 99,
      bytes: 999,
      currentPath: 'C:\\other',
    });

    await waitFor(() => {
      expect(screen.queryByText('999')).not.toBeInTheDocument();
    });
  });

  it('cancels the scan when the Cancel button is clicked', async () => {
    const status = vi
      .fn()
      .mockResolvedValueOnce(ok({ ...defaultStatus, state: 'running' }))
      .mockResolvedValue(
        ok({ ...defaultStatus, state: 'cancelled', finishedAt: '2026-10-23T10:01:00.000Z' }),
      );
    const { api } = installMock({
      scan: {
        start: vi.fn(async () => ok({ scanId: 1 })),
        cancel: vi.fn(async () => ok({ ok: true })),
        status,
        list: vi.fn(async () => ok({ scans: [] })),
      },
    } as never);
    render(
      <ScanView scanId={1} onViewResults={vi.fn()} onNewScan={vi.fn()} onError={vi.fn()} />,
    );

    await screen.findByText(/scanning/i);
    fireEvent.click(screen.getByRole('button', { name: /cancel scan/i }));

    await waitFor(() => {
      expect(api.scan.cancel).toHaveBeenCalledWith({ scanId: 1 });
      expect(screen.getByText(/scan cancelled/i)).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /cancel scan/i })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /view results/i })).toBeInTheDocument();
    });
  });

  it('shows the final state when a scan.finished event arrives', async () => {
    const status = vi
      .fn()
      .mockResolvedValueOnce(ok({ ...defaultStatus, state: 'running' }))
      .mockResolvedValue(
        ok({ ...defaultStatus, state: 'failed', error: 'boom', finishedAt: '2026-10-23T10:01:00.000Z' }),
      );
    const { api, captures } = installMock({
      scan: {
        start: vi.fn(async () => ok({ scanId: 1 })),
        cancel: vi.fn(async () => ok({ ok: true })),
        status,
        list: vi.fn(async () => ok({ scans: [] })),
      },
    } as never);
    const onError = vi.fn();
    render(<ScanView scanId={1} onViewResults={vi.fn()} onNewScan={vi.fn()} onError={onError} />);

    await screen.findByText(/scanning/i);
    captures.finished[0]?.({ scanId: 1, state: 'failed' });

    await waitFor(() => {
      expect(api.scan.status).toHaveBeenCalled();
      expect(screen.getByText(/scan failed/i)).toBeInTheDocument();
      expect(screen.getByText(/error: boom/i)).toBeInTheDocument();
    });
    expect(onError).not.toHaveBeenCalled();
  });

  it('shows the backend protected-path warning banner', async () => {
    installMock();
    render(
      <ScanView
        scanId={1}
        startWarning="protected-path"
        onViewResults={vi.fn()}
        onNewScan={vi.fn()}
        onError={vi.fn()}
      />,
    );

    await screen.findByText(/scanning/i);
    expect(screen.getByRole('alert')).toHaveTextContent(/protected path/i);
  });

  it('navigates to results when View results is clicked', async () => {
    installMock({
      scan: {
        start: vi.fn(async () => ok({ scanId: 1 })),
        cancel: vi.fn(async () => ok({ ok: true })),
        status: vi.fn(async () => ok({ ...defaultStatus, state: 'complete', finishedAt: '2026-10-23T10:01:00.000Z' })),
        list: vi.fn(async () => ok({ scans: [] })),
      },
    } as never);
    const onViewResults = vi.fn();
    render(
      <ScanView scanId={1} onViewResults={onViewResults} onNewScan={vi.fn()} onError={vi.fn()} />,
    );

    fireEvent.click(await screen.findByRole('button', { name: /view results/i }));
    expect(onViewResults).toHaveBeenCalledWith(1);
  });
});
