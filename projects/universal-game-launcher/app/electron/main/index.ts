/**
 * Main process entry. Trusted side: owns the window, the database, process
 * spawning and all native OS access. The renderer is untrusted and may only
 * call the narrow typed API exposed through the preload script.
 */
import { app, BrowserWindow, session } from 'electron';
import path from 'node:path';
import { openDatabase } from './data/database';
import { recoverInterruptedSessions } from './data/sessions';
import { GameLauncher } from './launch/launcher';
import { registerIpcHandlers } from './ipc/handlers';
import { chooseExecutable } from './files/picker';

const isDev = !!process.env.UGL_DEV_SERVER;
let mainWindow: BrowserWindow | null = null;
let launcher: GameLauncher | null = null;

function getMainWindow(): BrowserWindow | null {
  return mainWindow;
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'Universal Game Launcher',
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

  if (isDev && process.env.UGL_DEV_SERVER) {
    void mainWindow.loadURL(process.env.UGL_DEV_SERVER);
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
        (isDev && process.env.UGL_DEV_SERVER && url.startsWith(process.env.UGL_DEV_SERVER));
      if (!allowed) e.preventDefault();
    });
  });
  // Tighten the default session: no media permissions needed by the launcher UI.
  session.defaultSession.setPermissionRequestHandler((_wc, _permission, callback) =>
    callback(false),
  );
}

async function init(): Promise<void> {
  const db = openDatabase();
  // Conservative crash recovery: sessions left 'running' end at last checkpoint.
  const recovered = recoverInterruptedSessions(db);
  if (recovered > 0) {
    console.log(`[main] recovered ${recovered} interrupted session(s) from previous run`);
  }

  launcher = new GameLauncher({ db });
  registerIpcHandlers({
    db,
    launcher,
    chooseExecutable,
    getMainWindow,
  });

  installSecurityGuards();
  createWindow();

  // Smoke-test mode: used by `npm run smoke` under xvfb. Opens the real
  // window, then exits with a marker instead of running forever.
  if (process.env.UGL_SMOKE) {
    await new Promise((resolve) => setTimeout(resolve, 2500));
    console.log('SMOKE_OK window opened');
    app.quit();
  }

  app.on('before-quit', () => {
    try {
      launcher?.shutdown();
    } catch {
      // Never block shutdown on session finalization.
    }
    try {
      db.close();
    } catch {
      // ignore
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

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
