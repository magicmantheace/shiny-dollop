import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { StartView } from '../views/StartView';
import { installMock, ok } from './mockStorageAnalyzer';

describe('StartView', () => {
  it('runs the full start-scan flow: choose folder, edit exclusions, start', async () => {
    const { api } = installMock({
      dialog: {
        chooseDirectory: vi.fn(async () => ok({ path: 'C:\\data' })),
      },
      scan: {
        start: vi.fn(async () => ok({ scanId: 9 })),
        cancel: vi.fn(async () => ok({ ok: true })),
        status: vi.fn(async () => ok({ state: 'running', files: 0, dirs: 0, bytes: 0, startedAt: 'x', finishedAt: null })),
        list: vi.fn(async () => ok({ scans: [] })),
      },
    } as never);
    const onScanStarted = vi.fn();
    const onError = vi.fn();

    render(<StartView onScanStarted={onScanStarted} onError={onError} />);

    // Start button is disabled until a folder is chosen.
    expect(screen.getByRole('button', { name: /start scan/i })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /choose folder/i }));
    const pathInput = await screen.findByDisplayValue('C:\\data');
    expect(pathInput).toBeInTheDocument();
    expect(api.dialog.chooseDirectory).toHaveBeenCalledTimes(1);

    // Default exclusions are pre-filled.
    const exclusions = screen.getByLabelText(/exclusion patterns/i) as HTMLTextAreaElement;
    expect(exclusions.value).toContain('node_modules');

    // Edit exclusions, then start.
    fireEvent.change(exclusions, { target: { value: 'temp\n*.bak' } });
    fireEvent.click(screen.getByRole('button', { name: /start scan/i }));

    await waitFor(() => {
      expect(api.scan.start).toHaveBeenCalledWith({ rootPath: 'C:\\data', exclusions: ['temp', '*.bak'] });
      expect(onScanStarted).toHaveBeenCalledWith(9, undefined);
    });
    expect(onError).not.toHaveBeenCalled();
  });

  it('shows the protected-path warning banner for a drive root', async () => {
    installMock({
      dialog: { chooseDirectory: vi.fn(async () => ok({ path: 'C:\\' })) },
    } as never);
    render(<StartView onScanStarted={vi.fn()} onError={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: /choose folder/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/protected path warning/i);
    expect(screen.getByRole('alert')).toHaveTextContent(/read-only/i);
  });

  it('does not show the warning for an ordinary folder', async () => {
    installMock();
    render(<StartView onScanStarted={vi.fn()} onError={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: /choose folder/i }));
    await screen.findByDisplayValue('C:\\data');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('ignores a cancelled directory dialog', async () => {
    installMock({
      dialog: { chooseDirectory: vi.fn(async () => ok({ path: null })) },
    } as never);
    render(<StartView onScanStarted={vi.fn()} onError={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: /choose folder/i }));
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/no folder selected/i)).toHaveValue('');
    });
    expect(screen.getByRole('button', { name: /start scan/i })).toBeDisabled();
  });
});
