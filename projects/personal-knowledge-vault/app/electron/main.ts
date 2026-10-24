/**
 * Electron main process: app lifecycle, database open, window creation,
 * and IPC registration. Renderer sources are owned by Worker B
 * (app/src/); this file loads the built renderer output when present.
 */
import { app, BrowserWindow } from 'electron';
import path from 'node:path';
import { openDatabase } from '../db/store';
import { registerPkvIpc } from './ipc';

let mainWindow: BrowserWindow | null = null;
let db: ReturnType<typeof openDatabase> | null = null;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: 'Personal Knowledge Vault',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  const rendererIndex = path.join(__dirname, '..', 'renderer', 'index.html');
  void mainWindow.loadFile(rendererIndex).catch(() => {
    // Renderer bundle not built yet (Worker B owns app/src/). Keep the
    // window shell up so the backend can still be smoke-tested.
    void mainWindow?.loadURL(
      'data:text/html,<title>Personal Knowledge Vault</title><h1>Personal Knowledge Vault</h1><p>Renderer not built yet.</p>',
    );
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  db = openDatabase();
  registerPkvIpc({ db, getMainWindow: () => mainWindow });

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  try {
    db?.close();
  } catch {
    /* best effort */
  }
  db = null;
});
