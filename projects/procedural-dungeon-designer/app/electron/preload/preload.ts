// Sandboxed preload: self-contained at runtime.
// Only the Electron bridge API is imported at runtime; the PddApi import
// is type-only and erased at compile time. Channel strings are literals
// in this file (mirroring electron/main/channels.ts) because a sandboxed
// preload cannot load project modules at runtime.
import { contextBridge, ipcRenderer } from 'electron';
import type { PddApi } from '../../shared/types.js';

const pdd: PddApi = {
  themesList: () => ipcRenderer.invoke('pdd:themes-list'),
  generate: (params) => ipcRenderer.invoke('pdd:generate', params),
  validateMap: (map) => ipcRenderer.invoke('pdd:validate-map', map),
  dungeonsSave: (input) => ipcRenderer.invoke('pdd:dungeons-save', input),
  dungeonsList: () => ipcRenderer.invoke('pdd:dungeons-list'),
  dungeonsGet: (id) => ipcRenderer.invoke('pdd:dungeons-get', id),
  dungeonsDelete: (id) => ipcRenderer.invoke('pdd:dungeons-delete', id),
  placementsAdd: (dungeonId, op) => ipcRenderer.invoke('pdd:placements-add', dungeonId, op),
  placementsRemove: (dungeonId, placementId) =>
    ipcRenderer.invoke('pdd:placements-remove', dungeonId, placementId),
  placementsMove: (dungeonId, placementId, toRoomId) =>
    ipcRenderer.invoke('pdd:placements-move', dungeonId, placementId, toRoomId),
  exportJson: (dungeonId) => ipcRenderer.invoke('pdd:export-json', dungeonId),
  exportMarkdown: (dungeonId) => ipcRenderer.invoke('pdd:export-markdown', dungeonId),
  importJson: (text) => ipcRenderer.invoke('pdd:import-json', text),
};

contextBridge.exposeInMainWorld('pdd', pdd);
