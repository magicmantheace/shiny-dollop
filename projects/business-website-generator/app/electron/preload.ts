/**
 * Preload script (context-isolated): exposes a flat `window.bwg` API.
 *
 * The method list here must match shared/types.ts `BwgApi` exactly.
 * No validation happens here — arguments are forwarded to main, which
 * validates every call with zod.
 */
import { contextBridge, ipcRenderer } from 'electron';
import type { BwgApi } from '../shared/types.js';

/**
 * IPC channel names, inlined on purpose: the window runs with
 * `sandbox: true`, and a sandboxed preload may only require `electron`
 * (plus a few Node builtins) — it cannot require the main-process module
 * that owns the canonical map (`electron/main/ipc.ts` CHANNELS). Keep
 * these literals in sync with that map; tests/backend/preload.test.ts
 * pins the forwarded channel strings and tests/backend/desktop-launch
 * pins that this file has no runtime imports beyond `electron`.
 */
const CHANNELS = {
  sitesList: 'bwg:sites:list',
  sitesCreate: 'bwg:sites:create',
  sitesGet: 'bwg:sites:get',
  sitesUpdateProfile: 'bwg:sites:updateProfile',
  sitesDelete: 'bwg:sites:delete',
  sitesSetTheme: 'bwg:sites:setTheme',
  themesList: 'bwg:themes:list',
  previewRender: 'bwg:preview:render',
  exportValidate: 'bwg:export:validate',
  exportRun: 'bwg:export:run',
  dialogPickDirectory: 'bwg:dialog:pickDirectory',
} as const;

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
