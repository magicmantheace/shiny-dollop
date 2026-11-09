import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ResultsView } from '../views/ResultsView';
import { defaultGroups, defaultScans, installMock, ok } from './mockStorageAnalyzer';

const baseScans = defaultScans;

describe('ResultsView', () => {
  it('renders folder sizes, largest files and type summary', async () => {
    installMock();
    render(<ResultsView scanId={1} onError={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole('table', { name: /folder sizes/i })).toBeInTheDocument();
    });
    expect(screen.getByText('C:\\data\\big.iso')).toBeInTheDocument();
    // '900 B' appears in both the largest-files and file-types tables.
    expect(screen.getAllByText('900 B')).toHaveLength(2);
    expect(screen.getByText('.iso')).toBeInTheDocument();
    // Totals line.
    expect(screen.getByText('files,', { exact: false })).toBeInTheDocument();
  });

  it('shows a stale label when a newer scan of the same root exists', async () => {
    installMock({
      scan: {
        start: vi.fn(async () => ok({ scanId: 'x' })),
        cancel: vi.fn(async () => ok({ ok: true })),
        status: vi.fn(async () => ok({ state: 'complete', files: 1, dirs: 1, bytes: 1, startedAt: 'x', finishedAt: 'y' })),
        list: vi.fn(async () =>
          ok({
            scans: [
              ...baseScans,
              {
                id: 2,
                rootPath: 'C:\\data',
                state: 'complete',
                files: 50,
                bytes: 2048,
                startedAt: '2026-10-24T10:00:00.000Z',
                finishedAt: '2026-10-24T10:05:00.000Z',
              },
            ],
          }),
        ),
      },
    } as never);
    render(<ResultsView scanId={1} onError={vi.fn()} />);

    expect(await screen.findByText(/stale: this scan did not complete, or a newer scan/i)).toBeInTheDocument();
  });

  it('shows a stale label when the scan did not complete', async () => {
    installMock({
      scan: {
        start: vi.fn(async () => ok({ scanId: 'x' })),
        cancel: vi.fn(async () => ok({ ok: true })),
        status: vi.fn(async () => ok({ state: 'cancelled', files: 1, dirs: 1, bytes: 1, startedAt: 'x', finishedAt: 'y' })),
        list: vi.fn(async () =>
          ok({
            scans: [{ ...baseScans[0]!, state: 'cancelled', finishedAt: '2026-10-23T10:01:00.000Z' }],
          }),
        ),
      },
    } as never);
    render(<ResultsView scanId={1} onError={vi.fn()} />);

    expect(await screen.findByText(/stale:/i)).toBeInTheDocument();
  });

  it('shows no stale label for a complete scan with no newer scan', async () => {
    installMock();
    render(<ResultsView scanId={1} onError={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole('table', { name: /folder sizes/i })).toBeInTheDocument();
    });
    expect(screen.queryByText(/stale:/i)).not.toBeInTheDocument();
  });

  it('displays duplicate groups with SHA-256, files and potential savings', async () => {
    installMock();
    render(<ResultsView scanId={1} onError={vi.fn()} />);

    const group = await screen.findByRole('group', { name: /duplicate group/i });
    expect(group).toHaveTextContent(defaultGroups[0]!.sha256);
    expect(group).toHaveTextContent('C:\\data\\a.txt');
    expect(group).toHaveTextContent('C:\\data\\b.txt');
    // savings = 500 bytes * (2 - 1) = 500 bytes.
    expect(group).toHaveTextContent('Potential savings:');
    expect(group).toHaveTextContent('500 B');
    // Read-only disclaimer is a sibling note above the groups.
    expect(screen.getByText(/cannot delete files/i)).toBeInTheDocument();
  });

  it('searches and renders filtered results', async () => {
    const { api } = installMock();
    render(<ResultsView scanId={1} onError={vi.fn()} />);

    await screen.findByRole('table', { name: /folder sizes/i });

    fireEvent.change(screen.getByLabelText(/search in scan results/i), { target: { value: 'photo' } });
    fireEvent.click(screen.getByRole('button', { name: /^search$/i }));

    await waitFor(() => {
      expect(api.results.search).toHaveBeenCalledWith({ scanId: 1, query: 'photo' });
      expect(screen.getByText(/1 match/i)).toBeInTheDocument();
      expect(screen.getByText(/photo1\.png/, { exact: false })).toBeInTheDocument();
    });
  });

  it('does not search on an empty query', async () => {
    const { api } = installMock();
    render(<ResultsView scanId={1} onError={vi.fn()} />);

    await screen.findByRole('table', { name: /folder sizes/i });
    expect(screen.getByRole('button', { name: /^search$/i })).toBeDisabled();
    expect(api.results.search).not.toHaveBeenCalled();
  });

  it('invokes CSV and JSON export with the given outPath', async () => {
    const { api } = installMock();
    render(<ResultsView scanId={1} onError={vi.fn()} />);

    await screen.findByRole('table', { name: /folder sizes/i });

    fireEvent.change(screen.getByLabelText(/report output path/i), {
      target: { value: 'C:\\temp\\report.csv' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^export csv$/i }));

    await waitFor(() => {
      expect(api.export.report).toHaveBeenCalledWith({
        scanId: 1,
        format: 'csv',
        outPath: 'C:\\temp\\report.csv',
      });
      expect(screen.getByText(/report written to/i)).toHaveTextContent('C:\\temp\\report.csv');
    });

    fireEvent.click(screen.getByRole('button', { name: /^export json$/i }));
    await waitFor(() => {
      expect(api.export.report).toHaveBeenCalledWith({
        scanId: 1,
        format: 'json',
        outPath: 'C:\\temp\\report.csv',
      });
    });
  });

  it('reports backend errors through onError', async () => {
    const onError = vi.fn();
    installMock({
      results: {
        summary: vi.fn(async () => ({ ok: false, error: { code: 'SCAN_NOT_FOUND', message: 'gone' } })),
        duplicates: vi.fn(async () => ok({ groups: [] })),
        search: vi.fn(async () => ok({ files: [] })),
      },
    } as never);
    render(<ResultsView scanId={9} onError={onError} />);

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith(expect.stringContaining('could not be found'));
    });
  });

  it('shows the duplicate heading count', async () => {
    installMock();
    render(<ResultsView scanId={1} onError={vi.fn()} />);

    expect(await screen.findByRole('heading', { name: /duplicate groups \(1\)/i })).toBeInTheDocument();
  });
});
