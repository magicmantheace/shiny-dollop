import { app, BrowserWindow } from 'electron';
import path from 'node:path';
import { closeDb } from './db/database';
import { registerIpc } from './ipc/handlers';

let mainWindow: BrowserWindow | null = null;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'Volumetric Concrete Mix Calculator',
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  if (process.env.VCC_DEV_URL) {
    mainWindow.loadURL(process.env.VCC_DEV_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', '..', 'renderer', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Smoke mode (CI/verification): quit shortly after the window loads so the
  // smoke script can assert a clean boot without user interaction.
  if (process.env.VCC_SMOKE === '1') {
    mainWindow.webContents.on('did-finish-load', () => {
      setTimeout(() => app.quit(), 2000);
    });
    // Failsafe: never hang the smoke run.
    setTimeout(() => app.quit(), 20000);
  }
}

app.whenReady().then(() => {
  registerIpc();
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  closeDb();
});
