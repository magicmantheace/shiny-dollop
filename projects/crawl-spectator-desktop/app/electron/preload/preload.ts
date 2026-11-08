// Sandboxed preload. SELF-CONTAINED ON PURPOSE: Electron's sandboxed
// preload loader cannot require() relative shared modules (a runtime
// require of ../../shared/* here previously broke a sibling project), so
// this file uses ONLY `import type` from shared code (erased at compile
// time) and literal channel strings. The literal values must match
// SPECTATOR_IPC_CHANNELS in shared/types.ts — a backend regression test
// (tests/backend/preload.test.ts) asserts they stay in lockstep, and that
// the compiled preload requires nothing but 'electron'.

import { contextBridge, ipcRenderer } from 'electron';
import type { IpcRendererEvent } from 'electron';
import type { ConnectionStatus, FeedSnapshot, SpectatorApi } from '../../shared/types.js';

const spectator: SpectatorApi = {
  getStatus: () => ipcRenderer.invoke('spectator:get-status'),
  connectLive: (baseUrl) => ipcRenderer.invoke('spectator:connect-live', baseUrl),
  connectDemo: () => ipcRenderer.invoke('spectator:connect-demo'),
  disconnect: () => ipcRenderer.invoke('spectator:disconnect'),
  getDescent: () => ipcRenderer.invoke('spectator:get-descent'),
  listDescenders: () => ipcRenderer.invoke('spectator:list-descenders'),
  getProfile: (descenderId) => ipcRenderer.invoke('spectator:get-profile', descenderId),
  getHistory: (descenderId, limit) => ipcRenderer.invoke('spectator:get-history', descenderId, limit),
  search: (query) => ipcRenderer.invoke('spectator:search', query),
  listParties: () => ipcRenderer.invoke('spectator:list-parties'),
  getFeed: () => ipcRenderer.invoke('spectator:get-feed'),
  getReplay: (query) => ipcRenderer.invoke('spectator:get-replay', query),
  getHighlights: () => ipcRenderer.invoke('spectator:get-highlights'),
  getPrefs: () => ipcRenderer.invoke('spectator:get-prefs'),
  follow: (descenderId) => ipcRenderer.invoke('spectator:follow', descenderId),
  unfollow: (descenderId) => ipcRenderer.invoke('spectator:unfollow', descenderId),
  exportPrefs: () => ipcRenderer.invoke('spectator:export-prefs'),
  importPrefs: (envelope) => ipcRenderer.invoke('spectator:import-prefs', envelope),
  onStatusChanged: (listener) => {
    const wrapped = (_event: IpcRendererEvent, status: ConnectionStatus): void => listener(status);
    ipcRenderer.on('spectator:status-changed', wrapped);
    return () => ipcRenderer.removeListener('spectator:status-changed', wrapped);
  },
  onFeedChanged: (listener) => {
    const wrapped = (_event: IpcRendererEvent, snapshot: FeedSnapshot): void => listener(snapshot);
    ipcRenderer.on('spectator:feed-changed', wrapped);
    return () => ipcRenderer.removeListener('spectator:feed-changed', wrapped);
  },
};

contextBridge.exposeInMainWorld('spectator', spectator);
