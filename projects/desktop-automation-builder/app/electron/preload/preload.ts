// Preload: exposes a flat `window.dab` matching DabApi exactly.
// The renderer never gets raw ipcRenderer — only these 17 methods.
import { contextBridge, ipcRenderer } from 'electron';
import type { DabApi } from '../../shared/types.js';
import { DAB_METHOD_CHANNELS } from './channels.js';

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
