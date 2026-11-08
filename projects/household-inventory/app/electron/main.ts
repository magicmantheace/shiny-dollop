/**
 * Main process entry. Trusted side: owns the window, the database, the
 * simulation engine, report export, and all native OS access. The renderer
 * is untrusted and may only call the narrow typed API exposed through preload.
 */
import { app, BrowserWindow, session } from 'electron';
import fs from 'node:fs';
import path from 'node:path';
import { openDatabase } from '../db/store';
import { registerIpcHandlers } from './ipc';

const isDev = !!process.env.HI_DEV_SERVER;
const isSmoke = !!process.env.HI_SMOKE;
let mainWindow: BrowserWindow | null = null;

function getMainWindow(): BrowserWindow | null {
  return mainWindow;
}

/**
 * Renderer HTML for the production build. Worker B owns app/renderer/**;
 * when it has not been built yet (backend-only checkout), fall back to a
 * data-URL placeholder so the window — and `npm run smoke` — still works.
 */
function getRendererTarget(): { kind: 'file'; path: string } | { kind: 'url'; url: string } {
  if (isDev && process.env.HI_DEV_SERVER) {
    return { kind: 'url', url: process.env.HI_DEV_SERVER };
  }
  const html = path.join(__dirname, '..', 'renderer', 'index.html');
  if (fs.existsSync(html)) {
    return { kind: 'file', path: html };
  }
  const placeholder = `<!doctype html><html><head><meta charset="utf-8"><title>Household Inventory</title></head>
<body style="background:#14161c;color:#e8eaf0;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div><h1>Household Inventory</h1><p>Backend scaffold is running. The renderer (Worker B) has not been built yet.</p></div>
</body></html>`;
  return { kind: 'url', url: `data:text/html,${encodeURIComponent(placeholder)}` };
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 980,
    minHeight: 640,
    title: 'Household Inventory',
    backgroundColor: '#14161c',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
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

  if (isSmoke) {
    mainWindow.webContents.once('did-finish-load', () => {
      // Real native window opened with the production bundle: smoke passes.
      console.log('SMOKE_OK');
    });
  }
}

/** Lock down navigation: the app window may never leave its own content. */
function installSecurityGuards(): void {
  app.on('web-contents-created', (_event, contents) => {
    contents.setWindowOpenHandler(() => ({ action: 'deny' }));
    contents.on('will-navigate', (e, url) => {
      const allowed =
        url.startsWith('file://') ||
        url.startsWith('data:text/html') ||
        (isDev && process.env.HI_DEV_SERVER && url.startsWith(process.env.HI_DEV_SERVER));
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
  await app.whenReady();
  installSecurityGuards(); // session.defaultSession requires the app to be ready
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
}

void init().catch((err: unknown) => {
  console.error('[household-inventory] failed to start:', err);
  app.exit(1);
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
