/**
 * Electron main process entry point.
 * Owns the window, the SQLite database, and all IPC handlers.
 */
import { app, BrowserWindow } from 'electron';
import path from 'node:path';
import { openDatabase } from './db/database';
import { registerIpcHandlers } from './ipc/handlers';

let mainWindow: BrowserWindow | null = null;

function getDatabasePath(): string {
  return path.join(app.getPath('userData'), 'data', 'template-factory.db');
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    title: 'Digital Product Template Factory',
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    void mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    void mainWindow.loadFile(path.join(__dirname, '..', '..', 'renderer', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

async function main(): Promise<void> {
  await app.whenReady();

  const db = openDatabase(getDatabasePath());
  registerIpcHandlers({ db, getMainWindow: () => mainWindow });

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });

  app.on('before-quit', () => {
    db.close();
  });
}

void main();

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
