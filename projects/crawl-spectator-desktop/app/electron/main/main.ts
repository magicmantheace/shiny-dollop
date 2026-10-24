// Electron main process bootstrap + smoke mode (--spectator-smoke).
//
// Smoke mode runs the MVP acceptance walkthrough in DEMO/fixture terms:
// it starts the local fixture Feed server (real contract over HTTP),
// connects the engine in LIVE mode to it, and exercises descenders,
// profiles, history, search, the live ledger, follows + highlights,
// replay, preference persistence across a DB reopen, and demo mode.
// It never touches a real Underreach server or the user's data.

import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { app, BrowserWindow, ipcMain } from 'electron';
import { errorMessage } from '../../shared/errors.js';
import { SpectatorEngine } from './engine.js';
import { FixtureFeedServer } from './fixtureServer.js';
import { registerIpcHandlers } from './ipc.js';
import { openPrefsDatabase } from './prefs.js';

const SMOKE_ARG = '--spectator-smoke';

function assert(cond: boolean, msg: string): void {
  if (!cond) throw new Error(msg);
}

let mainWindow: BrowserWindow | null = null;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: join(__dirname, '..', 'preload', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
  mainWindow
    .loadFile(join(__dirname, '..', '..', 'renderer', 'index.html'))
    .catch((err: unknown) => console.error('Failed to load renderer:', err));
}

async function runSmoke(): Promise<void> {
  const dir = await mkdtemp(join(tmpdir(), 'spectator-smoke-'));
  const dbPath = join(dir, 'spectator.sqlite');
  const server = new FixtureFeedServer();
  let db: ReturnType<typeof openPrefsDatabase> | null = null;
  try {
    await server.listen(0);
    db = openPrefsDatabase(dbPath);
    const engine = new SpectatorEngine(db, { pollIntervalMs: 40, backoffBaseMs: 40, backoffMaxMs: 200 });

    // LIVE-mode connection to the fixture server (contract over real HTTP).
    const status = await engine.connectLive(server.baseUrl);
    assert(status.state === 'connected' && status.mode === 'live', `expected connected/live, got ${status.state}/${status.mode}`);
    assert(status.descentId === 'descent-fixture-001', `unexpected descent ${status.descentId}`);

    const descenders = await engine.listDescenders();
    assert(descenders.length === 8, `expected 8 fixture descenders, got ${descenders.length}`);

    const profile = await engine.getProfile('mira-vane');
    assert(profile.current_stratum === 3, 'profile stratum mismatch');
    assert((profile.relationships ?? []).length >= 1, 'profile relationships missing');

    const history = await engine.getHistory('mira-vane');
    assert(history.length >= 3, `expected mira-vane history, got ${history.length} events`);

    const found = await engine.search('mira');
    assert(found.descenders.some((d) => d.descender_id === 'mira-vane'), 'search did not find mira-vane');

    const parties = await engine.listParties();
    assert(parties.length === 2, `expected 2 parties, got ${parties.length}`);

    const feed = engine.feedSnapshot();
    assert(feed.events.length >= 10, `expected initial ledger in feed, got ${feed.events.length}`);
    const ids = new Set(feed.events.map((e) => e.id));
    assert(ids.size === feed.events.length, 'feed contains duplicate event ids');
    for (let i = 1; i < feed.events.length; i++) {
      const prev = feed.events[i - 1]!;
      const cur = feed.events[i]!;
      assert(prev.tick < cur.tick || (prev.tick === cur.tick && prev.id < cur.id), 'feed events out of order');
    }

    // Follows are local-only and feed the highlights computation.
    engine.follow('mira-vane');
    server.feed.advance();
    server.feed.advance();
    const highlights = await engine.getHighlights();
    assert(highlights.length >= 1, 'expected highlights for followed mira-vane');
    assert(
      highlights.every((e) => e.actor_ids.includes('mira-vane')),
      'highlight without the followed descender',
    );

    const replay = await engine.getReplay({ afterTick: 1220, limit: 100 });
    assert(replay.length >= 1 && replay.every((e) => e.tick > 1220), 'replay after_tick semantics broken');

    // Read-only proof over the wire: every request so far was a GET.
    assert(server.requests.length > 0, 'fixture server saw no requests');
    assert(server.requests.every((r) => r.method === 'GET'), 'client issued a non-GET request');
    assert(
      !server.requests.some((r) => r.path.includes('/live/follow') || r.path.includes('/live/release')),
      'client called a server session endpoint',
    );

    await engine.disconnect();

    // Preferences survive a database reopen.
    db.close();
    db = openPrefsDatabase(dbPath);
    const engine2 = new SpectatorEngine(db, { pollIntervalMs: 40 });
    assert(engine2.getPrefs().followedDescenderIds.includes('mira-vane'), 'follow did not persist across reopen');

    // Demo mode: in-process fixture, clearly labeled by mode.
    const demoStatus = await engine2.connectDemo();
    assert(demoStatus.state === 'connected' && demoStatus.mode === 'demo', 'demo mode did not connect');
    assert(engine2.feedSnapshot().events.length >= 10, 'demo feed empty');
    await engine2.disconnect();

    console.log('SMOKE_OK');
  } catch (err) {
    console.error('SMOKE_FAIL:', errorMessage(err));
    process.exitCode = 1;
  } finally {
    try {
      db?.close();
    } catch {
      /* ignore */
    }
    await server.close();
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
  const dbPath = join(app.getPath('userData'), 'spectator.sqlite');
  const db = openPrefsDatabase(dbPath);
  const engine = new SpectatorEngine(db);
  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });
  app.on('before-quit', () => {
    try {
      db.close();
    } catch {
      /* ignore */
    }
  });
  await app.whenReady();
  registerIpcHandlers(ipcMain, engine, () => mainWindow);
  createWindow();
}

void boot();
