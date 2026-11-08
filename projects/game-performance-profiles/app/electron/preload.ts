/**
 * Preload script — exposes a typed, minimal `window.gpp` API to the renderer.
 * No direct Node/Electron access leaks into the renderer; every call goes
 * through a validated IPC channel, and activation progress arrives as events.
 */

import { contextBridge, ipcRenderer } from 'electron';
import {
  ACTIVATION_PROGRESS_EVENT,
  IPC_CHANNELS,
  type ActivationProgress,
  type GppApi,
} from '../shared/gpp-types.js';

const gpp: GppApi = {
  getCapabilities: () => ipcRenderer.invoke(IPC_CHANNELS.capabilities),
  listProfiles: () => ipcRenderer.invoke(IPC_CHANNELS.profilesList),
  createProfile: (input) => ipcRenderer.invoke(IPC_CHANNELS.profilesCreate, input),
  updateProfile: (input) => ipcRenderer.invoke(IPC_CHANNELS.profilesUpdate, input),
  deleteProfile: (input) => ipcRenderer.invoke(IPC_CHANNELS.profilesDelete, input),
  previewProfile: (input) => ipcRenderer.invoke(IPC_CHANNELS.profilesPreview, input),
  activateProfile: (input) => ipcRenderer.invoke(IPC_CHANNELS.profilesActivate, input),
  rollbackProfile: (input) => ipcRenderer.invoke(IPC_CHANNELS.profilesRollback, input),
  restoreAll: () => ipcRenderer.invoke(IPC_CHANNELS.restoreAll),
  listJournal: () => ipcRenderer.invoke(IPC_CHANNELS.journalList),
  takeSnapshot: (input) => ipcRenderer.invoke(IPC_CHANNELS.snapshotsTake, input),
  listSnapshots: () => ipcRenderer.invoke(IPC_CHANNELS.snapshotsList),
  onActivationProgress: (cb: (p: ActivationProgress) => void) => {
    const listener = (_event: unknown, payload: ActivationProgress) => cb(payload);
    ipcRenderer.on(ACTIVATION_PROGRESS_EVENT, listener);
    return () => ipcRenderer.removeListener(ACTIVATION_PROGRESS_EVENT, listener);
  },
};

contextBridge.exposeInMainWorld('gpp', gpp);
