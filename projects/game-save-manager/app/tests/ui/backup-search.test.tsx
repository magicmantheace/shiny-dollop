/**
 * Backup history search filters rows by label and by timestamp.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import GameDetail from '../../src/components/GameDetail';
import { SaveManagerProvider } from '../../src/store';
import { installMockSaveManager, makeBackup, makeGame, type MockSaveManager } from './mockSaveManager';

let mock: MockSaveManager;

beforeEach(() => {
  mock = installMockSaveManager();
  // Three backups with distinct labels and dates.
  mock.api.backups.list = () =>
    Promise.resolve({
      ok: true,
      data: [
        makeBackup({ id: 11, createdAt: '2026-10-23T10:05:00.000Z', label: 'Before boss fight' }),
        makeBackup({ id: 12, createdAt: '2026-10-20T09:00:00.000Z', label: 'After DLC install' }),
        makeBackup({ id: 13, createdAt: '2026-10-18T08:00:00.000Z', label: null }),
      ],
    });
});

function renderDetail(): void {
  render(
    <SaveManagerProvider>
      <GameDetail game={makeGame()} onBack={() => {}} />
    </SaveManagerProvider>,
  );
}

describe('backup history search', () => {
  it('filters backups by label text', async () => {
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText('Before boss fight');

    await user.type(screen.getByRole('searchbox', { name: /search backup history/i }), 'dlc');

    expect(screen.getByText('After DLC install')).toBeInTheDocument();
    expect(screen.queryByText('Before boss fight')).not.toBeInTheDocument();
  });

  it('matches timestamps as well as labels', async () => {
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText('Before boss fight');

    await user.type(screen.getByRole('searchbox', { name: /search backup history/i }), '2026-10-20');

    expect(screen.getByText('After DLC install')).toBeInTheDocument();
    expect(screen.queryByText('Before boss fight')).not.toBeInTheDocument();
  });

  it('shows a no-match message when nothing matches', async () => {
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText('Before boss fight');

    await user.type(screen.getByRole('searchbox', { name: /search backup history/i }), 'zzz-nope');

    expect(screen.getByText(/no backups match/i)).toBeInTheDocument();
  });
});
