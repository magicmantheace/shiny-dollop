// Electron main process bootstrap + smoke mode (--aidm-smoke).
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { app, BrowserWindow, ipcMain } from 'electron';
import { replayRoll } from '../../shared/dice.js';
import { isAidmError } from '../../shared/errors.js';
import { registerIpcHandlers } from './ipc.js';
import { CampaignService } from './service.js';
import { openDatabase } from './store.js';

const SMOKE_ARG = '--aidm-smoke';

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg);
}

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1240,
    height: 860,
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

/**
 * Smoke: the full MVP acceptance workflow against the real service and a
 * real database file — create campaign + characters, roll dice, run an
 * encounter with logged state, close the DB, reopen, and resume exactly.
 */
async function runSmoke(): Promise<void> {
  const dir = await mkdtemp(join(tmpdir(), 'aidm-smoke-'));
  const dbPath = join(dir, 'aidm.sqlite');
  let db = openDatabase(dbPath);
  try {
    const service = new CampaignService(db);
    const campaign = await service.campaignsCreate({
      name: 'Smoke Campaign',
      setting: 'A flooded watchtower.',
      seed: 'smoke-seed',
    });
    const session = await service.sessionsCreate(campaign.id, { title: 'Session 1' });
    const hero = await service.charactersCreate(campaign.id, {
      kind: 'pc',
      name: 'Wren',
      archetype: 'Scout',
      stats: { agility: 2 },
      hpMax: 12,
    });
    const foe = await service.charactersCreate(campaign.id, {
      kind: 'npc',
      name: 'Mire Hound',
      archetype: 'Beast',
      hpMax: 8,
    });

    const roll = await service.diceRoll(campaign.id, {
      notation: '2d6+1',
      label: 'Smoke roll',
      sessionId: session.id,
    });
    assert(replayRoll(roll.outcome), 'smoke roll does not replay from its recorded state');

    const encounter = await service.encountersStart(campaign.id, {
      name: 'Watchtower Ambush',
      characterIds: [hero.id, foe.id],
      sessionId: session.id,
    });
    assert(encounter.combatants.length === 2, 'encounter does not have 2 combatants');
    await service.encountersApplyDamage(encounter.id, {
      characterId: foe.id,
      amount: 3,
      note: 'smoke',
    });
    const midLog = await service.logList(campaign.id);
    assert(
      midLog.some((e) => e.kind === 'damage'),
      'damage was not logged',
    );

    const exported = await service.exportCampaign(campaign.id);
    assert(
      exported === (await service.exportCampaign(campaign.id)),
      'export is not byte-identical across calls',
    );

    // Narrate with the default mock narrator; rules state must not move.
    const stateBefore = (await service.campaignsGet(campaign.id)).diceState;
    const narration = await service.narrate(roll.entry.id);
    assert(narration.source === 'mock', 'default narration source is not mock');
    assert(
      (await service.campaignsGet(campaign.id)).diceState === stateBefore,
      'narration moved the dice stream',
    );

    // Close and reopen: the active encounter and HP must resume exactly.
    db.close();
    db = openDatabase(dbPath);
    const resumed = new CampaignService(db);
    const active = await resumed.encountersGetActive(campaign.id);
    assert(active !== null && active.id === encounter.id, 'active encounter did not resume');
    const foeAfter = (await resumed.charactersList(campaign.id)).find((c) => c.id === foe.id);
    assert(foeAfter?.hpCurrent === 5, `foe HP did not persist (got ${foeAfter?.hpCurrent})`);
    const logAfter = await resumed.logList(campaign.id);
    assert(logAfter.length >= midLog.length, 'log shrank across restart');

    const imported = await resumed.importCampaign(exported);
    assert(imported.id !== campaign.id, 're-import into the same DB should remap ids');
    const importedLog = await resumed.logList(imported.id);
    assert(importedLog.length === logAfter.length, 'imported campaign log length differs');

    console.log('SMOKE_OK');
  } catch (err) {
    console.error(
      'SMOKE_FAIL:',
      isAidmError(err)
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
  const dbPath = join(app.getPath('userData'), 'aidm.sqlite');
  const db = openDatabase(dbPath);
  const service = new CampaignService(db);
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
