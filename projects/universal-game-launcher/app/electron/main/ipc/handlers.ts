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
  getGame,
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
import { coverDataUrl } from '../files/cover-store';
import {
  RealSteamOs,
  SteamAdapter,
  createScanController,
  lastScan,
  recordScan,
  syncSteamGames,
  type ScanController,
  type SteamOs,
} from '../sources/steam';
import {
  EpicAdapter,
  RealEpicOs,
  createEpicScanController,
  lastScan as epicLastScan,
  recordScan as epicRecordScan,
  syncEpicGames,
  type EpicOs,
} from '../sources/epic';
import { BattleNetAdapter, RealBattleNetOs, type BattleNetOs } from '../sources/battlenet';

export interface HandlerDeps {
  db: DatabaseSync;
  launcher: GameLauncher;
  chooseExecutable: () => Promise<PickResult>;
  /** Override for tests. Imports a user-picked image into the covers dir. */
  chooseCover: () => Promise<{ canceled: true } | { coverPath: string }>;
  /** Covers directory (app-data). Override for tests. */
  getCoversDir: () => string;
  getMainWindow: () => BrowserWindow | null;
  /** Override for tests. Defaults to the real OS layer. */
  steamOs?: SteamOs;
  /** Override for tests. Defaults to the real OS layer. */
  epicOs?: EpicOs;
  /** Override for tests. Defaults to the real OS layer. */
  battleNetOs?: BattleNetOs;
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

/** In-flight store scans by source — used to honor cancellation requests. */
const activeScans = new Map<GameSource, ScanController>();

function steamOsFor(deps: HandlerDeps): SteamOs {
  return deps.steamOs ?? new RealSteamOs();
}

function epicOsFor(deps: HandlerDeps): EpicOs {
  return deps.epicOs ?? new RealEpicOs();
}

function battleNetOsFor(deps: HandlerDeps): BattleNetOs {
  return deps.battleNetOs ?? new RealBattleNetOs();
}

function battleNetStatus(db: DatabaseSync, os: BattleNetOs): SourceStatus {
  const adapter = new BattleNetAdapter(os);
  const probe = adapter.probe();
  const scan = lastScan(db, 'battlenet');
  const gamesFound = listGames(db, { source: 'battlenet', includeHidden: true }).length;
  const parts = [probe.reason];
  if (scan.scannedAt) {
    parts.push(
      `Last scan ${scan.scannedAt}${scan.status !== 'ok' ? ` (${scan.status}${scan.error ? `: ${scan.error}` : ''})` : ''}.`,
    );
  }
  return {
    source: 'battlenet',
    available: probe.status === 'installed',
    reason: parts.join(' '),
    lastScanAt: scan.scannedAt,
    gamesFound,
  };
}

function steamStatus(db: DatabaseSync, os: SteamOs): SourceStatus {
  const adapter = new SteamAdapter(os);
  const probe = adapter.probe();
  const scan = lastScan(db, 'steam');
  const gamesFound = listGames(db, { source: 'steam', includeHidden: true }).length;
  const parts = [probe.reason];
  if (scan.scannedAt) {
    parts.push(
      `Last scan ${scan.scannedAt}${scan.status !== 'ok' ? ` (${scan.status}${scan.error ? `: ${scan.error}` : ''})` : ''}.`,
    );
  }
  return {
    source: 'steam',
    available: probe.status === 'installed',
    reason: parts.join(' '),
    lastScanAt: scan.scannedAt,
    gamesFound,
  };
}

function epicStatus(db: DatabaseSync, os: EpicOs): SourceStatus {
  const adapter = new EpicAdapter(os);
  const probe = adapter.probe();
  const scan = epicLastScan(db, 'epic');
  const gamesFound = listGames(db, { source: 'epic', includeHidden: true }).length;
  const parts = [probe.reason];
  if (scan.scannedAt) {
    parts.push(
      `Last scan ${scan.scannedAt}${scan.status !== 'ok' ? ` (${scan.status}${scan.error ? `: ${scan.error}` : ''})` : ''}.`,
    );
  }
  return {
    source: 'epic',
    available: probe.status === 'installed',
    reason: parts.join(' '),
    lastScanAt: scan.scannedAt,
    gamesFound,
  };
}

/**
 * Run a store library scan: probe, discover, merge idempotently, log.
 * Only one scan per source runs at a time; a second call while one is in
 * flight fails explicitly instead of interleaving. A source's failure is
 * isolated — it never touches another source's rows.
 */
function runStoreScan(
  deps: HandlerDeps,
  source: 'steam' | 'epic',
): { scannedAt: string; gamesFound: number } {
  if (activeScans.has(source)) {
    throw new ValidationError('SCAN_IN_PROGRESS', `A ${source} scan is already running.`);
  }
  if (source === 'steam') {
    const controller = createScanController();
    activeScans.set(source, controller);
    try {
      const adapter = new SteamAdapter(steamOsFor(deps));
      const result = adapter.scan(controller.token);
      if (result.status === 'cancelled') {
        recordScan(deps.db, 'steam', 'cancelled', 0, 'Cancelled by the user.');
        return { scannedAt: result.scannedAt, gamesFound: 0 };
      }
      if (result.status === 'failed') {
        recordScan(deps.db, 'steam', 'failed', 0, result.error);
        throw new ValidationError('SCAN_FAILED', result.error ?? 'Steam scan failed.');
      }
      const syncResult = syncSteamGames(deps.db, result.games);
      const gamesFound = listGames(deps.db, { source: 'steam', includeHidden: true }).length;
      const note =
        result.warnings.length > 0
          ? `${result.warnings.length} warning(s), e.g.: ${result.warnings[0]}`
          : `Imported/updated ${syncResult.added + syncResult.updated} Steam game(s).`;
      recordScan(deps.db, 'steam', 'ok', gamesFound, result.warnings.length > 0 ? note : null);
      return { scannedAt: result.scannedAt, gamesFound };
    } finally {
      activeScans.delete(source);
    }
  }
  const controller = createEpicScanController();
  activeScans.set(source, controller);
  try {
    const adapter = new EpicAdapter(epicOsFor(deps));
    const result = adapter.scan(controller.token);
    if (result.status === 'cancelled') {
      epicRecordScan(deps.db, 'epic', 'cancelled', 0, 'Cancelled by the user.');
      return { scannedAt: result.scannedAt, gamesFound: 0 };
    }
    if (result.status === 'failed') {
      epicRecordScan(deps.db, 'epic', 'failed', 0, result.error);
      throw new ValidationError('SCAN_FAILED', result.error ?? 'Epic scan failed.');
    }
    const syncResult = syncEpicGames(deps.db, result.games);
    const gamesFound = listGames(deps.db, { source: 'epic', includeHidden: true }).length;
    const note =
      result.warnings.length > 0
        ? `${result.warnings.length} warning(s), e.g.: ${result.warnings[0]}`
        : `Imported/updated ${syncResult.added + syncResult.updated} Epic game(s).`;
    epicRecordScan(deps.db, 'epic', 'ok', gamesFound, result.warnings.length > 0 ? note : null);
    return { scannedAt: result.scannedAt, gamesFound };
  } finally {
    activeScans.delete(source);
  }
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
      channel: IpcChannels.filesChooseCover,
      schema: z.object({}).strict().optional(),
      run: (_payload, deps) => deps.chooseCover(),
    },
    {
      channel: IpcChannels.filesCoverData,
      schema: schemas.filesCoverDataSchema,
      run: (payload, deps) => {
        const p = payload as { id: string };
        const game = getGame(deps.db, p.id);
        if (!game || !game.coverPath) return Promise.resolve({ dataUrl: null });
        return Promise.resolve({
          dataUrl: coverDataUrl(deps.getCoversDir(), game.coverPath),
        });
      },
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
        const steam = steamStatus(deps.db, steamOsFor(deps));
        const epic = epicStatus(deps.db, epicOsFor(deps));
        const battlenet = battleNetStatus(deps.db, battleNetOsFor(deps));
        return Promise.resolve([manual, steam, epic, battlenet]);
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
        if (p.source === 'steam' || p.source === 'epic') {
          return Promise.resolve(runStoreScan(deps, p.source));
        }
        if (p.source === 'battlenet') {
          const adapter = new BattleNetAdapter(battleNetOsFor(deps));
          const result = adapter.scan();
          const note =
            result.warnings.length > 0 ? result.warnings[0]! : 'No per-game discovery for Battle.net.';
          recordScan(deps.db, 'battlenet', 'ok', 0, note);
          return Promise.resolve({
            scannedAt: result.scannedAt,
            gamesFound: listGames(deps.db, { source: 'battlenet', includeHidden: true }).length,
          });
        }
        throw new ValidationError(
          'NOT_IMPLEMENTED',
          'Store scanning is not implemented yet. Manual entries are fully supported.',
        );
      },
    },
    {
      channel: IpcChannels.sourcesCancelScan,
      schema: z.object({}).strict().optional(),
      run: () => {
        let cancelledAny = false;
        for (const [, controller] of activeScans) {
          controller.cancel();
          cancelledAny = true;
        }
        activeScans.clear();
        return Promise.resolve({ cancelled: cancelledAny });
      },
    },
    {
      channel: IpcChannels.sourcesOpenClient,
      schema: schemas.sourcesOpenClientSchema,
      run: async (payload, deps) => {
        const p = payload as { source: 'epic' | 'battlenet' };
        await deps.launcher.openClient(p.source);
        return { opened: true };
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
