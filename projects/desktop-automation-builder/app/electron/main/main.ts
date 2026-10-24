// Electron main process: app bootstrap, SQLite store wiring, IPC handlers.
// Smoke mode (`--dab-smoke`): exercises the compiled backend against a temp
// database and prints SMOKE_OK — no window is created.
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { app, BrowserWindow, dialog, ipcMain } from 'electron';
import { isDabError, previewWorkflow, startRun } from './executor.js';
import { registerIpcHandlers } from './ipc.js';
import { createWorkflow, openDatabase, updateWorkflow } from './store.js';

const SMOKE_ARG = '--dab-smoke';

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1100,
    height: 750,
    webPreferences: {
      preload: join(__dirname, '..', 'preload', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  // Renderer bundle is produced by `npm run build:renderer` (Worker B owns
  // app/src/** and app/index.html).
  win.loadFile(join(__dirname, '..', 'renderer', 'index.html')).catch((err: unknown) => {
    console.error('Failed to load renderer:', err);
  });
}

async function runSmoke(): Promise<void> {
  const dir = await mkdtemp(join(tmpdir(), 'dab-smoke-'));
  const dbPath = join(dir, 'dab.sqlite');
  const db: DatabaseSync = openDatabase(dbPath);
  try {
    const sandbox = join(dir, 'sandbox');
    const wf = createWorkflow(db, { name: 'smoke', sandboxRoot: sandbox });
    const updated = updateWorkflow(db, wf.id, {
      steps: [
        { id: 's1', label: 'Make folder', kind: 'folder-create', path: 'docs' },
        { id: 's2', label: 'Note', kind: 'log-message', message: 'smoke says hi' },
      ],
    });
    if (!updated || updated.version !== 2 || updated.versions.length !== 1) {
      throw new Error('smoke: version bump / history failed');
    }
    const preview = previewWorkflow(db, updated);
    if (preview.length !== 2) throw new Error('smoke: preview step count mismatch');

    // Seed a source file, then run a real file-copy workflow end to end.
    await writeFile(join(dir, 'in.txt'), 'smoke-data');
    const wf2 = createWorkflow(db, { name: 'smoke-copy', sandboxRoot: dir });
    const wf2u = updateWorkflow(db, wf2.id, {
      steps: [{ id: 'c1', label: 'Copy it', kind: 'file-copy', from: 'in.txt', to: 'docs/out.txt' }],
    });
    if (!wf2u) throw new Error('smoke: workflow update returned null');
    const run = await startRun(db, wf2.id, { approved: true });
    if (run.status !== 'completed') throw new Error(`smoke: run status ${run.status}`);
    if (run.steps[0]?.outcome !== 'succeeded') throw new Error('smoke: copy step did not succeed');

    console.log('SMOKE_OK');
  } catch (err) {
    console.error('SMOKE_FAIL:', isDabError(err) ? `${err.code}: ${err.message}` : String(err));
    process.exitCode = 1;
  } finally {
    db.close();
    await rm(dir, { recursive: true, force: true });
  }
}

async function boot(): Promise<void> {
  if (process.argv.includes(SMOKE_ARG)) {
    await app.whenReady();
    await runSmoke();
    app.exit(0);
    return;
  }

  const dbPath = join(app.getPath('userData'), 'dab.sqlite');
  const db = openDatabase(dbPath);

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });
  app.on('before-quit', () => {
    try {
      db.close();
    } catch {
      // Best effort on shutdown.
    }
  });

  await app.whenReady();
  registerIpcHandlers(ipcMain, {
    db,
    pickDirectory: async () => {
      const res = await dialog.showOpenDialog({ properties: ['openDirectory'] });
      return res.canceled ? null : (res.filePaths[0] ?? null);
    },
  });
  createWindow();
}

void boot();
