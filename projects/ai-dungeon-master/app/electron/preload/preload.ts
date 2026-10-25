// Sandboxed preload: self-contained at runtime.
// Only the Electron bridge API is imported at runtime; the AidmApi import
// is type-only and erased at compile time. Channel strings are literals
// in this file (mirroring electron/main/channels.ts) because a sandboxed
// preload cannot load project modules at runtime.
import { contextBridge, ipcRenderer } from 'electron';
import type { AidmApi } from '../../shared/types.js';

const aidm: AidmApi = {
  campaignsList: () => ipcRenderer.invoke('aidm:campaigns-list'),
  campaignsCreate: (input) => ipcRenderer.invoke('aidm:campaigns-create', input),
  campaignsGet: (id) => ipcRenderer.invoke('aidm:campaigns-get', id),
  campaignsDelete: (id) => ipcRenderer.invoke('aidm:campaigns-delete', id),
  sessionsList: (campaignId) => ipcRenderer.invoke('aidm:sessions-list', campaignId),
  sessionsCreate: (campaignId, input) => ipcRenderer.invoke('aidm:sessions-create', campaignId, input),
  sessionsUpdateNotes: (sessionId, notes) => ipcRenderer.invoke('aidm:sessions-update-notes', sessionId, notes),
  sessionsEnd: (sessionId) => ipcRenderer.invoke('aidm:sessions-end', sessionId),
  charactersList: (campaignId) => ipcRenderer.invoke('aidm:characters-list', campaignId),
  charactersCreate: (campaignId, input) => ipcRenderer.invoke('aidm:characters-create', campaignId, input),
  charactersUpdate: (id, patch) => ipcRenderer.invoke('aidm:characters-update', id, patch),
  charactersDelete: (id) => ipcRenderer.invoke('aidm:characters-delete', id),
  diceRoll: (campaignId, req) => ipcRenderer.invoke('aidm:dice-roll', campaignId, req),
  checkRoll: (campaignId, req) => ipcRenderer.invoke('aidm:check-roll', campaignId, req),
  logList: (campaignId, sessionId) => ipcRenderer.invoke('aidm:log-list', campaignId, sessionId),
  logAddNote: (campaignId, text, sessionId) => ipcRenderer.invoke('aidm:log-add-note', campaignId, text, sessionId),
  encountersStart: (campaignId, req) => ipcRenderer.invoke('aidm:encounters-start', campaignId, req),
  encountersGetActive: (campaignId) => ipcRenderer.invoke('aidm:encounters-get-active', campaignId),
  encountersAdvanceTurn: (encounterId) => ipcRenderer.invoke('aidm:encounters-advance-turn', encounterId),
  encountersApplyDamage: (encounterId, req) => ipcRenderer.invoke('aidm:encounters-apply-damage', encounterId, req),
  encountersApplyHeal: (encounterId, req) => ipcRenderer.invoke('aidm:encounters-apply-heal', encounterId, req),
  encountersEnd: (encounterId) => ipcRenderer.invoke('aidm:encounters-end', encounterId),
  memoryList: (campaignId) => ipcRenderer.invoke('aidm:memory-list', campaignId),
  memoryCreate: (campaignId, input) => ipcRenderer.invoke('aidm:memory-create', campaignId, input),
  memoryUpdate: (id, patch) => ipcRenderer.invoke('aidm:memory-update', id, patch),
  memoryDelete: (id) => ipcRenderer.invoke('aidm:memory-delete', id),
  memorySearch: (campaignId, query) => ipcRenderer.invoke('aidm:memory-search', campaignId, query),
  narrate: (logEntryId) => ipcRenderer.invoke('aidm:narrate', logEntryId),
  settingsGet: () => ipcRenderer.invoke('aidm:settings-get'),
  settingsUpdate: (settings) => ipcRenderer.invoke('aidm:settings-update', settings),
  exportCampaign: (campaignId) => ipcRenderer.invoke('aidm:export-campaign', campaignId),
  importCampaign: (text) => ipcRenderer.invoke('aidm:import-campaign', text),
  importWorldbuilding: (campaignId, text) => ipcRenderer.invoke('aidm:import-worldbuilding', campaignId, text),
  importDungeonManifest: (campaignId, text) => ipcRenderer.invoke('aidm:import-dungeon-manifest', campaignId, text),
};

contextBridge.exposeInMainWorld('aidm', aidm);
