/**
 * IPC wiring. Every channel validates its payload with zod and returns an
 * ApiResult — the main process never throws across the IPC boundary and
 * never leaks stack traces or unrelated paths to the renderer.
 */
import { BrowserWindow, ipcMain } from 'electron';
import type { DatabaseSync } from 'node:sqlite';
import { z } from 'zod';
import { IpcChannels } from '../../../shared/ipc-channels';
import * as schemas from '../../../shared/ipc-schemas';
import type { ApiError, GameSource, Settings, SourceStatus } from '../../../shared/types';
import {
  listGames,
  addManualGame,
  removeGame,
  setFavorite,
  updateGame,
  type AddManualInput,
  type ListQuery,
  type UpdateGameInput,
} from '../data/games';
import { clearSessions, listSessions } from '../data/sessions';
import { getSettings, updateSettings } from '../data/settings';
import { ValidationError } from '../launch/validation';
import type { GameLauncher } from '../launch/launcher';
import type { PickResult } from '../files/picker';

export interface HandlerDeps {
  db: DatabaseSync;
  launcher: GameLauncher;
  chooseExecutable: () => Promise<PickResult>;
  getMainWindow: () => BrowserWindow | null;
}

function toApiError(err: unknown): ApiError {
  if (err instanceof z.ZodError) {
    const first = err.issues[0];
    const where = first && first.path.length > 0 ? ` (${first.path.join('.')})` : '';
    return {
      code: 'VALIDATION_ERROR',
      message: `Invalid request${where}: ${first?.message ?? 'malformed payload'}.`,
    };
  }
  if (err instanceof ValidationError) {
    return { code: err.code, message: err.message };
  }
  console.error('[ipc] unexpected handler error:', err);
  return { code: 'INTERNAL', message: 'Something went wrong. Please try again.' };
}

interface HandlerDef {
  channel: string;
  schema: z.ZodTypeAny;
  run: (payload: never, deps: HandlerDeps) => Promise<unknown>;
}

const STORE_SOURCES: GameSource[] = ['steam', 'epic', 'battlenet'];

function storeStatus(db: DatabaseSync, source: GameSource): SourceStatus {
  return {
    source,
    available: false,
    reason: 'Store scanning arrives in a later milestone. Add games manually for now.',
    lastScanAt: null,
    gamesFound: listGames(db, { source, includeHidden: true }).length,
  };
}

export function createHandlers(): HandlerDef[] {
  return [
    {
      channel: IpcChannels.libraryList,
      schema: schemas.libraryListSchema,
      run: (payload, deps) => Promise.resolve(listGames(deps.db, (payload ?? {}) as ListQuery)),
    },
    {
      channel: IpcChannels.libraryAddManual,
      schema: schemas.libraryAddManualSchema,
      run: (payload, deps) => addManualGame(deps.db, payload as AddManualInput),
    },
    {
      channel: IpcChannels.libraryUpdate,
      schema: schemas.libraryUpdateSchema,
      run: (payload, deps) => updateGame(deps.db, payload as UpdateGameInput),
    },
    {
      channel: IpcChannels.libraryRemove,
      schema: schemas.libraryRemoveSchema,
      run: (payload, deps) => {
        removeGame(deps.db, (payload as { id: string }).id);
        return Promise.resolve(null);
      },
    },
    {
      channel: IpcChannels.librarySetFavorite,
      schema: schemas.librarySetFavoriteSchema,
      run: (payload, deps) => {
        const p = payload as { id: string; favorite: boolean };
        return Promise.resolve(setFavorite(deps.db, p.id, p.favorite));
      },
    },
    {
      channel: IpcChannels.gamesLaunch,
      schema: schemas.gamesLaunchSchema,
      run: async (payload, deps) => {
        const p = payload as { id: string };
        const result = await deps.launcher.launch(p.id);
        if (!result.alreadyRunning && getSettings(deps.db).minimizeOnLaunch) {
          deps.getMainWindow()?.minimize();
        }
        return result;
      },
    },
    {
      channel: IpcChannels.sessionsList,
      schema: schemas.sessionsListSchema,
      run: (payload, deps) =>
        Promise.resolve(listSessions(deps.db, (payload ?? {}) as { gameId?: string; limit?: number })),
    },
    {
      channel: IpcChannels.sessionsClear,
      schema: z.object({}).strict().optional(),
      run: (_payload, deps) => {
        clearSessions(deps.db);
        return Promise.resolve(null);
      },
    },
    {
      channel: IpcChannels.settingsGet,
      schema: z.object({}).strict().optional(),
      run: (_payload, deps) => Promise.resolve(getSettings(deps.db)),
    },
    {
      channel: IpcChannels.settingsUpdate,
      schema: schemas.settingsUpdateSchema,
      run: (payload, deps) => Promise.resolve(updateSettings(deps.db, (payload ?? {}) as Partial<Settings>)),
    },
    {
      channel: IpcChannels.filesChooseExecutable,
      schema: z.object({}).strict().optional(),
      run: (_payload, deps) => deps.chooseExecutable(),
    },
    {
      channel: IpcChannels.sourcesStatus,
      schema: z.object({}).strict().optional(),
      run: (_payload, deps) => {
        const manual: SourceStatus = {
          source: 'manual',
          available: true,
          reason: 'Add executables with the Add Game button.',
          lastScanAt: null,
          gamesFound: listGames(deps.db, { source: 'manual', includeHidden: true }).length,
        };
        return Promise.resolve([manual, ...STORE_SOURCES.map((s) => storeStatus(deps.db, s))]);
      },
    },
    {
      channel: IpcChannels.sourcesScan,
      schema: schemas.sourcesScanSchema,
      run: (payload, deps) => {
        const p = payload as { source: GameSource };
        if (p.source === 'manual') {
          return Promise.resolve({
            scannedAt: new Date().toISOString(),
            gamesFound: listGames(deps.db, { source: 'manual', includeHidden: true }).length,
          });
        }
        throw new ValidationError(
          'NOT_IMPLEMENTED',
          'Store scanning is not implemented yet. Manual entries are fully supported.',
        );
      },
    },
  ];
}

export function registerIpcHandlers(deps: HandlerDeps): void {
  for (const def of createHandlers()) {
    ipcMain.handle(def.channel, async (_event, payload: unknown) => {
      try {
        const parsed = def.schema.parse(payload);
        const data = await def.run(parsed as never, deps);
        return { ok: true, data };
      } catch (err) {
        return { ok: false, error: toApiError(err) };
      }
    });
  }
}
