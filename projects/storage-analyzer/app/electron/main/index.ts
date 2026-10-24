/**
 * Main process entry. Trusted side: owns the window, the database, the scan
 * engine, exports and all native OS access. The renderer is untrusted and may
 * only call the narrow typed API exposed through preload.
 */
import { app, BrowserWindow, session } from 'electron';
import fs from 'node:fs';
import path from 'node:path';
import { openDatabase } from './db/database';
import { abortAllScans, registerIpcHandlers } from './ipc/handlers';

const isDev = !!process.env.SA_DEV_SERVER;
let mainWindow: BrowserWindow | null = null;

function getMainWindow(): BrowserWindow | null {
  return mainWindow;
}

/**
 * Renderer HTML for the production build. Worker B owns app/src/; when it
 * has not been built yet (backend-only checkout), fall back to a data-URL
 * placeholder so the window — and `npm run smoke` — still works.
 */
function getRendererTarget(): { kind: 'file'; path: string } | { kind: 'url'; url: string } {
  if (isDev && process.env.SA_DEV_SERVER) {
    return { kind: 'url', url: process.env.SA_DEV_SERVER };
  }
  const html = path.join(__dirname, '..', '..', 'renderer', 'index.html');
  if (fs.existsSync(html)) {
    return { kind: 'file', path: html };
  }
  const placeholder = `<!doctype html><html><head><meta charset="utf-8"><title>Storage Analyzer</title></head>
<body style="background:#14161c;color:#e8eaf0;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div><h1>Storage Analyzer</h1><p>Backend scaffold is running. The renderer (Worker B) has not been built yet.</p></div>
</body></html>`;
  return { kind: 'url', url: `data:text/html,${encodeURIComponent(placeholder)}` };
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 980,
    minHeight: 640,
    title: 'Storage Analyzer',
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

  const target = getRendererTarget();
  if (target.kind === 'file') {
    void mainWindow.loadFile(target.path);
  } else {
    void mainWindow.loadURL(target.url);
    if (isDev) mainWindow.webContents.openDevTools({ mode: 'detach' });
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
        url.startsWith('data:text/html') ||
        (isDev && process.env.SA_DEV_SERVER && url.startsWith(process.env.SA_DEV_SERVER));
      if (!allowed) e.preventDefault();
    });
  });
  session.defaultSession.setPermissionRequestHandler((_wc, _permission, callback) =>
    callback(false),
  );
}

async function init(): Promise<void> {
  const db = openDatabase();

  registerIpcHandlers({ db, getMainWindow });

  installSecurityGuards();
  createWindow();

  // Smoke-test mode: used by `npm run smoke` under xvfb. Opens the real
  // window, then exits with a marker instead of running forever.
  if (process.env.SA_SMOKE) {
    await new Promise((resolve) => setTimeout(resolve, 2500));
    console.log('SMOKE_OK window opened');
    app.quit();
  }

  app.on('before-quit', () => {
    abortAllScans();
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
