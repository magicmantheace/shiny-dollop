import { contextBridge, ipcRenderer } from 'electron';

/**
 * Preload bridge — the only surface the renderer may call.
 * Every channel returns { ok: true, data } or { ok: false, error }.
 */
const api = {
  profiles: {
    list: () => ipcRenderer.invoke('profiles.list'),
    get: (id: number) => ipcRenderer.invoke('profiles.get', id),
    create: (profile: unknown) => ipcRenderer.invoke('profiles.create', profile),
    update: (id: number, profile: unknown) => ipcRenderer.invoke('profiles.update', { id, profile }),
    remove: (id: number) => ipcRenderer.invoke('profiles.delete', id),
  },
  calc: {
    run: (input: unknown) => ipcRenderer.invoke('calc.run', input),
  },
  history: {
    list: () => ipcRenderer.invoke('history.list'),
  },
  export_: {
    envelope: (profileId: number) => ipcRenderer.invoke('export.envelope', profileId),
    csv: (calculationId: number) => ipcRenderer.invoke('export.csv', { calculationId }),
  },
  import_: {
    envelope: () => ipcRenderer.invoke('import.envelope'),
  },
};

contextBridge.exposeInMainWorld('vcc', api);
export type VccApi = typeof api;
