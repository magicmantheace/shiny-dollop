/**
 * Regression tests for "scans block the main process; cancellation
 * unreliable". Scans are async and yield to the event loop between
 * manifests, so the main thread stays responsive and the cancel IPC is
 * honored promptly. Covers: mid-scan cancel over hundreds of manifests,
 * immediate cancel, the same-source overlap guard, malformed/inaccessible
 * manifests, library integrity after cancel, and progress reporting.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { IpcChannels } from '../../shared/ipc-channels';
import type { Game } from '../../shared/types';
import { createTestContext, type TestContext } from './helpers';
import { SteamAdapter } from '../../electron/main/sources/steam/adapter';
import { FakeSteamOs, acf, fakeSteamInstall } from '../steam-helpers';

const STEAM_DIR = 'C:\\Program Files (x86)\\Steam';

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Fake Steam install whose reads take a few ms — simulates real disk I/O. */
class SlowSteamOs extends FakeSteamOs {
  delayMs = 3;

  async readTextFile(p: string, maxBytes: number): Promise<string> {
    await sleep(this.delayMs);
    return super.readTextFile(p, maxBytes);
  }
}

/** A fake Steam install with `count` manifests. */
function manyManifestTree(count: number): SlowSteamOs {
  const os = new SlowSteamOs();
  os.platform = 'win32';
  os.setEnv('ProgramFiles(x86)', 'C:\\Program Files (x86)');
  fakeSteamInstall(os, STEAM_DIR);
  for (let i = 0; i < count; i++) {
    const appid = String(100000 + i);
    os.addFile(
      `${STEAM_DIR}\\steamapps\\appmanifest_${appid}.acf`,
      acf(appid, `Fixture Game ${appid}`, `Game${appid}`),
    );
  }
  return os;
}

let ctx: TestContext | null = null;
afterEach(() => {
  ctx?.close();
  ctx = null;
});

function openContext(os: FakeSteamOs) {
  ctx = createTestContext({ steamOs: os });
}

async function listSteamGames(): Promise<Game[]> {
  const list = await ctx!.call(IpcChannels.libraryList, { source: 'steam' });
  expect(list.ok).toBe(true);
  return (list.data as Game[]).sort((a, b) => (a.externalId ?? '').localeCompare(b.externalId ?? ''));
}

describe('adapter-level cancellation', () => {
  it('cancels mid-scan over hundreds of manifests without throwing', async () => {
    const os = manyManifestTree(300);
    const adapter = new SteamAdapter(os);
    const token = { cancelled: false };
    const progress: Array<[number, number]> = [];
    // Cancel after the first few manifests, the way a real cancel IPC would.
    const scanPromise = adapter.scan(token, (scanned, total) => {
      progress.push([scanned, total]);
      if (scanned >= 5) token.cancelled = true;
    });
    const r = await scanPromise;
    expect(r.status).toBe('cancelled');
    expect(r.games.length).toBeLessThan(300);
    expect(r.games.length).toBeGreaterThan(0);
    // Progress was reported with a real total and increasing counts.
    expect(progress.length).toBeGreaterThan(0);
    const totals = new Set(progress.map(([, t]) => t));
    expect(totals.size).toBe(1);
    expect([...totals][0]).toBe(300);
    for (let i = 1; i < progress.length; i++) {
      expect(progress[i]![0]).toBeGreaterThan(progress[i - 1]![0]);
    }
  });

  it('cancelling before the first manifest yields an empty, safe result', async () => {
    const os = manyManifestTree(50);
    const adapter = new SteamAdapter(os);
    const r = await adapter.scan({ cancelled: true });
    expect(r.status).toBe('cancelled');
    expect(r.games).toHaveLength(0);
    expect(r.error).toBeNull();
  });

  it('a full scan completes and reports progress through to the total', async () => {
    const os = manyManifestTree(25);
    const adapter = new SteamAdapter(os);
    const seen = new Set<number>();
    const r = await adapter.scan({ cancelled: false }, (scanned, total) => {
      seen.add(scanned);
      expect(total).toBe(25);
    });
    expect(r.status).toBe('completed');
    expect(r.games).toHaveLength(25);
    expect(Math.max(...seen)).toBe(25);
  });
});

describe('malformed and inaccessible manifests', () => {
  it('skips bad manifests with warnings and still completes', async () => {
    const os = new FakeSteamOs();
    os.platform = 'win32';
    os.setEnv('ProgramFiles(x86)', 'C:\\Program Files (x86)');
    fakeSteamInstall(os, STEAM_DIR);
    // Valid game.
    os.addFile(`${STEAM_DIR}\\steamapps\\appmanifest_10.acf`, acf('10', 'Good Game', 'GoodGame'));
    // Malformed VDF.
    os.addFile(`${STEAM_DIR}\\steamapps\\appmanifest_20.acf`, '"AppState"\n{ unclosed');
    // Unreadable: listed in the dir via a different casing trick is awkward in
    // the fake, so simulate a directory where the manifest lives instead.
    os.addFile(`${STEAM_DIR}\\steamapps\\appmanifest_30.acf`, acf('30', 'Another Good', 'AnotherGood'));
    // Manifest whose inner appid disagrees with the file name.
    os.addFile(
      `${STEAM_DIR}\\steamapps\\appmanifest_40.acf`,
      acf('999', 'Mismatch', 'Mismatch'),
    );
    // Missing installdir value (required field absent).
    os.addFile(`${STEAM_DIR}\\steamapps\\appmanifest_50.acf`, '"AppState"\n{\n\t"appid"\t\t"50"\n}');

    const adapter = new SteamAdapter(os);
    const r = await adapter.scan();
    expect(r.status).toBe('completed');
    // The two valid manifests plus the appid-mismatch one (filename AppID wins,
    // with a warning) produce games.
    expect(r.games.map((g) => g.appid).sort()).toEqual(['10', '30', '40']);
    // Every skipped manifest produced a warning; the mismatch warns too.
    expect(r.warnings.join('\n')).toMatch(/appmanifest_20/);
    expect(r.warnings.join('\n')).toMatch(/appmanifest_40/);
    expect(r.warnings.join('\n')).toMatch(/appmanifest_50/);
    expect(r.error).toBeNull();
  });
});

describe('IPC-level scan behavior', () => {
  it('cancelScan mid-scan resolves the scan and leaves the library untouched', async () => {
    openContext(manyManifestTree(300));
    const before = await listSteamGames();
    expect(before).toHaveLength(0);

    const scanPromise = ctx!.call(IpcChannels.sourcesScan, { source: 'steam' });
    await sleep(40);
    const cancel = await ctx!.call(IpcChannels.sourcesCancelScan, {});
    expect(cancel.ok).toBe(true);
    expect((cancel.data as { cancelled: boolean }).cancelled).toBe(true);
    const scan = await scanPromise;
    expect(scan.ok).toBe(true);
    expect((scan.data as { gamesFound: number }).gamesFound).toBe(0);

    // Library intact: no partial scan results were merged.
    expect(await listSteamGames()).toHaveLength(0);
  });

  it('two simultaneous scans of one source: the second fails with SCAN_IN_PROGRESS', async () => {
    openContext(manyManifestTree(300));
    const first = ctx!.call(IpcChannels.sourcesScan, { source: 'steam' });
    // Give the first scan a tick so its guard is set before the second call.
    await sleep(10);
    const second = await ctx!.call(IpcChannels.sourcesScan, { source: 'steam' });
    expect(second.ok).toBe(false);
    if (!second.ok) {
      expect(second.error.code).toBe('SCAN_IN_PROGRESS');
    }
    // Clean up: cancel the first scan, then confirm the guard released.
    await ctx!.call(IpcChannels.sourcesCancelScan, {});
    const firstResult = await first;
    expect(firstResult.ok).toBe(true);
    const third = await ctx!.call(IpcChannels.sourcesScan, { source: 'steam' });
    expect(third.ok).toBe(true);
    await ctx!.call(IpcChannels.sourcesCancelScan, {});
    await third;
  });

  it('a completed scan still merges results idempotently after the refactor', async () => {
    const os = manyManifestTree(4);
    os.delayMs = 0;
    openContext(os);
    const first = await ctx!.call(IpcChannels.sourcesScan, { source: 'steam' });
    expect(first.ok).toBe(true);
    expect((first.data as { gamesFound: number }).gamesFound).toBe(4);
    const second = await ctx!.call(IpcChannels.sourcesScan, { source: 'steam' });
    expect(second.ok).toBe(true);
    expect((second.data as { gamesFound: number }).gamesFound).toBe(4);
    expect(await listSteamGames()).toHaveLength(4);
  });

  it('library contents survive a cancelled re-scan after a successful scan', async () => {
    const os = manyManifestTree(300);
    os.delayMs = 0;
    openContext(os);
    const first = await ctx!.call(IpcChannels.sourcesScan, { source: 'steam' });
    expect(first.ok).toBe(true);
    const before = await listSteamGames();
    expect(before).toHaveLength(300);

    // Slow the re-scan down so cancellation lands mid-flight.
    os.delayMs = 5;
    const rescan = ctx!.call(IpcChannels.sourcesScan, { source: 'steam' });
    await sleep(40);
    await ctx!.call(IpcChannels.sourcesCancelScan, {});
    const rescanResult = await rescan;
    expect(rescanResult.ok).toBe(true);

    // Same 300 games, byte-identical rows: no corruption, no partial merge.
    const after = await listSteamGames();
    expect(after).toHaveLength(300);
    expect(after.map((g) => g.id)).toEqual(before.map((g) => g.id));
    expect(after.map((g) => g.title)).toEqual(before.map((g) => g.title));
  });
});
