// Sandboxed preload: self-contained at runtime.
// Only the Electron bridge API is imported at runtime; shared imports are
// type-only and erased at compile time. Channel strings are literals in
// this file (mirroring electron/main/channels.ts) because a sandboxed
// preload cannot load project modules at runtime.
import { contextBridge, ipcRenderer } from 'electron';
import type { AidmError, AidmIpcResult } from '../../shared/errors.js';
import type { AidmApi } from '../../shared/types.js';

async function invoke<T>(channel: string, ...args: unknown[]): Promise<T> {
  const result = (await ipcRenderer.invoke(channel, ...args)) as
    | AidmIpcResult<T>
    | undefined;
  if (result?.ok === true) return result.value;
  if (result?.ok === false) throw result.error;
  const malformed: AidmError = {
    code: 'INPUT_INVALID',
    message: `Malformed IPC response from ${channel}.`,
  };
  throw malformed;
}

const aidm: AidmApi = {
  campaignsList: () => invoke('aidm:campaigns-list'),
  campaignsCreate: (input) => invoke('aidm:campaigns-create', input),
  campaignsGet: (id) => invoke('aidm:campaigns-get', id),
  campaignsDelete: (id) => invoke('aidm:campaigns-delete', id),
  sessionsList: (campaignId) => invoke('aidm:sessions-list', campaignId),
  sessionsCreate: (campaignId, input) => invoke('aidm:sessions-create', campaignId, input),
  sessionsUpdateNotes: (sessionId, notes) => invoke('aidm:sessions-update-notes', sessionId, notes),
  sessionsEnd: (sessionId) => invoke('aidm:sessions-end', sessionId),
  charactersList: (campaignId) => invoke('aidm:characters-list', campaignId),
  charactersCreate: (campaignId, input) => invoke('aidm:characters-create', campaignId, input),
  charactersUpdate: (id, patch) => invoke('aidm:characters-update', id, patch),
  charactersDelete: (id) => invoke('aidm:characters-delete', id),
  diceRoll: (campaignId, req) => invoke('aidm:dice-roll', campaignId, req),
  checkRoll: (campaignId, req) => invoke('aidm:check-roll', campaignId, req),
  logList: (campaignId, sessionId) => invoke('aidm:log-list', campaignId, sessionId),
  logAddNote: (campaignId, text, sessionId) => invoke('aidm:log-add-note', campaignId, text, sessionId),
  encountersStart: (campaignId, req) => invoke('aidm:encounters-start', campaignId, req),
  encountersGetActive: (campaignId) => invoke('aidm:encounters-get-active', campaignId),
  encountersAdvanceTurn: (encounterId) => invoke('aidm:encounters-advance-turn', encounterId),
  encountersApplyDamage: (encounterId, req) => invoke('aidm:encounters-apply-damage', encounterId, req),
  encountersApplyHeal: (encounterId, req) => invoke('aidm:encounters-apply-heal', encounterId, req),
  encountersEnd: (encounterId) => invoke('aidm:encounters-end', encounterId),
  memoryList: (campaignId) => invoke('aidm:memory-list', campaignId),
  memoryCreate: (campaignId, input) => invoke('aidm:memory-create', campaignId, input),
  memoryUpdate: (id, patch) => invoke('aidm:memory-update', id, patch),
  memoryDelete: (id) => invoke('aidm:memory-delete', id),
  memorySearch: (campaignId, query) => invoke('aidm:memory-search', campaignId, query),
  narrate: (logEntryId) => invoke('aidm:narrate', logEntryId),
  settingsGet: () => invoke('aidm:settings-get'),
  settingsUpdate: (settings) => invoke('aidm:settings-update', settings),
  exportCampaign: (campaignId) => invoke('aidm:export-campaign', campaignId),
  importCampaign: (text) => invoke('aidm:import-campaign', text),
  importWorldbuilding: (campaignId, text) => invoke('aidm:import-worldbuilding', campaignId, text),
  importDungeonManifest: (campaignId, text) => invoke('aidm:import-dungeon-manifest', campaignId, text),
};

contextBridge.exposeInMainWorld('aidm', aidm);
