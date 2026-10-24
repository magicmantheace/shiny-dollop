import { contextBridge, ipcRenderer } from 'electron';
import type { LaccApi, LaccMethodName } from '../../shared/types.js';

// Sandboxed preload: Electron's sandboxed renderer only allows requiring
// `electron` (and a few built-ins) — it cannot require local modules such as
// `./channels.js` or `../../shared/types.js`. The channel map is therefore
// inlined here so the compiled preload.js is a single self-contained script
// whose only runtime require is `electron`. This map MUST stay identical to
// LACC_IPC_CHANNELS in shared/types.ts (guarded by tests/backend/preload.test.ts);
// main-process code continues to import the canonical map via channels.ts.
const LACC_METHOD_CHANNELS: Record<LaccMethodName, string> = {
  configGet: 'lacc:config-get',
  configSave: 'lacc:config-save',
  endpointHealth: 'lacc:endpoint-health',
  endpointModels: 'lacc:endpoint-models',
  tasksSubmit: 'lacc:tasks-submit',
  tasksList: 'lacc:tasks-list',
  tasksGet: 'lacc:tasks-get',
  tasksCancel: 'lacc:tasks-cancel',
  tasksLogs: 'lacc:tasks-logs',
  proposalsList: 'lacc:proposals-list',
  proposalsGet: 'lacc:proposals-get',
  proposalsApprove: 'lacc:proposals-approve',
  proposalsReject: 'lacc:proposals-reject',
  auditList: 'lacc:audit-list',
  resourcesSnapshot: 'lacc:resources-snapshot',
  pickDirectory: 'lacc:pick-directory',
};

const lacc: LaccApi = {
  configGet: () => ipcRenderer.invoke(LACC_METHOD_CHANNELS.configGet),
  configSave: (config) => ipcRenderer.invoke(LACC_METHOD_CHANNELS.configSave, config),
  endpointHealth: () => ipcRenderer.invoke(LACC_METHOD_CHANNELS.endpointHealth),
  endpointModels: () => ipcRenderer.invoke(LACC_METHOD_CHANNELS.endpointModels),
  tasksSubmit: (input) => ipcRenderer.invoke(LACC_METHOD_CHANNELS.tasksSubmit, input),
  tasksList: () => ipcRenderer.invoke(LACC_METHOD_CHANNELS.tasksList),
  tasksGet: (id) => ipcRenderer.invoke(LACC_METHOD_CHANNELS.tasksGet, id),
  tasksCancel: (id) => ipcRenderer.invoke(LACC_METHOD_CHANNELS.tasksCancel, id),
  tasksLogs: (id) => ipcRenderer.invoke(LACC_METHOD_CHANNELS.tasksLogs, id),
  proposalsList: () => ipcRenderer.invoke(LACC_METHOD_CHANNELS.proposalsList),
  proposalsGet: (id) => ipcRenderer.invoke(LACC_METHOD_CHANNELS.proposalsGet, id),
  proposalsApprove: (id) => ipcRenderer.invoke(LACC_METHOD_CHANNELS.proposalsApprove, id),
  proposalsReject: (id) => ipcRenderer.invoke(LACC_METHOD_CHANNELS.proposalsReject, id),
  auditList: (limit) => ipcRenderer.invoke(LACC_METHOD_CHANNELS.auditList, limit),
  resourcesSnapshot: () => ipcRenderer.invoke(LACC_METHOD_CHANNELS.resourcesSnapshot),
  pickDirectory: () => ipcRenderer.invoke(LACC_METHOD_CHANNELS.pickDirectory),
};
contextBridge.exposeInMainWorld('lacc', lacc);
