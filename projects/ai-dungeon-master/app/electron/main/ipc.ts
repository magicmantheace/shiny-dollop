// IPC boundary: zod-parse the raw args array for every method, delegate
// to CampaignService, and convert every failure to a plain { code,
// message } AidmError so nothing exotic crosses the bridge.
import { ZodError } from 'zod';
import {
  AIDM_ERROR_CODES,
  isAidmError,
  aidmError,
  type AidmError,
  type AidmErrorCode,
} from '../../shared/errors.js';
import { AIDM_CHANNELS, type AidmMethodName } from './channels.js';
import * as s from './schemas.js';
import type { CampaignService } from './service.js';
import type {
  CampaignInput,
  CharacterInput,
  CharacterPatch,
  CheckRequest,
  EncounterStartRequest,
  HpChangeRequest,
  MemoryInput,
  MemoryPatch,
  NarrationSettings,
  RollRequest,
} from '../../shared/types.js';

export interface IpcMainLike {
  handle(channel: string, listener: (event: unknown, ...args: unknown[]) => Promise<unknown>): void;
}

type Handler = (...args: unknown[]) => Promise<unknown>;

function toPlain(err: unknown, fallback: AidmErrorCode): AidmError {
  if (isAidmError(err)) return { code: err.code, message: err.message };
  if (err instanceof ZodError) {
    return aidmError(
      AIDM_ERROR_CODES.INPUT_INVALID,
      `Invalid input: ${err.issues.map((i) => i.message).join('; ') || err.message}`,
    );
  }
  return aidmError(fallback, err instanceof Error ? err.message : String(err));
}

const FALLBACKS: Record<AidmMethodName, AidmErrorCode> = {
  campaignsList: AIDM_ERROR_CODES.INPUT_INVALID,
  campaignsCreate: AIDM_ERROR_CODES.INPUT_INVALID,
  campaignsGet: AIDM_ERROR_CODES.CAMPAIGN_NOT_FOUND,
  campaignsDelete: AIDM_ERROR_CODES.CAMPAIGN_NOT_FOUND,
  sessionsList: AIDM_ERROR_CODES.CAMPAIGN_NOT_FOUND,
  sessionsCreate: AIDM_ERROR_CODES.INPUT_INVALID,
  sessionsUpdateNotes: AIDM_ERROR_CODES.SESSION_NOT_FOUND,
  sessionsEnd: AIDM_ERROR_CODES.SESSION_NOT_FOUND,
  charactersList: AIDM_ERROR_CODES.CAMPAIGN_NOT_FOUND,
  charactersCreate: AIDM_ERROR_CODES.INPUT_INVALID,
  charactersUpdate: AIDM_ERROR_CODES.CHARACTER_NOT_FOUND,
  charactersDelete: AIDM_ERROR_CODES.CHARACTER_NOT_FOUND,
  diceRoll: AIDM_ERROR_CODES.DICE_NOTATION_INVALID,
  checkRoll: AIDM_ERROR_CODES.INPUT_INVALID,
  logList: AIDM_ERROR_CODES.CAMPAIGN_NOT_FOUND,
  logAddNote: AIDM_ERROR_CODES.INPUT_INVALID,
  encountersStart: AIDM_ERROR_CODES.INPUT_INVALID,
  encountersGetActive: AIDM_ERROR_CODES.CAMPAIGN_NOT_FOUND,
  encountersAdvanceTurn: AIDM_ERROR_CODES.ENCOUNTER_NOT_FOUND,
  encountersApplyDamage: AIDM_ERROR_CODES.ENCOUNTER_NOT_FOUND,
  encountersApplyHeal: AIDM_ERROR_CODES.ENCOUNTER_NOT_FOUND,
  encountersEnd: AIDM_ERROR_CODES.ENCOUNTER_NOT_FOUND,
  memoryList: AIDM_ERROR_CODES.CAMPAIGN_NOT_FOUND,
  memoryCreate: AIDM_ERROR_CODES.INPUT_INVALID,
  memoryUpdate: AIDM_ERROR_CODES.MEMORY_NOT_FOUND,
  memoryDelete: AIDM_ERROR_CODES.MEMORY_NOT_FOUND,
  memorySearch: AIDM_ERROR_CODES.CAMPAIGN_NOT_FOUND,
  narrate: AIDM_ERROR_CODES.LOG_ENTRY_NOT_FOUND,
  settingsGet: AIDM_ERROR_CODES.INPUT_INVALID,
  settingsUpdate: AIDM_ERROR_CODES.INPUT_INVALID,
  exportCampaign: AIDM_ERROR_CODES.CAMPAIGN_NOT_FOUND,
  importCampaign: AIDM_ERROR_CODES.IMPORT_INVALID,
  importWorldbuilding: AIDM_ERROR_CODES.IMPORT_INVALID,
  importDungeonManifest: AIDM_ERROR_CODES.IMPORT_INVALID,
};

export function createHandlers(service: CampaignService): Record<string, Handler> {
  const byMethod: Record<AidmMethodName, Handler> = {
    campaignsList: async () => service.campaignsList(),
    campaignsCreate: async (...a) => service.campaignsCreate(s.campaignsCreateSchema.parse(a)[0] as CampaignInput),
    campaignsGet: async (...a) => service.campaignsGet(s.campaignsGetSchema.parse(a)[0]),
    campaignsDelete: async (...a) => service.campaignsDelete(s.campaignsDeleteSchema.parse(a)[0]),
    sessionsList: async (...a) => service.sessionsList(s.sessionsListSchema.parse(a)[0]),
    sessionsCreate: async (...a) => {
      const [id, input] = s.sessionsCreateSchema.parse(a);
      return service.sessionsCreate(id, input);
    },
    sessionsUpdateNotes: async (...a) => {
      const [id, notes] = s.sessionsUpdateNotesSchema.parse(a);
      return service.sessionsUpdateNotes(id, notes);
    },
    sessionsEnd: async (...a) => service.sessionsEnd(s.sessionsEndSchema.parse(a)[0]),
    charactersList: async (...a) => service.charactersList(s.charactersListSchema.parse(a)[0]),
    charactersCreate: async (...a) => {
      const [id, input] = s.charactersCreateSchema.parse(a);
      return service.charactersCreate(id, input as CharacterInput);
    },
    charactersUpdate: async (...a) => {
      const [id, patch] = s.charactersUpdateSchema.parse(a);
      return service.charactersUpdate(id, patch as CharacterPatch);
    },
    charactersDelete: async (...a) => service.charactersDelete(s.charactersDeleteSchema.parse(a)[0]),
    diceRoll: async (...a) => {
      const [id, req] = s.diceRollSchema.parse(a);
      return service.diceRoll(id, req as RollRequest);
    },
    checkRoll: async (...a) => {
      const [id, req] = s.checkRollSchema.parse(a);
      return service.checkRoll(id, req as CheckRequest);
    },
    logList: async (...a) => {
      const [id, sessionId] = s.logListSchema.parse(a);
      return service.logList(id, sessionId);
    },
    logAddNote: async (...a) => {
      const [id, text, sessionId] = s.logAddNoteSchema.parse(a);
      return service.logAddNote(id, text, sessionId);
    },
    encountersStart: async (...a) => {
      const [id, req] = s.encountersStartSchema.parse(a);
      return service.encountersStart(id, req as EncounterStartRequest);
    },
    encountersGetActive: async (...a) =>
      service.encountersGetActive(s.encountersGetActiveSchema.parse(a)[0]),
    encountersAdvanceTurn: async (...a) =>
      service.encountersAdvanceTurn(s.encountersAdvanceTurnSchema.parse(a)[0]),
    encountersApplyDamage: async (...a) => {
      const [id, req] = s.encountersApplyDamageSchema.parse(a);
      return service.encountersApplyDamage(id, req as HpChangeRequest);
    },
    encountersApplyHeal: async (...a) => {
      const [id, req] = s.encountersApplyHealSchema.parse(a);
      return service.encountersApplyHeal(id, req as HpChangeRequest);
    },
    encountersEnd: async (...a) => service.encountersEnd(s.encountersEndSchema.parse(a)[0]),
    memoryList: async (...a) => service.memoryList(s.memoryListSchema.parse(a)[0]),
    memoryCreate: async (...a) => {
      const [id, input] = s.memoryCreateSchema.parse(a);
      return service.memoryCreate(id, input as MemoryInput);
    },
    memoryUpdate: async (...a) => {
      const [id, patch] = s.memoryUpdateSchema.parse(a);
      return service.memoryUpdate(id, patch as MemoryPatch);
    },
    memoryDelete: async (...a) => service.memoryDelete(s.memoryDeleteSchema.parse(a)[0]),
    memorySearch: async (...a) => {
      const [id, q] = s.memorySearchSchema.parse(a);
      return service.memorySearch(id, q);
    },
    narrate: async (...a) => service.narrate(s.narrateSchema.parse(a)[0]),
    settingsGet: async () => service.settingsGet(),
    settingsUpdate: async (...a) => service.settingsUpdate(s.settingsUpdateSchema.parse(a)[0] as NarrationSettings),
    exportCampaign: async (...a) => service.exportCampaign(s.exportCampaignSchema.parse(a)[0]),
    importCampaign: async (...a) => service.importCampaign(s.importCampaignSchema.parse(a)[0]),
    importWorldbuilding: async (...a) => {
      const [id, text] = s.importWorldbuildingSchema.parse(a);
      return service.importWorldbuilding(id, text);
    },
    importDungeonManifest: async (...a) => {
      const [id, text] = s.importDungeonManifestSchema.parse(a);
      return service.importDungeonManifest(id, text);
    },
  };

  const table: Record<string, Handler> = {};
  for (const [method, channel] of Object.entries(AIDM_CHANNELS) as Array<
    [AidmMethodName, string]
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

export function registerIpcHandlers(ipcMain: IpcMainLike, service: CampaignService): void {
  const table = createHandlers(service);
  for (const [channel, handler] of Object.entries(table)) {
    ipcMain.handle(channel, async (_event, ...args) => handler(...args));
  }
}
