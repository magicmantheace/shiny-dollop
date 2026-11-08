// IPC channel names for the AI Dungeon Master.
// The channel strings are the wire contract between preload and main;
// the sandboxed preload repeats them as literals (it cannot import this
// module at runtime), and a backend test keeps the two in step via the
// method-name mapping below.
import type { AidmApi } from '../../shared/types.js';

export const AIDM_CHANNELS = {
  campaignsList: 'aidm:campaigns-list',
  campaignsCreate: 'aidm:campaigns-create',
  campaignsGet: 'aidm:campaigns-get',
  campaignsDelete: 'aidm:campaigns-delete',
  sessionsList: 'aidm:sessions-list',
  sessionsCreate: 'aidm:sessions-create',
  sessionsUpdateNotes: 'aidm:sessions-update-notes',
  sessionsEnd: 'aidm:sessions-end',
  charactersList: 'aidm:characters-list',
  charactersCreate: 'aidm:characters-create',
  charactersUpdate: 'aidm:characters-update',
  charactersDelete: 'aidm:characters-delete',
  diceRoll: 'aidm:dice-roll',
  checkRoll: 'aidm:check-roll',
  logList: 'aidm:log-list',
  logAddNote: 'aidm:log-add-note',
  encountersStart: 'aidm:encounters-start',
  encountersGetActive: 'aidm:encounters-get-active',
  encountersAdvanceTurn: 'aidm:encounters-advance-turn',
  encountersApplyDamage: 'aidm:encounters-apply-damage',
  encountersApplyHeal: 'aidm:encounters-apply-heal',
  encountersEnd: 'aidm:encounters-end',
  memoryList: 'aidm:memory-list',
  memoryCreate: 'aidm:memory-create',
  memoryUpdate: 'aidm:memory-update',
  memoryDelete: 'aidm:memory-delete',
  memorySearch: 'aidm:memory-search',
  narrate: 'aidm:narrate',
  settingsGet: 'aidm:settings-get',
  settingsUpdate: 'aidm:settings-update',
  exportCampaign: 'aidm:export-campaign',
  importCampaign: 'aidm:import-campaign',
  importWorldbuilding: 'aidm:import-worldbuilding',
  importDungeonManifest: 'aidm:import-dungeon-manifest',
} as const satisfies Record<keyof AidmApi, string>;

export type AidmMethodName = keyof typeof AIDM_CHANNELS;
