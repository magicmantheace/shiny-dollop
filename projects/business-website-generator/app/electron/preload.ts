/**
 * Preload script (context-isolated): exposes a flat `window.bwg` API.
 *
 * The method list here must match shared/types.ts `BwgApi` exactly.
 * No validation happens here — arguments are forwarded to main, which
 * validates every call with zod.
 */
import { contextBridge, ipcRenderer } from 'electron';
import type { BwgApi } from '../shared/types.js';
import { CHANNELS } from './main/ipc.js';

function invoke<T>(channel: string, ...args: unknown[]): Promise<T> {
  return ipcRenderer.invoke(channel, ...args);
}

const api: BwgApi = {
  sites: {
    list: () => invoke(CHANNELS.sitesList),
    create: (input) => invoke(CHANNELS.sitesCreate, input),
    get: (id) => invoke(CHANNELS.sitesGet, id),
    updateProfile: (id, patch) => invoke(CHANNELS.sitesUpdateProfile, id, patch),
    delete: (id) => invoke(CHANNELS.sitesDelete, id),
    setTheme: (id, themeId) => invoke(CHANNELS.sitesSetTheme, id, themeId),
  },
  themes: {
    list: () => invoke(CHANNELS.themesList),
  },
  preview: {
    render: (id) => invoke(CHANNELS.previewRender, id),
  },
  export: {
    validate: (id) => invoke(CHANNELS.exportValidate, id),
    run: (id, destDir) => invoke(CHANNELS.exportRun, id, destDir),
  },
  dialog: {
    pickDirectory: () => invoke(CHANNELS.dialogPickDirectory),
  },
};

contextBridge.exposeInMainWorld('bwg', api);
