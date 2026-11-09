/**
 * Preload script. Runs in a sandboxed context with access to ipcRenderer.
 * Exposes ONLY the narrow typed saveManager API — no raw ipcRenderer,
 * no Node APIs, no arbitrary channel access.
 */
import { contextBridge, ipcRenderer } from 'electron';
import { IpcChannels, IpcEvents } from '../../shared/ipc-channels';
import type {
  BackupCompletedEvent,
  BackupFailedEvent,
  BackupProgressEvent,
  SaveManagerApi,
} from '../../shared/types';

function invoke<T>(channel: string, payload?: unknown): Promise<T> {
  return ipcRenderer.invoke(channel, payload) as Promise<T>;
}

function onEvent<T>(event: string, listener: (e: T) => void): () => void {
  const wrapped = (_e: unknown, payload: T): void => listener(payload);
  ipcRenderer.on(event, wrapped);
  return () => {
    ipcRenderer.removeListener(event, wrapped);
  };
}

const api: SaveManagerApi = {
  games: {
    list: () => invoke(IpcChannels.gamesList, {}),
    add: (input) => invoke(IpcChannels.gamesAdd, input),
    update: (input) => invoke(IpcChannels.gamesUpdate, input),
    remove: (input) => invoke(IpcChannels.gamesRemove, input),
    discoverCandidates: () => invoke(IpcChannels.gamesDiscoverCandidates, {}),
    chooseFolder: () => invoke(IpcChannels.gamesChooseFolder, {}),
  },
  backups: {
    create: (input) => invoke(IpcChannels.backupsCreate, input),
    list: (input) => invoke(IpcChannels.backupsList, input),
    get: (input) => invoke(IpcChannels.backupsGet, input),
    verify: (input) => invoke(IpcChannels.backupsVerify, input),
    restore: (input) => invoke(IpcChannels.backupsRestore, input),
  },
  schedules: {
    list: () => invoke(IpcChannels.schedulesList, {}),
    set: (input) => invoke(IpcChannels.schedulesSet, input),
    delete: (input) => invoke(IpcChannels.schedulesDelete, input),
  },
  events: {
    onBackupProgress: (listener: (e: BackupProgressEvent) => void) =>
      onEvent(IpcEvents.backupProgress, listener),
    onBackupCompleted: (listener: (e: BackupCompletedEvent) => void) =>
      onEvent(IpcEvents.backupCompleted, listener),
    onBackupFailed: (listener: (e: BackupFailedEvent) => void) =>
      onEvent(IpcEvents.backupFailed, listener),
  },
};

contextBridge.exposeInMainWorld('saveManager', api);

declare global {
  interface Window {
    saveManager: SaveManagerApi;
  }
}
