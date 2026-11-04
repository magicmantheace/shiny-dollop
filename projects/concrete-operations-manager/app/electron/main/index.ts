/**
 * Main process entry. Trusted side: owns the window, the database, exports,
 * backup/restore and all native OS access. The renderer is untrusted and may
 * only call the narrow typed API exposed through preload.
 */
import { app, BrowserWindow, session } from 'electron';
import path from 'node:path';
import { openDatabase, getDatabasePath } from './db/database';
import { registerIpcHandlers } from './ipc/handlers';

const isDev = !!process.env.COM_DEV_SERVER;
let mainWindow: BrowserWindow | null = null;
let dbPath: string | null = null;

function getMainWindow(): BrowserWindow | null {
  return mainWindow;
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 980,
    minHeight: 640,
    title: 'Concrete Operations Manager',
    backgroundColor: '#14161c',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    },
  });

  if (isDev && process.env.COM_DEV_SERVER) {
    void mainWindow.loadURL(process.env.COM_DEV_SERVER);
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    void mainWindow.loadFile(path.join(__dirname, '..', '..', 'renderer', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/** Lock down navigation: the app window may never leave its own content. */
function installSecurityGuards(): void {
  app.on('web-contents-created', (_event, contents) => {
    contents.setWindowOpenHandler(() => ({ action: 'deny' }));
    contents.on('will-navigate', (e, url) => {
      const allowed =
        url.startsWith('file://') ||
        (isDev && process.env.COM_DEV_SERVER && url.startsWith(process.env.COM_DEV_SERVER));
      if (!allowed) e.preventDefault();
    });
  });
  session.defaultSession.setPermissionRequestHandler((_wc, _permission, callback) =>
    callback(false),
  );
}

async function init(): Promise<void> {
  const db = openDatabase();
  dbPath = getDatabasePath();

  registerIpcHandlers({
    db,
    dbPath,
    getMainWindow,
    reopenDatabase: () => openDatabase(),
  });

  installSecurityGuards();
  createWindow();

  // Smoke-test mode: used by `npm run smoke` under xvfb. Opens the real
  // window, then exits with a marker instead of running forever.
  if (process.env.COM_SMOKE) {
    await new Promise((resolve) => setTimeout(resolve, 2500));
    console.log('SMOKE_OK window opened');
    app.quit();
  }

  app.on('before-quit', () => {
    try {
      db.close();
    } catch {
      // Never block shutdown on teardown.
    }
  });
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
  void app.whenReady().then(init);
}
