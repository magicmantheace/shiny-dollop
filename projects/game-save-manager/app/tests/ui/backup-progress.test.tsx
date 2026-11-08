/**
 * Backup progress: the detail view renders live progress from the
 * onBackupProgress event (phase, done/total, current file).
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import GameDetail from '../../src/components/GameDetail';
import { SaveManagerProvider } from '../../src/store';
import { installMockSaveManager, makeGame, type MockSaveManager } from './mockSaveManager';

let mock: MockSaveManager;

beforeEach(() => {
  mock = installMockSaveManager();
});

function renderDetail(): void {
  render(
    <SaveManagerProvider>
      <GameDetail game={makeGame()} onBack={() => {}} />
    </SaveManagerProvider>,
  );
}

describe('backup progress events', () => {
  it('renders hashing phase with done/total and current file', async () => {
    renderDetail();
    await screen.findByRole('button', { name: /back up now/i });

    act(() => {
      for (const listener of mock.events.progressListeners) {
        listener({
          gameId: 1,
          phase: 'hash',
          done: 3,
          total: 10,
          currentFile: 'saves/slot1.dat',
        });
      }
    });

    const bar = await screen.findByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '30');
    expect(screen.getByText(/hashing 3 of 10 files/i)).toBeInTheDocument();
    expect(screen.getByText('saves/slot1.dat')).toBeInTheDocument();
  });

  it('switches to the copying phase label', async () => {
    renderDetail();
    await screen.findByRole('button', { name: /back up now/i });

    act(() => {
      for (const listener of mock.events.progressListeners) {
        listener({ gameId: 1, phase: 'copy', done: 7, total: 10 });
      }
    });

    expect(await screen.findByText(/copying 7 of 10 files/i)).toBeInTheDocument();
  });

  it('progress for other games does not show in this detail view', async () => {
    renderDetail();
    await screen.findByRole('button', { name: /back up now/i });

    act(() => {
      for (const listener of mock.events.progressListeners) {
        listener({ gameId: 999, phase: 'copy', done: 1, total: 2 });
      }
    });

    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });
});
