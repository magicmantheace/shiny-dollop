// Preload: exposes a flat `window.dab` matching DabApi exactly.
// The renderer never gets raw ipcRenderer — only these 17 methods.
//
// SANDBOX NOTE: the BrowserWindow leaves Electron's renderer sandbox
// enabled, and a sandboxed preload's restricted `require` can only load
// `electron` (and a small set of built-ins) — it CANNOT load local files.
// This script must therefore be fully self-contained: the channel map is
// inlined below instead of imported from `./channels.js`, and the only
// other import is a type-only one (erased at compile time). The main
// process keeps using `electron/preload/channels.ts` for registration;
// the two maps are pinned to each other by a backend test that asserts
// this file carries exactly the DAB_IPC_CHANNELS values.
import { contextBridge, ipcRenderer } from 'electron';
import type { DabApi, DabIpcChannel } from '../../shared/types.js';

/** Inlined copy of DAB_METHOD_CHANNELS (see channels.ts) — do not import it here. */
const DAB_METHOD_CHANNELS: Record<keyof DabApi, DabIpcChannel> = {
  workflowsList: 'dab:workflows:list',
  workflowsCreate: 'dab:workflows:create',
  workflowsGet: 'dab:workflows:get',
  workflowsUpdate: 'dab:workflows:update',
  workflowsDelete: 'dab:workflows:delete',
  workflowsExport: 'dab:workflows:export',
  workflowsImport: 'dab:workflows:import',
  scriptsList: 'dab:scripts:list',
  scriptsRegister: 'dab:scripts:register',
  scriptsUnregister: 'dab:scripts:unregister',
  runsPreview: 'dab:runs:preview',
  runsStart: 'dab:runs:start',
  runsCancel: 'dab:runs:cancel',
  runsRetry: 'dab:runs:retry',
  runsGet: 'dab:runs:get',
  runsList: 'dab:runs:list',
  pickDirectory: 'dab:dialog:pick-directory',
};

const dab: DabApi = {
  workflowsList: () => ipcRenderer.invoke(DAB_METHOD_CHANNELS.workflowsList),
  workflowsCreate: (name, sandboxRoot) =>
    ipcRenderer.invoke(DAB_METHOD_CHANNELS.workflowsCreate, name, sandboxRoot),
  workflowsGet: (id) => ipcRenderer.invoke(DAB_METHOD_CHANNELS.workflowsGet, id),
  workflowsUpdate: (id, patch) => ipcRenderer.invoke(DAB_METHOD_CHANNELS.workflowsUpdate, id, patch),
  workflowsDelete: (id) => ipcRenderer.invoke(DAB_METHOD_CHANNELS.workflowsDelete, id),
  workflowsExport: (id) => ipcRenderer.invoke(DAB_METHOD_CHANNELS.workflowsExport, id),
  workflowsImport: (json) => ipcRenderer.invoke(DAB_METHOD_CHANNELS.workflowsImport, json),
  scriptsList: () => ipcRenderer.invoke(DAB_METHOD_CHANNELS.scriptsList),
  scriptsRegister: (name, filePath) =>
    ipcRenderer.invoke(DAB_METHOD_CHANNELS.scriptsRegister, name, filePath),
  scriptsUnregister: (id) => ipcRenderer.invoke(DAB_METHOD_CHANNELS.scriptsUnregister, id),
  runsPreview: (workflowId) => ipcRenderer.invoke(DAB_METHOD_CHANNELS.runsPreview, workflowId),
  runsStart: (workflowId, approved) =>
    ipcRenderer.invoke(DAB_METHOD_CHANNELS.runsStart, workflowId, approved),
  runsCancel: (runId) => ipcRenderer.invoke(DAB_METHOD_CHANNELS.runsCancel, runId),
  runsRetry: (runId) => ipcRenderer.invoke(DAB_METHOD_CHANNELS.runsRetry, runId),
  runsGet: (runId) => ipcRenderer.invoke(DAB_METHOD_CHANNELS.runsGet, runId),
  runsList: (workflowId) => ipcRenderer.invoke(DAB_METHOD_CHANNELS.runsList, workflowId),
  pickDirectory: () => ipcRenderer.invoke(DAB_METHOD_CHANNELS.pickDirectory),
};

contextBridge.exposeInMainWorld('dab', dab);
