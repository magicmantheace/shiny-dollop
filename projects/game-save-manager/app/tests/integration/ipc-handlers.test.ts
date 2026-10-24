/**
 * IPC handler regression tests: the restore handler must emit a terminal
 * backup.completed / backup.failed event on both paths — otherwise the
 * renderer's progress indicator sticks on "Backing up…" forever.
 *
 * The real 'electron' module is mocked: ipcMain.handle captures the
 * registered handlers and getMainWindow returns a fake window whose
 * webContents.send is a spy.
 */
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { ipcMain, type BrowserWindow } from 'electron';
import { registerIpcHandlers } from '../../electron/main/ipc/handlers';
import { IpcChannels, IpcEvents } from '../../shared/ipc-channels';
import { createBackup } from '../../electron/main/backup/engine';
import { addTestGame, makeFixture, seedSaveTree, type Fixture } from '../helpers';

vi.mock('electron', () => ({
  BrowserWindow: class {},
  dialog: { showOpenDialog: vi.fn() },
  ipcMain: { handle: vi.fn() },
}));

type HandlerFn = (event: unknown, payload: unknown) => Promise<unknown>;

function restoreHandler(): HandlerFn {
  const calls = (ipcMain.handle as Mock).mock.calls as [string, HandlerFn][];
  const found = calls.find(([channel]) => channel === IpcChannels.backupsRestore);
  if (!found) throw new Error('backups.restore handler was not registered');
  return found[1];
}

let fixture: Fixture | null = null;
let send: ReturnType<typeof vi.fn>;

afterEach(() => {
  fixture?.cleanup();
  fixture = null;
});

beforeEach(() => {
  fixture = makeFixture();
  seedSaveTree(fixture.saveDir);
  send = vi.fn();
  registerIpcHandlers({
    db: fixture.db,
    backupsRoot: fixture.backupsRoot,
    getMainWindow: () => ({ webContents: { send } }) as unknown as BrowserWindow,
  });
});

function useFixture(): Fixture {
  if (!fixture) throw new Error('fixture not set');
  return fixture;
}

describe('backupsRestore handler terminal events', () => {
  it('emits backup.completed when a restore succeeds', async () => {
    const f = useFixture();
    const game = addTestGame(f);
    const created = await createBackup({ db: f.db, backupsRoot: f.backupsRoot }, game.id);

    const result = (await restoreHandler()({}, { backupId: created.backup.id, confirmed: true })) as {
      ok: boolean;
    };

    expect(result.ok).toBe(true);
    expect(send).toHaveBeenCalledWith(
      IpcEvents.backupCompleted,
      expect.objectContaining({ gameId: game.id, backupId: created.backup.id }),
    );
  });

  it('emits backup.failed when a restore fails', async () => {
    const result = (await restoreHandler()({}, { backupId: 424242, confirmed: true })) as {
      ok: boolean;
      error?: { code: string; message: string };
    };

    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe('BACKUP_NOT_FOUND');
    expect(send).toHaveBeenCalledWith(
      IpcEvents.backupFailed,
      expect.objectContaining({ code: 'BACKUP_NOT_FOUND' }),
    );
    // …and the envelope still carries the error for the direct caller.
    expect(result.error?.message).toMatch(/does not exist/);
  });
});
