import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { App } from '../App';
import { installMock } from './mockStorageAnalyzer';

describe('App', () => {
  it('displays backend errors in a dismissible banner', async () => {
    installMock({
      dialog: {
        chooseDirectory: vi.fn(async () => ({
          ok: false as const,
          error: { code: 'PATH_NOT_FOUND', message: 'no such directory' },
        })),
      },
    } as never);
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: /choose folder/i }));

    const banner = await screen.findByRole('alert');
    expect(banner).toHaveTextContent(/the selected folder no longer exists/i);
    expect(banner).toHaveTextContent(/no such directory/);

    fireEvent.click(screen.getByRole('button', { name: /dismiss error/i }));
    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  it('navigates between New scan and History views', async () => {
    installMock();
    render(<App />);

    expect(screen.getByRole('heading', { name: /new scan/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^history$/i }));
    expect(await screen.findByRole('heading', { name: /scan history/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /new scan/i })).toBeInTheDocument();
  });
});
