/**
 * Preload script. Runs in a sandboxed context with access to ipcRenderer.
 * Exposes ONLY the narrow typed `window.sim` API — no raw ipcRenderer,
 * no Node APIs, no arbitrary channel access.
 */
import { contextBridge, ipcRenderer } from 'electron';
import { SimChannels } from '../shared/ipc-channels';
import type {
  ReportSaveResult,
  SimApi,
} from '../shared/api-types';
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

const api: SimApi = {
  debts: {
    list: () => invoke(SimChannels.debtsList, {}),
    upsert: (input) => invoke(SimChannels.debtsUpsert, input),
    remove: (id) => invoke(SimChannels.debtsDelete, { id }),
  },
  income: {
    list: () => invoke(SimChannels.incomeList, {}),
    upsert: (input) => invoke(SimChannels.incomeUpsert, input),
    remove: (id) => invoke(SimChannels.incomeDelete, { id }),
  },
  simulate: {
    run: (extraPaymentCents) => invoke(SimChannels.simulateRun, { extraPaymentCents }),
  },
  report: {
    save: (input): Promise<ReportSaveResult> => invoke(SimChannels.reportSave, input),
  },
};

contextBridge.exposeInMainWorld('sim', api);
