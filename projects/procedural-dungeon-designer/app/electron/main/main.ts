// Electron main process bootstrap + smoke mode (--pdd-smoke).
import { deepStrictEqual } from 'node:assert';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { app, BrowserWindow, ipcMain } from 'electron';
import { isPddError } from '../../shared/errors.js';
import { registerIpcHandlers } from './ipc.js';
import { DungeonService } from './service.js';
import { openDatabase } from './store.js';

const SMOKE_ARG = '--pdd-smoke';

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg);
}

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1200,
    height: 820,
    webPreferences: {
      preload: join(__dirname, '..', 'preload', 'preload.js'),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  // __dirname is dist/electron/main, so ../../renderer = dist/renderer.
  win
    .loadFile(join(__dirname, '..', '..', 'renderer', 'index.html'))
    .catch((err: unknown) => console.error('Failed to load renderer:', err));
}

async function runSmoke(): Promise<void> {
  const dir = await mkdtemp(join(tmpdir(), 'pdd-smoke-'));
  const dbPath = join(dir, 'pdd.sqlite');
  const db = openDatabase(dbPath);
  try {
    const service = new DungeonService(db);
    const map = await service.generate({
      seed: 'smoke-seed',
      gridWidth: 24,
      gridHeight: 18,
      roomCount: 8,
      theme: 'sunken-crypt',
      difficulty: 2,
    });
    const validation = await service.validateMap(map);
    assert(validation.connected, 'generated smoke map is not connected');

    let current = await service.dungeonsSave({ name: 'Smoke Dungeon', map });
    const targetRoom = current.map.rooms.find((r) => !r.isEntrance);
    assert(targetRoom !== undefined, 'smoke map has no non-entrance room');

    const themes = await service.themesList();
    const theme = themes.find((t) => t.id === current.map.params.theme);
    assert(theme !== undefined, 'smoke theme not found');

    // First theme encounter entry that fits the remaining budget; free
    // budget by removing generated placements if none fits initially.
    const remaining = (): number => current.map.budgetLimit - current.map.budgetUsed;
    let entry = theme.tables.encounter.find((e) => e.cost <= remaining());
    while (!entry) {
      const existing = current.map.rooms.flatMap((r) => r.placements)[0];
      if (!existing) throw new Error('No encounter fits and no placement to remove in smoke.');
      current = await service.placementsRemove(current.id, existing.id);
      entry = theme.tables.encounter.find((e) => e.cost <= remaining());
    }

    const beforeIds = new Set(targetRoom.placements.map((p) => p.id));
    current = await service.placementsAdd(current.id, {
      roomId: targetRoom.id,
      kind: 'encounter',
      key: entry.key,
    });
    const addedRoom = current.map.rooms.find((r) => r.id === targetRoom.id);
    const added = addedRoom?.placements.find((p) => !beforeIds.has(p.id));
    assert(added !== undefined, 'placementsAdd did not add a placement');
    assert(added.key === entry.key && added.cost === entry.cost, 'added placement does not match the theme entry');

    const export1 = await service.exportJson(current.id);
    const export2 = await service.exportJson(current.id);
    assert(export1 === export2, 'exportJson is not byte-identical across calls');

    const imported = await service.importJson(export1);
    try {
      deepStrictEqual(imported.map, current.map);
    } catch {
      throw new Error('imported map does not deep-equal the saved map');
    }

    const afterRemove = await service.placementsRemove(current.id, added.id);
    assert(
      !afterRemove.map.rooms.some((r) => r.placements.some((p) => p.id === added.id)),
      'placementsRemove did not remove the placement',
    );

    console.log('SMOKE_OK');
  } catch (err) {
    console.error(
      'SMOKE_FAIL:',
      isPddError(err)
        ? `${err.code}: ${err.message}`
        : err instanceof Error
          ? err.message
          : String(err),
    );
    process.exitCode = 1;
  } finally {
    try {
      db.close();
    } catch {
      /* ignore */
    }
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
  const dbPath = join(app.getPath('userData'), 'pdd.sqlite');
  const db = openDatabase(dbPath);
  const service = new DungeonService(db);
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
  registerIpcHandlers(ipcMain, service);
  createWindow();
}

void boot();
