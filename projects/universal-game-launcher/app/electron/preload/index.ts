/**
 * Preload script. Runs in a sandboxed context with access to ipcRenderer.
 * Exposes ONLY the narrow typed gameLauncher API — no raw ipcRenderer,
 * no Node APIs, no way to smuggle an arbitrary path to the spawn path.
 */
import { contextBridge, ipcRenderer } from 'electron';
import { IpcChannels } from '../../shared/ipc-channels';
import type { GameLauncherApi } from '../../shared/types';

function invoke<T>(channel: string, payload?: unknown): Promise<T> {
  return ipcRenderer.invoke(channel, payload) as Promise<T>;
}

const api: GameLauncherApi = {
  library: {
    list: (query) => invoke(IpcChannels.libraryList, query),
    addManual: (input) => invoke(IpcChannels.libraryAddManual, input),
    update: (input) => invoke(IpcChannels.libraryUpdate, input),
    remove: (input) => invoke(IpcChannels.libraryRemove, input),
    setFavorite: (input) => invoke(IpcChannels.librarySetFavorite, input),
  },
  games: {
    launch: (input) => invoke(IpcChannels.gamesLaunch, input),
  },
  sessions: {
    list: (input) => invoke(IpcChannels.sessionsList, input),
    clear: () => invoke(IpcChannels.sessionsClear, {}),
  },
  settings: {
    get: () => invoke(IpcChannels.settingsGet, {}),
    update: (input) => invoke(IpcChannels.settingsUpdate, input),
  },
  files: {
    chooseExecutable: () => invoke(IpcChannels.filesChooseExecutable, {}),
    chooseCover: () => invoke(IpcChannels.filesChooseCover, {}),
    coverData: (input) => invoke(IpcChannels.filesCoverData, input),
  },
  sources: {
    status: () => invoke(IpcChannels.sourcesStatus, {}),
    scan: (input) => invoke(IpcChannels.sourcesScan, input),
    cancelScan: () => invoke(IpcChannels.sourcesCancelScan, {}),
    openClient: (input) => invoke(IpcChannels.sourcesOpenClient, input),
  },
};

contextBridge.exposeInMainWorld('gameLauncher', api);
