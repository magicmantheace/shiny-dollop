// Electron main process bootstrap + smoke mode (--lacc-smoke).
import { mkdtemp, mkdir, readFile, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { app, BrowserWindow, dialog, ipcMain } from 'electron';
import { isLaccError } from '../../shared/errors.js';
import { MockAdapter } from './adapter.js';
import { TaskEngine } from './engine.js';
import { registerIpcHandlers } from './ipc.js';
import { openDatabase } from './store.js';

const SMOKE_ARG = '--lacc-smoke';
function assert(cond: boolean, msg: string): void { if (!cond) throw new Error(msg); }

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1100, height: 750,
    webPreferences: { preload: join(__dirname, '..', 'preload', 'preload.js'), contextIsolation: true, nodeIntegration: false },
  });
  win.loadFile(join(__dirname, '..', '..', 'renderer', 'index.html')).catch((err: unknown) => console.error('Failed to load renderer:', err));
  // Note: sibling pattern loads dist/renderer/index.html; __dirname is dist/electron/main, so ../../renderer = dist/renderer
}

async function runSmoke(): Promise<void> {
  const dir = await mkdtemp(join(tmpdir(), 'lacc-smoke-'));
  const dbPath = join(dir, 'lacc.sqlite');
  const ws = join(dir, 'ws');
  await mkdir(ws, { recursive: true });
  const db = openDatabase(dbPath);
  try {
    const engine = new TaskEngine(db, { adapterFactory: () => new MockAdapter({ delayMs: 1 }) });
    engine.saveConfig({ mode: 'mock', baseUrl: 'http://127.0.0.1:11434', model: 'mock-echo-1', timeoutMs: 5000, workspaceRoot: ws });
    const health = await engine.health();
    assert(health.ok, 'health not ok');
    const t1 = engine.submit({ prompt: 'Say hello' });
    await engine.whenIdle();
    const done1 = engine.getTask(t1.id);
    assert(done1.status === 'completed', `task1 status ${done1.status}`);

    const tHang = engine.submit({ prompt: '[mock:hang] please wait' });
    // wait until running
    for (let i = 0; i < 100 && engine.getTask(tHang.id).status !== 'running'; i++) await new Promise((r) => setTimeout(r, 10));
    const cancelled = await engine.cancel(tHang.id);
    assert(cancelled.status === 'cancelled', `hang task not cancelled: ${cancelled.status}`);

    const proposePrompt = 'Create file\n```propose path=notes/out.txt\nhello smoke\n```';
    engine.submit({ prompt: proposePrompt });
    await engine.whenIdle();
    const props1 = engine.listProposals();
    assert(props1.length >= 1, 'no proposal created');
    const p1 = props1[props1.length - 1]!;
    assert(p1.status === 'pending', 'proposal not pending');
    assert(p1.relativePath === 'notes/out.txt', `proposal path ${p1.relativePath}`);
    await engine.reject(p1.id);
    assert(!existsSync(join(ws, 'notes/out.txt')), 'rejected proposal file must not exist');

    const propose2 = 'Create file\n```propose path=notes/ok.txt\napproved content\n```';
    engine.submit({ prompt: propose2 });
    await engine.whenIdle();
    const props2 = engine.listProposals().filter((p) => p.relativePath === 'notes/ok.txt');
    assert(props2.length >= 1, 'no second proposal');
    const p2 = props2[props2.length - 1]!;
    const approved = await engine.approve(p2.id);
    assert(approved.status === 'approved', 'proposal not approved');
    const onDisk = await readFile(join(ws, 'notes/ok.txt'), 'utf8');
    assert(onDisk === p2.proposedContent, `file content mismatch: ${JSON.stringify(onDisk)} vs ${JSON.stringify(p2.proposedContent)}`);
    console.log('SMOKE_OK');
  } catch (err) {
    console.error('SMOKE_FAIL:', isLaccError(err) ? `${err.code}: ${err.message}` : err instanceof Error ? err.message : String(err));
    process.exitCode = 1;
  } finally {
    try { db.close(); } catch { /* ignore */ }
    await rm(dir, { recursive: true, force: true });
  }
}

async function boot(): Promise<void> {
  if (process.argv.includes(SMOKE_ARG)) {
    await app.whenReady();
    await runSmoke();
    app.exit(typeof process.exitCode === 'number' ? process.exitCode : 0);
    return;
  }
  const dbPath = join(app.getPath('userData'), 'lacc.sqlite');
  const db = openDatabase(dbPath);
  const engine = new TaskEngine(db);
  app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
  app.on('before-quit', () => { try { db.close(); } catch { /* ignore */ } });
  await app.whenReady();
  registerIpcHandlers(ipcMain, engine, async () => {
    const res = await dialog.showOpenDialog({ properties: ['openDirectory'] });
    return res.canceled ? null : (res.filePaths[0] ?? null);
  });
  createWindow();
}
void boot();
