/**
 * Preload script. Runs in a sandboxed context with access to ipcRenderer.
 * Exposes ONLY the narrow typed storageAnalyzer API — no raw ipcRenderer,
 * no Node APIs, no arbitrary channel access.
 */
import { contextBridge, ipcRenderer } from 'electron';
import { IpcChannels, StorageEvents } from '../../shared/ipc-channels';
import type { StorageAnalyzerApi, Unsubscribe } from '../../shared/api-types';
import type { ScanFinishedEvent, ScanProgressEvent } from '../../shared/types';

function invoke<T>(channel: string, payload?: unknown): Promise<T> {
  return ipcRenderer.invoke(channel, payload) as Promise<T>;
}

function onEvent<T>(eventName: string, listener: (event: T) => void): Unsubscribe {
  const wrapped = (_event: unknown, data: T): void => {
    listener(data);
  };
  ipcRenderer.on(eventName, wrapped as (...args: unknown[]) => void);
  return () => {
    ipcRenderer.removeListener(eventName, wrapped as (...args: unknown[]) => void);
  };
}

const api: StorageAnalyzerApi = {
  dialog: {
    chooseDirectory: () => invoke(IpcChannels.dialogChooseDirectory, {}),
  },
  scan: {
    start: (input) => invoke(IpcChannels.scanStart, input),
    cancel: (input) => invoke(IpcChannels.scanCancel, input),
    status: (input) => invoke(IpcChannels.scanStatus, input),
    list: () => invoke(IpcChannels.scanList, {}),
  },
  results: {
    summary: (input) => invoke(IpcChannels.resultsSummary, input),
    duplicates: (input) => invoke(IpcChannels.resultsDuplicates, input),
    search: (input) => invoke(IpcChannels.resultsSearch, input),
  },
  export: {
    report: (input) => invoke(IpcChannels.exportReport, input),
  },
  onProgress: (listener: (event: ScanProgressEvent) => void) =>
    onEvent<ScanProgressEvent>(StorageEvents.progress, listener),
  onFinished: (listener: (event: ScanFinishedEvent) => void) =>
    onEvent<ScanFinishedEvent>(StorageEvents.finished, listener),
};

contextBridge.exposeInMainWorld('storageAnalyzer', api);

declare global {
  interface Window {
    storageAnalyzer: StorageAnalyzerApi;
  }
}
