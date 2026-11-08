/**
 * Preload script. Runs in a sandboxed context with access to ipcRenderer.
 * Exposes ONLY the narrow typed `window.inv` API — no raw ipcRenderer,
 * no Node APIs, no arbitrary channel access.
 */
import { contextBridge, ipcRenderer } from 'electron';
import { InvChannels } from '../shared/ipc-channels';
import type { InvApi } from '../shared/api-types';
import type { IpcResult } from '../shared/types';

function invoke<T>(channel: string, payload?: unknown): Promise<T> {
  return ipcRenderer.invoke(channel, payload).then((result: unknown) => {
    const envelope = result as IpcResult<T>;
    if (!envelope || typeof envelope !== 'object' || !('ok' in envelope)) {
      throw new Error('Malformed IPC response.');
    }
    if (!envelope.ok) {
      throw new Error(envelope.error.message);
    }
    return envelope.data;
  });
}

const api: InvApi = {
  items: {
    list: (filter) => invoke(InvChannels.itemsList, filter ?? {}),
    get: (id) => invoke(InvChannels.itemsGet, { id }),
    create: (input) => invoke(InvChannels.itemsCreate, input),
    update: (id, input) => invoke(InvChannels.itemsUpdate, { id, input }),
    remove: (id) => invoke(InvChannels.itemsDelete, { id }),
  },
  categories: {
    list: () => invoke(InvChannels.categoriesList, {}),
  },
  attachments: {
    add: (itemId, input) => invoke(InvChannels.attachmentsAdd, { itemId, input }),
    get: (id) => invoke(InvChannels.attachmentsGet, { id }),
    remove: (id) => invoke(InvChannels.attachmentsDelete, { id }),
  },
  maintenance: {
    list: (itemId) => invoke(InvChannels.maintenanceList, { itemId }),
    add: (itemId, input) => invoke(InvChannels.maintenanceAdd, { itemId, input }),
    remove: (id) => invoke(InvChannels.maintenanceDelete, { id }),
  },
  warranties: {
    expiring: (withinDays) => invoke(InvChannels.warrantiesExpiring, { withinDays }),
  },
  backup: {
    export: () => invoke(InvChannels.backupExport, {}),
    import: () => invoke(InvChannels.backupImport, {}),
  },
};

contextBridge.exposeInMainWorld('inv', api);
