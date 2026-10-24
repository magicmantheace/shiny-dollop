/**
 * Electron main process entry.
 *
 * - Chooses WindowsOsLayer on win32, MockOsLayer elsewhere (with a loud
 *   console warning — the mock never touches the OS, so a non-Windows build
 *   is a safe UI/test harness, not a functional Windows utility).
 * - Opens the SQLite DB under userData, seeds the built-in profile on first run.
 * - Registers the twelve gpp:* IPC channels; forwards activation progress
 *   events to the focused window.
 * - `--smoke` flag: open the window, wait for load, quit — used by npm run smoke.
 */

import { app, BrowserWindow } from 'electron';
import path from 'node:path';
import { GppDatabase } from './store/database.js';
import { MockOsLayer } from './os-layer/mock.js';
import { WindowsOsLayer } from './os-layer/windows.js';
import { OsLayer } from './os-layer/types.js';
import { registerIpcHandlers } from './ipc/handlers.js';
import { seedProfile, SEED_PROFILE_NAME } from './seed.js';

const SMOKE = process.argv.includes('--smoke');

function chooseOsLayer(): OsLayer {
  if (process.platform === 'win32') {
    return new WindowsOsLayer();
  }
  console.warn(
    '[gpp] WARNING: not running on Windows — using MockOsLayer. ' +
      'Previews and activations will use synthetic state and change nothing on this machine.',
  );
  return new MockOsLayer();
}

async function createWindow(): Promise<BrowserWindow> {
  const win = new BrowserWindow({
    width: 1100,
    height: 750,
    title: 'Game Performance Profiles',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  const rendererIndex = path.join(__dirname, '..', 'renderer', 'index.html');
  await win.loadFile(rendererIndex);
  return win;
}

async function main(): Promise<void> {
  await app.whenReady();

  const dbPath = path.join(app.getPath('userData'), 'gpp.sqlite');
  const db = new GppDatabase(dbPath);
  const os = chooseOsLayer();
  if (seedProfile(db)) console.log(`[gpp] seeded built-in profile "${SEED_PROFILE_NAME}"`);

  const window = await createWindow();
  registerIpcHandlers({
    db,
    os,
    emit: (event, payload) => {
      window.webContents.send(event, payload);
    },
  });

  if (SMOKE) {
    // Wait briefly for the renderer to settle, then exit 0. Any load failure
    // rejects createWindow() and exits non-zero via the catch below.
    await new Promise((r) => setTimeout(r, 2500));
    console.log('[gpp] smoke: window loaded ok');
    db.close();
    app.quit();
    return;
  }

  app.on('window-all-closed', () => {
    db.close();
    if (process.platform !== 'darwin') app.quit();
  });
}

main().catch((e) => {
  console.error('[gpp] fatal:', e);
  process.exit(1);
});
