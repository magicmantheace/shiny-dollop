/**
 * Preload script. Sandboxed: exposes ONLY the narrow typed `dtf` API.
 * No raw ipcRenderer, no Node APIs, no arbitrary channel access.
 */
import { contextBridge, ipcRenderer } from 'electron';
import { IpcChannels } from '../../shared/ipc-channels';
import type { DtfApi } from '../../shared/types';

function invoke<T>(channel: string, payload?: unknown): Promise<T> {
  return ipcRenderer.invoke(channel, payload) as Promise<T>;
}

const api: DtfApi = {
  templates: {
    list: () => invoke(IpcChannels.templatesList, {}),
    get: (input) => invoke(IpcChannels.templatesGet, input),
    import: (input) => invoke(IpcChannels.templatesImport, input),
  },
  documents: {
    list: () => invoke(IpcChannels.documentsList, {}),
    create: (input) => invoke(IpcChannels.documentsCreate, input),
    get: (input) => invoke(IpcChannels.documentsGet, input),
    updateField: (input) => invoke(IpcChannels.documentsUpdateField, input),
    updateTokens: (input) => invoke(IpcChannels.documentsUpdateTokens, input),
    delete: (input) => invoke(IpcChannels.documentsDelete, input),
  },
  export: {
    generate: (input) => invoke(IpcChannels.exportGenerate, input),
    save: (input) => invoke(IpcChannels.exportSave, input),
  },
};

contextBridge.exposeInMainWorld('dtf', api);

declare global {
  interface Window {
    dtf: DtfApi;
  }
}
