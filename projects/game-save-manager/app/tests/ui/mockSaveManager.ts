/**
 * Mock for window.saveManager used by renderer component tests.
 * Install with installMockSaveManager(); capture event listeners via the
 * returned `events` object to simulate backup progress/completion/failure.
 */
import type {
  Backup,
  BackupCompletedEvent,
  BackupFailedEvent,
  BackupProgressEvent,
  Game,
  IpcResult,
  SaveManagerApi,
} from '../../shared/types';

export interface MockEvents {
  progressListeners: Array<(e: BackupProgressEvent) => void>;
  completedListeners: Array<(e: BackupCompletedEvent) => void>;
  failedListeners: Array<(e: BackupFailedEvent) => void>;
}

export interface MockSaveManager {
  api: SaveManagerApi;
  events: MockEvents;
  calls: {
    backupsRestore: Array<{ backupId: number; confirmed: true }>;
    backupsCreate: Array<{ gameId: number; label?: string }>;
    backupsVerify: Array<{ backupId: number }>;
    gamesAdd: Array<{ name: string; savePath: string; source?: Game['source'] }>;
    schedulesSet: Array<{ gameId: number; intervalMinutes: number; enabled?: boolean }>;
  };
}

function ok<T>(data: T): IpcResult<T> {
  return { ok: true, data };
}

export function makeGame(overrides: Partial<Game> = {}): Game {
  return {
    id: 1,
    name: 'Test Game',
    savePath: 'C:\\Saves\\Test Game',
    source: 'manual',
    createdAt: '2026-10-23T10:00:00.000Z',
    ...overrides,
  };
}

export function makeBackup(overrides: Partial<Backup> = {}): Backup {
  return {
    id: 11,
    gameId: 1,
    createdAt: '2026-10-23T10:05:00.000Z',
    label: 'Before boss fight',
    fileCount: 2,
    totalBytes: 2048,
    backupDir: 'C:\\Backups\\1\\2026-10-23T10-05-00',
    notes: null,
    ...overrides,
  };
}

export function installMockSaveManager(): MockSaveManager {
  const events: MockEvents = {
    progressListeners: [],
    completedListeners: [],
    failedListeners: [],
  };
  const calls: MockSaveManager['calls'] = {
    backupsRestore: [],
    backupsCreate: [],
    backupsVerify: [],
    gamesAdd: [],
    schedulesSet: [],
  };

  const sub = <T>(arr: Array<(e: T) => void>, listener: (e: T) => void): (() => void) => {
    arr.push(listener);
    return () => {
      const i = arr.indexOf(listener);
      if (i >= 0) {
        arr.splice(i, 1);
      }
    };
  };

  const game = makeGame();

  const api: SaveManagerApi = {
    games: {
      list: () => Promise.resolve(ok([game])),
      add: (input) => {
        calls.gamesAdd.push(input);
        return Promise.resolve(ok(makeGame({ id: 2, name: input.name, savePath: input.savePath })));
      },
      update: (input) => Promise.resolve(ok({ ...game, ...input })),
      remove: () => Promise.resolve(ok({ removed: true })),
      discoverCandidates: () => Promise.resolve(ok([])),
      chooseFolder: () => Promise.resolve(ok({ path: null })),
    },
    backups: {
      create: (input) => {
        calls.backupsCreate.push(input);
        return Promise.resolve(
          ok({
            skipped: false,
            backup: makeBackup({ id: 99, label: input.label ?? null }),
            skippedFiles: [],
            notes: [],
          }),
        );
      },
      list: () => Promise.resolve(ok([makeBackup()])),
      get: (input) =>
        Promise.resolve(
          ok({
            ...makeBackup({ id: input.backupId }),
            files: [
              { relPath: 'save1.dat', sha256: 'a'.repeat(64), sizeBytes: 1024 },
              { relPath: 'slot2/save2.dat', sha256: 'b'.repeat(64), sizeBytes: 1024 },
            ],
          }),
        ),
      verify: (input) => {
        calls.backupsVerify.push(input);
        return Promise.resolve(ok({ backupId: input.backupId, ok: true, checkedFiles: 2, corrupt: [] }));
      },
      restore: (input) => {
        calls.backupsRestore.push(input);
        return Promise.resolve(
          ok({ backupId: input.backupId, safetyBackupId: 100, restoredFiles: 2, mismatches: [] }),
        );
      },
    },
    schedules: {
      list: () => Promise.resolve(ok([])),
      set: (input) => {
        calls.schedulesSet.push(input);
        return Promise.resolve(
          ok({ id: 1, gameId: input.gameId, intervalMinutes: input.intervalMinutes, enabled: input.enabled ?? true, lastRunAt: null }),
        );
      },
      delete: () => Promise.resolve(ok({ removed: true })),
    },
    events: {
      onBackupProgress: (listener) => sub(events.progressListeners, listener),
      onBackupCompleted: (listener) => sub(events.completedListeners, listener),
      onBackupFailed: (listener) => sub(events.failedListeners, listener),
    },
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (window as any).saveManager = api;

  return { api, events, calls };
}
