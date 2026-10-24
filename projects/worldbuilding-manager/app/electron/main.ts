/**
 * Electron main process: owns the SQLite database in userData, registers
 * IPC, and hosts the renderer in a locked-down window. Fully offline.
 */
import { app, BrowserWindow } from 'electron';
import { join } from 'node:path';
import { WorldStore } from '../db/world';
import { registerIpc } from './ipc';

let mainWindow: BrowserWindow | null = null;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'Novel and Worldbuilding Manager',
    webPreferences: {
      preload: join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  const devUrl = process.env['WBM_DEV_URL'];
  if (devUrl) {
    void mainWindow.loadURL(devUrl);
  } else {
    void mainWindow.loadFile(join(__dirname, '..', 'renderer', 'index.html'));
  }
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  const store = new WorldStore(join(app.getPath('userData'), 'worldbuilding.sqlite'));
  registerIpc(store);
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
  app.on('window-all-closed', () => {
    store.close();
    if (process.platform !== 'darwin') app.quit();
  });
});
