// IPC boundary: zod-parse the raw args array for every method, delegate
// to DungeonService, and convert every failure to a plain { code,
// message } PddError so nothing exotic crosses the bridge.
import { ZodError } from 'zod';
import {
  PDD_ERROR_CODES,
  isPddError,
  pddError,
  type PddError,
  type PddErrorCode,
} from '../../shared/errors.js';
import { PDD_CHANNELS, type PddMethodName } from './channels.js';
import {
  dungeonsDeleteSchema,
  dungeonsGetSchema,
  dungeonsSaveSchema,
  exportJsonSchema,
  exportMarkdownSchema,
  generateSchema,
  importJsonSchema,
  placementsAddSchema,
  placementsMoveSchema,
  placementsRemoveSchema,
  validateMapSchema,
} from './schemas.js';
import type { DungeonService } from './service.js';

export interface IpcMainLike {
  handle(channel: string, listener: (event: unknown, ...args: unknown[]) => Promise<unknown>): void;
}

type Handler = (...args: unknown[]) => Promise<unknown>;

function toPlain(err: unknown, fallback: PddErrorCode): PddError {
  if (isPddError(err)) return { code: err.code, message: err.message };
  if (err instanceof ZodError) {
    return pddError(
      fallback,
      `Invalid input: ${err.issues.map((i) => i.message).join('; ') || err.message}`,
    );
  }
  return pddError(fallback, err instanceof Error ? err.message : String(err));
}

const FALLBACKS: Record<PddMethodName, PddErrorCode> = {
  themesList: PDD_ERROR_CODES.PARAMS_INVALID,
  generate: PDD_ERROR_CODES.PARAMS_INVALID,
  validateMap: PDD_ERROR_CODES.DUNGEON_INVALID,
  dungeonsSave: PDD_ERROR_CODES.DUNGEON_INVALID,
  dungeonsList: PDD_ERROR_CODES.DUNGEON_INVALID,
  dungeonsGet: PDD_ERROR_CODES.DUNGEON_NOT_FOUND,
  dungeonsDelete: PDD_ERROR_CODES.DUNGEON_NOT_FOUND,
  placementsAdd: PDD_ERROR_CODES.DUNGEON_INVALID,
  placementsRemove: PDD_ERROR_CODES.DUNGEON_INVALID,
  placementsMove: PDD_ERROR_CODES.DUNGEON_INVALID,
  exportJson: PDD_ERROR_CODES.DUNGEON_NOT_FOUND,
  exportMarkdown: PDD_ERROR_CODES.DUNGEON_NOT_FOUND,
  importJson: PDD_ERROR_CODES.IMPORT_INVALID,
};

export function createHandlers(service: DungeonService): Record<string, Handler> {
  const byMethod: Record<PddMethodName, Handler> = {
    themesList: async () => service.themesList(),
    generate: async (...args) => {
      const [params] = generateSchema.parse(args);
      return service.generate(params);
    },
    validateMap: async (...args) => {
      const [map] = validateMapSchema.parse(args);
      return service.validateMap(map);
    },
    dungeonsSave: async (...args) => {
      const [input] = dungeonsSaveSchema.parse(args);
      return service.dungeonsSave(input);
    },
    dungeonsList: async () => service.dungeonsList(),
    dungeonsGet: async (...args) => {
      const [id] = dungeonsGetSchema.parse(args);
      return service.dungeonsGet(id);
    },
    dungeonsDelete: async (...args) => {
      const [id] = dungeonsDeleteSchema.parse(args);
      return service.dungeonsDelete(id);
    },
    placementsAdd: async (...args) => {
      const [dungeonId, op] = placementsAddSchema.parse(args);
      return service.placementsAdd(dungeonId, op);
    },
    placementsRemove: async (...args) => {
      const [dungeonId, placementId] = placementsRemoveSchema.parse(args);
      return service.placementsRemove(dungeonId, placementId);
    },
    placementsMove: async (...args) => {
      const [dungeonId, placementId, toRoomId] = placementsMoveSchema.parse(args);
      return service.placementsMove(dungeonId, placementId, toRoomId);
    },
    exportJson: async (...args) => {
      const [dungeonId] = exportJsonSchema.parse(args);
      return service.exportJson(dungeonId);
    },
    exportMarkdown: async (...args) => {
      const [dungeonId] = exportMarkdownSchema.parse(args);
      return service.exportMarkdown(dungeonId);
    },
    importJson: async (...args) => {
      const [text] = importJsonSchema.parse(args);
      return service.importJson(text);
    },
  };

  const table: Record<string, Handler> = {};
  for (const [method, channel] of Object.entries(PDD_CHANNELS) as Array<
    [PddMethodName, string]
  >) {
    const handler = byMethod[method];
    const fallback = FALLBACKS[method];
    table[channel] = async (...args: unknown[]) => {
      try {
        return await handler(...args);
      } catch (err) {
        throw toPlain(err, fallback);
      }
    };
  }
  return table;
}

export function registerIpcHandlers(ipcMain: IpcMainLike, service: DungeonService): void {
  const table = createHandlers(service);
  for (const [channel, handler] of Object.entries(table)) {
    ipcMain.handle(channel, async (_event, ...args) => handler(...args));
  }
}
