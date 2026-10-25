/**
 * Skipped-file warnings: when a backup succeeds but some saves were skipped,
 * the user must SEE which paths were excluded and why — both for a manual
 * "Back up now" and for scheduled backups arriving via backup.completed.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import GameDetail from '../../src/components/GameDetail';
import Toasts from '../../src/components/Toasts';
import { SaveManagerProvider } from '../../src/store';
import { installMockSaveManager, makeBackup, makeGame, type MockSaveManager } from './mockSaveManager';

let mock: MockSaveManager;

beforeEach(() => {
  mock = installMockSaveManager();
});

const SKIPPED = [{ relPath: 'locked.sav', reason: 'unreadable file: EACCES' }];

describe('skipped-file warnings', () => {
  it('manual backup shows the skipped paths and reasons after success', async () => {
    mock.api.backups.create = (input) => {
      mock.calls.backupsCreate.push(input);
      return Promise.resolve({
        ok: true,
        data: {
          skipped: false,
          backup: makeBackup({ id: 99, label: input.label ?? null }),
          skippedFiles: SKIPPED,
          notes: [],
        },
      });
    };

    render(
      <SaveManagerProvider>
        <GameDetail game={makeGame()} onBack={() => {}} />
      </SaveManagerProvider>,
    );

    fireEvent.click(await screen.findByRole('button', { name: /back up now/i }));

    expect(await screen.findByText(/locked\.sav/)).toBeInTheDocument();
    expect(screen.getByText(/skipped 1 file/i)).toBeInTheDocument();
  });

  it('scheduled backup completion event surfaces a warning toast with the skipped path', async () => {
    render(
      <SaveManagerProvider>
        <Toasts />
        <GameDetail game={makeGame()} onBack={() => {}} />
      </SaveManagerProvider>,
    );
    await screen.findByRole('button', { name: /back up now/i });

    act(() => {
      for (const listener of mock.events.completedListeners) {
        listener({
          gameId: 1,
          backupId: 42,
          label: 'scheduled backup',
          fileCount: 3,
          totalBytes: 100,
          skipped: false,
          skippedFiles: SKIPPED,
        });
      }
    });

    expect(await screen.findByText(/locked\.sav/)).toBeInTheDocument();
    expect(screen.getByText(/skipped/i)).toBeInTheDocument();
  });
});
