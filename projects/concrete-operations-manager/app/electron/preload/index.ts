/**
 * Preload script. Runs in a sandboxed context with access to ipcRenderer.
 * Exposes ONLY the narrow typed concreteOps API — no raw ipcRenderer,
 * no Node APIs, no arbitrary channel access.
 */
import { contextBridge, ipcRenderer } from 'electron';
import { IpcChannels } from '../../shared/ipc-channels';
import type { ConcreteOpsApi } from '../../shared/api-types';

function invoke<T>(channel: string, payload?: unknown): Promise<T> {
  return ipcRenderer.invoke(channel, payload) as Promise<T>;
}

const api: ConcreteOpsApi = {
  customers: {
    list: () => invoke(IpcChannels.customersList, {}),
    get: (input) => invoke(IpcChannels.customersGet, input),
    add: (input) => invoke(IpcChannels.customersAdd, input),
    update: (input) => invoke(IpcChannels.customersUpdate, input),
    remove: (input) => invoke(IpcChannels.customersRemove, input),
  },
  jobs: {
    list: (input) => invoke(IpcChannels.jobsList, input ?? {}),
    get: (input) => invoke(IpcChannels.jobsGet, input),
    add: (input) => invoke(IpcChannels.jobsAdd, input),
    update: (input) => invoke(IpcChannels.jobsUpdate, input),
    remove: (input) => invoke(IpcChannels.jobsRemove, input),
  },
  pours: {
    listByJob: (input) => invoke(IpcChannels.poursListByJob, input),
    add: (input) => invoke(IpcChannels.poursAdd, input),
    update: (input) => invoke(IpcChannels.poursUpdate, input),
    setDelivered: (input) => invoke(IpcChannels.poursSetDelivered, input),
    remove: (input) => invoke(IpcChannels.poursRemove, input),
  },
  quotes: {
    listByJob: (input) => invoke(IpcChannels.quotesListByJob, input),
    get: (input) => invoke(IpcChannels.quotesGet, input),
    create: (input) => invoke(IpcChannels.quotesCreate, input),
    updateDraft: (input) => invoke(IpcChannels.quotesUpdateDraft, input),
    issue: (input) => invoke(IpcChannels.quotesIssue, input),
    revise: (input) => invoke(IpcChannels.quotesRevise, input),
    deleteDraft: (input) => invoke(IpcChannels.quotesDeleteDraft, input),
  },
  invoices: {
    list: () => invoke(IpcChannels.invoicesList, {}),
    get: (input) => invoke(IpcChannels.invoicesGet, input),
    create: (input) => invoke(IpcChannels.invoicesCreate, input),
    markPaid: (input) => invoke(IpcChannels.invoicesMarkPaid, input),
    void: (input) => invoke(IpcChannels.invoicesVoid, input),
  },
  settings: {
    get: () => invoke(IpcChannels.settingsGet, {}),
    set: (input) => invoke(IpcChannels.settingsSet, input),
  },
  taxRates: {
    list: () => invoke(IpcChannels.taxRatesList, {}),
    add: (input) => invoke(IpcChannels.taxRatesAdd, input),
    update: (input) => invoke(IpcChannels.taxRatesUpdate, input),
    remove: (input) => invoke(IpcChannels.taxRatesRemove, input),
  },
  inventory: {
    materials: () => invoke(IpcChannels.inventoryMaterials, {}),
    materialAdd: (input) => invoke(IpcChannels.inventoryMaterialAdd, input),
    receipts: (input) => invoke(IpcChannels.inventoryReceipts, input ?? {}),
    receiptAdd: (input) => invoke(IpcChannels.inventoryReceiptAdd, input),
    consumption: (input) => invoke(IpcChannels.inventoryConsumption, input ?? {}),
    consumptionAdd: (input) => invoke(IpcChannels.inventoryConsumptionAdd, input),
    stock: () => invoke(IpcChannels.inventoryStock, {}),
  },
  audit: {
    list: (input) => invoke(IpcChannels.auditList, input ?? {}),
  },
  exports: {
    csv: () => invoke(IpcChannels.exportsCsv, {}),
    invoicePdf: (input) => invoke(IpcChannels.invoicePdf, input),
  },
  backup: {
    create: () => invoke(IpcChannels.backupCreate, {}),
    restore: () => invoke(IpcChannels.backupRestore, {}),
  },
  calibration: {
    list: () => invoke(IpcChannels.calibrationList, {}),
    export: (input) => invoke(IpcChannels.calibrationExport, input),
    import: () => invoke(IpcChannels.calibrationImport, {}),
    remove: (input) => invoke(IpcChannels.calibrationRemove, input),
  },
};

contextBridge.exposeInMainWorld('concreteOps', api);

declare global {
  interface Window {
    concreteOps: ConcreteOpsApi;
  }
}
