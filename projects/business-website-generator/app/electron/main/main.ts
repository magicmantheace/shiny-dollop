/**
 * Electron main process entry: window lifecycle, SQLite store, IPC wiring.
 *
 * The renderer is owned by Worker B; this file only creates the window and
 * hands it the preload bridge.
 */
import { app, BrowserWindow, dialog } from 'electron';
import * as path from 'node:path';
import { openDb } from './db.js';
import { registerIpc } from './ipc.js';

const isDev = !app.isPackaged;

function dbPath(): string {
  return path.join(app.getPath('userData'), 'bwg.sqlite');
}

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  if (isDev) {
    win.loadURL('http://localhost:5176').catch(() => {
      win.loadFile(path.join(__dirname, '..', 'renderer', 'index.html'));
    });
  } else {
    win.loadFile(path.join(__dirname, '..', 'renderer', 'index.html'));
  }
  return win;
}

async function boot(): Promise<void> {
  await app.whenReady();
  const store = openDb(dbPath());
  registerIpc({
    store,
    pickDirectory: async () => {
      const options = {
        properties: ['openDirectory', 'createDirectory'] as ('openDirectory' | 'createDirectory')[],
        title: 'Choose an export folder',
      };
      const win = BrowserWindow.getFocusedWindow();
      const res = win ? await dialog.showOpenDialog(win, options) : await dialog.showOpenDialog(options);
      return res.canceled ? null : (res.filePaths[0] ?? null);
    },
  });

  const win = createWindow();
  void win;

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
}

void boot();

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
