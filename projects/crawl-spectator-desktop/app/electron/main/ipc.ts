// ipcMain registration for the spectator API. All inputs are validated;
// the engine does the work. Status/feed changes are pushed to the window.

import type { BrowserWindow, IpcMain } from 'electron';
import { SPECTATOR_IPC_CHANNELS as CH } from '../../shared/types.js';
import type { SpectatorEngine } from './engine.js';
import { BaseUrlInput, DescenderIdInput, LimitInput, ReplayQueryInput, SearchQueryInput, parseInput } from './schemas.js';

export function registerIpcHandlers(ipcMain: IpcMain, engine: SpectatorEngine, getWindow: () => BrowserWindow | null): void {
  const win = (): BrowserWindow | null => getWindow();
  engine.onStatus((status) => win()?.webContents.send(CH.statusChanged, status));
  engine.onFeed((snapshot) => win()?.webContents.send(CH.feedChanged, snapshot));

  ipcMain.handle(CH.getStatus, () => engine.status);
  ipcMain.handle(CH.connectLive, (_e, baseUrl: unknown) => engine.connectLive(parseInput(BaseUrlInput, baseUrl, 'base URL')));
  ipcMain.handle(CH.connectDemo, () => engine.connectDemo());
  ipcMain.handle(CH.disconnect, () => engine.disconnect());
  ipcMain.handle(CH.getDescent, () => engine.getDescent());
  ipcMain.handle(CH.listDescenders, () => engine.listDescenders());
  ipcMain.handle(CH.getProfile, (_e, id: unknown) => engine.getProfile(parseInput(DescenderIdInput, id, 'descender id')));
  ipcMain.handle(CH.getHistory, (_e, id: unknown, limit: unknown) =>
    engine.getHistory(parseInput(DescenderIdInput, id, 'descender id'), parseInput(LimitInput, limit, 'limit') ?? 200));
  ipcMain.handle(CH.search, (_e, q: unknown) => engine.search(parseInput(SearchQueryInput, q, 'search query')));
  ipcMain.handle(CH.listParties, () => engine.listParties());
  ipcMain.handle(CH.getFeed, () => engine.feedSnapshot());
  ipcMain.handle(CH.getReplay, (_e, query: unknown) => {
    const q = parseInput(ReplayQueryInput, query ?? {}, 'replay query');
    return engine.getReplay({ afterTick: q.afterTick ?? null, limit: q.limit ?? 100, eventType: q.eventType ?? null });
  });
  ipcMain.handle(CH.getHighlights, () => engine.getHighlights());
  ipcMain.handle(CH.getPrefs, () => engine.getPrefs());
  ipcMain.handle(CH.follow, (_e, id: unknown) => engine.follow(parseInput(DescenderIdInput, id, 'descender id')));
  ipcMain.handle(CH.unfollow, (_e, id: unknown) => engine.unfollow(parseInput(DescenderIdInput, id, 'descender id')));
  ipcMain.handle(CH.exportPrefs, () => engine.exportPrefs());
  ipcMain.handle(CH.importPrefs, (_e, envelope: unknown) => engine.importPrefs(envelope));
}
