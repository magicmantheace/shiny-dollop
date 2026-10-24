import { contextBridge, ipcRenderer } from 'electron';
import type { LaccApi } from '../../shared/types.js';
import { LACC_METHOD_CHANNELS } from './channels.js';

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
