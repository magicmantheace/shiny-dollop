/**
 * IPC handlers. Every payload is validated with zod before anything touches
 * the database or filesystem. Responses use the uniform IpcResult envelope:
 * { ok: true, data } or { ok: false, error: { code, message } }.
 *
 * The renderer is untrusted: it can only invoke these narrow channels, never
 * raw filesystem or SQL access.
 */
import { BrowserWindow, dialog, ipcMain } from 'electron';
import type { DatabaseSync } from 'node:sqlite';
import { z } from 'zod';
import { IpcChannels, IpcEvents } from '../../../shared/ipc-channels';
import {
  backupCreateSchema,
  backupIdSchema,
  backupListSchema,
  backupRestoreSchema,
  emptySchema,
  gameAddSchema,
  gameIdSchema,
  gameUpdateSchema,
  scheduleDeleteSchema,
  scheduleSetSchema,
} from '../../../shared/schemas';
import type {
  BackupCompletedEvent,
  BackupFailedEvent,
  BackupProgressEvent,
  IpcResult,
} from '../../../shared/types';
import { addGame, getGame, listGames, removeGame, updateGame } from '../db/games';
import {
  getBackup,
  getBackupDetail,
  listBackups,
} from '../db/backups';
import { deleteSchedule, listSchedules, setSchedule } from '../db/schedules';
import { createBackup, restoreBackup, verifyBackup, type ProgressCallback } from '../backup/engine';
import { BackupError, BackupErrorCodes } from '../backup/errors';
import { runDiscovery } from '../discovery';

export interface HandlerDeps {
  db: DatabaseSync;
  backupsRoot: string;
  getMainWindow: () => BrowserWindow | null;
}

function ok<T>(data: T): IpcResult<T> {
  return { ok: true, data };
}

function fail(code: string, message: string): IpcResult<never> {
  return { ok: false, error: { code, message } };
}

function toErrorResult(err: unknown): IpcResult<never> {
  if (err instanceof BackupError) return fail(err.code, err.message);
  if (err instanceof z.ZodError) return fail('INVALID_INPUT', err.issues.map((i) => i.message).join('; '));
  return fail('INTERNAL_ERROR', err instanceof Error ? err.message : String(err));
}

function emitToRenderer(deps: HandlerDeps, event: string, payload: unknown): void {
  deps.getMainWindow()?.webContents.send(event, payload);
}

export function registerIpcHandlers(deps: HandlerDeps): void {
  const { db, backupsRoot } = deps;
  const engineDeps = { db, backupsRoot };

  const handle = <T>(channel: string, fn: (payload: unknown) => Promise<T>): void => {
    ipcMain.handle(channel, async (_event, payload: unknown) => {
      try {
        return ok(await fn(payload));
      } catch (err) {
        return toErrorResult(err);
      }
    });
  };

  // ---- games ----
  handle(IpcChannels.gamesList, async (payload) => {
    emptySchema.parse(payload ?? {});
    return listGames(db);
  });

  handle(IpcChannels.gamesAdd, async (payload) => {
    const input = gameAddSchema.parse(payload);
    return addGame(db, { name: input.name, savePath: input.savePath, source: input.source });
  });

  handle(IpcChannels.gamesUpdate, async (payload) => {
    const input = gameUpdateSchema.parse(payload);
    const patch: { name?: string | undefined; savePath?: string | undefined } = {};
    if (input.name !== undefined) patch.name = input.name;
    if (input.savePath !== undefined) patch.savePath = input.savePath;
    const game = updateGame(db, input.id, patch);
    if (!game) throw new BackupError(BackupErrorCodes.GAME_NOT_FOUND, `Game #${input.id} is not tracked.`);
    return game;
  });

  handle(IpcChannels.gamesRemove, async (payload) => {
    const input = gameIdSchema.parse(payload);
    return { removed: removeGame(db, input.id) };
  });

  handle(IpcChannels.gamesDiscoverCandidates, async (payload) => {
    emptySchema.parse(payload ?? {});
    return runDiscovery().candidates;
  });

  handle(IpcChannels.gamesChooseFolder, async (payload) => {
    emptySchema.parse(payload ?? {});
    const win = deps.getMainWindow();
    const dialogOptions = {
      title: 'Choose the game save folder',
      properties: ['openDirectory', 'createDirectory'] as ('openDirectory' | 'createDirectory')[],
    };
    const result = win
      ? await dialog.showOpenDialog(win, dialogOptions)
      : await dialog.showOpenDialog(dialogOptions);
    return { path: result.canceled ? null : (result.filePaths[0] ?? null) };
  });

  // ---- backups ----
  handle(IpcChannels.backupsCreate, async (payload) => {
    const input = backupCreateSchema.parse(payload);
    const result = await createBackup(engineDeps, input.gameId, {
      label: input.label,
      onProgress: (p) => {
        const evt: BackupProgressEvent = { gameId: input.gameId, ...p };
        emitToRenderer(deps, IpcEvents.backupProgress, evt);
      },
    });
    const completed: BackupCompletedEvent = {
      gameId: input.gameId,
      backupId: result.backup.id,
      label: result.backup.label,
      fileCount: result.backup.fileCount,
      totalBytes: result.backup.totalBytes,
      skipped: result.skipped,
      skippedFiles: result.skippedFiles,
    };
    emitToRenderer(deps, IpcEvents.backupCompleted, completed);
    return result;
  });

  handle(IpcChannels.backupsList, async (payload) => {
    const input = backupListSchema.parse(payload);
    return listBackups(db, input.gameId);
  });

  handle(IpcChannels.backupsGet, async (payload) => {
    const input = backupIdSchema.parse(payload);
    const detail = getBackupDetail(db, input.backupId);
    if (!detail) {
      throw new BackupError(BackupErrorCodes.BACKUP_NOT_FOUND, `Backup #${input.backupId} does not exist.`);
    }
    return detail;
  });

  handle(IpcChannels.backupsVerify, async (payload) => {
    const input = backupIdSchema.parse(payload);
    return verifyBackup(engineDeps, input.backupId);
  });

  handle(IpcChannels.backupsRestore, async (payload) => {
    // zod enforces confirmed: z.literal(true) — no other shape restores.
    const input = backupRestoreSchema.parse(payload);
    const detail = getBackup(db, input.backupId);
    const gameId = detail?.gameId ?? -1;
    const onProgress: ProgressCallback = (p) => {
      const evt: BackupProgressEvent = {
        gameId,
        backupId: input.backupId,
        ...p,
      };
      emitToRenderer(deps, IpcEvents.backupProgress, evt);
    };
    try {
      const result = await restoreBackup(engineDeps, input.backupId, {
        confirmed: input.confirmed,
        onProgress,
      });
      const completed: BackupCompletedEvent = {
        gameId,
        backupId: input.backupId,
        label: detail?.label ?? null,
        fileCount: result.restoredFiles,
        totalBytes: detail?.totalBytes ?? 0,
        skipped: false,
        // A restore either completes fully or aborts (its safety backup must
        // be complete before any writes), so nothing was skipped here.
        skippedFiles: [],
      };
      emitToRenderer(deps, IpcEvents.backupCompleted, completed);
      return result;
    } catch (err) {
      // Terminal event on the failure path too — otherwise the renderer's
      // progress indicator sticks on "Backing up…" forever.
      const failed: BackupFailedEvent = {
        gameId,
        code:
          err instanceof BackupError
            ? err.code
            : err instanceof z.ZodError
              ? 'INVALID_INPUT'
              : 'INTERNAL_ERROR',
        message: err instanceof Error ? err.message : String(err),
      };
      emitToRenderer(deps, IpcEvents.backupFailed, failed);
      throw err;
    }
  });

  // ---- schedules ----
  handle(IpcChannels.schedulesList, async (payload) => {
    emptySchema.parse(payload ?? {});
    return listSchedules(db);
  });

  handle(IpcChannels.schedulesSet, async (payload) => {
    const input = scheduleSetSchema.parse(payload);
    const game = getGame(db, input.gameId);
    if (!game) {
      throw new BackupError(BackupErrorCodes.GAME_NOT_FOUND, `Game #${input.gameId} is not tracked.`);
    }
    return setSchedule(db, {
      gameId: input.gameId,
      intervalMinutes: input.intervalMinutes,
      enabled: input.enabled,
    });
  });

  handle(IpcChannels.schedulesDelete, async (payload) => {
    const input = scheduleDeleteSchema.parse(payload);
    return { removed: deleteSchedule(db, input.gameId) };
  });

}
