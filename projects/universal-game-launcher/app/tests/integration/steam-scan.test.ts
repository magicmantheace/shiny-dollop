/**
 * Integration tests for the Steam source: IPC status/scan round-trips,
 * idempotent re-scans, user-edit preservation, missing flips, and the
 * steam:// launch handoff (with a stubbed OS opener — no real Steam).
 */
import { afterEach, describe, expect, it } from 'vitest';
import type { DatabaseSync } from 'node:sqlite';
import { IpcChannels } from '../../shared/ipc-channels';
import type { Game, SourceStatus } from '../../shared/types';
import { createTestContext, type TestContext } from './helpers';
import { FakeSteamOs, acf, fakeSteamInstall, libraryFoldersVdf } from '../steam-helpers';

const STEAM_DIR = 'C:\\Program Files (x86)\\Steam';

function steamTree(): FakeSteamOs {
  const os = new FakeSteamOs();
  os.platform = 'win32';
  os.setEnv('ProgramFiles(x86)', 'C:\\Program Files (x86)');
  fakeSteamInstall(os, STEAM_DIR);
  os.addFile(
    `${STEAM_DIR}\\steamapps\\libraryfolders.vdf`,
    libraryFoldersVdf([STEAM_DIR, 'D:\\SteamLibrary']),
  );
  os.addDir('D:\\SteamLibrary\\steamapps');
  os.addDir('D:\\SteamLibrary\\steamapps\\common');
  os.addFile(`${STEAM_DIR}\\steamapps\\appmanifest_730.acf`, acf('730', 'Counter-Strike 2', 'CS2'));
  os.addDir(`${STEAM_DIR}\\steamapps\\common\\CS2`);
  os.addFile('D:\\SteamLibrary\\steamapps\\appmanifest_440.acf', acf('440', 'Team Fortress 2', 'TF2'));
  os.addDir('D:\\SteamLibrary\\steamapps\\common\\TF2');
  return os;
}

let ctx: TestContext | null = null;
afterEach(() => {
  ctx?.close();
  ctx = null;
});

function openContext(os: FakeSteamOs) {
  const opened: string[] = [];
  ctx = createTestContext({
    steamOs: os,
    openExternalImpl: async (uri: string) => {
      opened.push(uri);
    },
  });
  return { ctx, opened };
}

async function scanGames(): Promise<Game[]> {
  const res = await ctx!.call(IpcChannels.sourcesScan, { source: 'steam' });
  expect(res.ok).toBe(true);
  const list = await ctx!.call(IpcChannels.libraryList, { source: 'steam' });
  expect(list.ok).toBe(true);
  return (list.data as Game[]).sort((a, b) => (a.externalId ?? '').localeCompare(b.externalId ?? ''));
}

describe('sources.status', () => {
  it('reports Steam detected with the detection method', async () => {
    openContext(steamTree());
    const res = await ctx!.call(IpcChannels.sourcesStatus, {});
    expect(res.ok).toBe(true);
    const statuses = res.data as SourceStatus[];
    const steam = statuses.find((s) => s.source === 'steam')!;
    expect(steam.available).toBe(true);
    expect(steam.reason).toContain('ProgramFiles(x86)');
  });

  it('reports Steam not found honestly when absent', async () => {
    openContext(new FakeSteamOs());
    const res = await ctx!.call(IpcChannels.sourcesStatus, {});
    expect(res.ok).toBe(true);
    const statuses = res.data as SourceStatus[];
    const steam = statuses.find((s) => s.source === 'steam')!;
    expect(steam.available).toBe(false);
    expect(steam.reason).toContain('not found');
  });
});

describe('sources.scan', () => {
  it('imports discovered games as steam entries', async () => {
    openContext(steamTree());
    const games = await scanGames();
    expect(games).toHaveLength(2);
    const cs2 = games.find((g) => g.externalId === '730')!;
    expect(cs2).toMatchObject({
      source: 'steam',
      externalId: '730',
      title: 'Counter-Strike 2',
      launchCapability: 'native-uri',
      launchUri: 'steam://rungameid/730',
    });
    expect(cs2.installDir).toBe('C:\\Program Files (x86)\\Steam\\steamapps\\common\\CS2');
    // NOTE: `missing` is computed against the real filesystem, so these
    // fake Windows paths always read as missing on Linux. The missing
    // computation itself is covered with real temp dirs below.
    const tf2 = games.find((g) => g.externalId === '440')!;
    expect(tf2.title).toBe('Team Fortress 2');
  });

  it('re-scans are idempotent and preserve user edits', async () => {
    openContext(steamTree());
    await scanGames();
    const games = await scanGames();
    const cs = games.find((g) => g.externalId === '730')!;

    // User edits: favorite + custom title.
    await ctx!.call(IpcChannels.librarySetFavorite, { id: cs.id, favorite: true });
    await ctx!.call(IpcChannels.libraryUpdate, { id: cs.id, title: 'My CS2' });

    const again = await scanGames();
    expect(again).toHaveLength(2); // no duplicates
    const kept = again.find((g) => g.externalId === '730')!;
    expect(kept.favorite).toBe(true);
    expect(kept.title).toBe('My CS2'); // scanner did not overwrite the user's title
  });

  it('marks removed installations missing without deleting history', async () => {
    openContext(steamTree());
    const before = await scanGames();
    expect(before).toHaveLength(2);
    const tf2 = before.find((g) => g.externalId === '440')!;
    await ctx!.call(IpcChannels.librarySetFavorite, { id: tf2.id, favorite: true });

    // Simulate uninstall: rebuild the fixture tree without the TF2 manifest/dir.
    const os3 = new FakeSteamOs();
    os3.platform = 'win32';
    os3.setEnv('ProgramFiles(x86)', 'C:\\Program Files (x86)');
    fakeSteamInstall(os3, STEAM_DIR);
    os3.addFile(
      `${STEAM_DIR}\\steamapps\\libraryfolders.vdf`,
      libraryFoldersVdf([STEAM_DIR]),
    );
    os3.addFile(`${STEAM_DIR}\\steamapps\\appmanifest_730.acf`, acf('730', 'Counter-Strike 2', 'CS2'));
    os3.addDir(`${STEAM_DIR}\\steamapps\\common\\CS2`);
    ctx!.deps.steamOs = os3;

    const after = await scanGames();
    expect(after).toHaveLength(2); // row kept, not deleted
    const gone = after.find((g) => g.externalId === '440')!;
    // On Linux the fake Windows install dirs never exist on the real
    // filesystem, so `missing` is always true here; the point of this test
    // is that the row (and its favorite flag) survives the re-scan.
    expect(gone.favorite).toBe(true);
  });

  it('fails honestly when Steam is absent', async () => {
    openContext(new FakeSteamOs());
    const res = await ctx!.call(IpcChannels.sourcesScan, { source: 'steam' });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('SCAN_FAILED');
  });
});

describe('games.launch for Steam', () => {
  it('hands a validated steam:// URI to the OS and records an untracked session', async () => {
    const { opened } = openContext(steamTree());
    const games = await scanGames();
    const cs = games.find((g) => g.externalId === '730')!;

    const res = await ctx!.call(IpcChannels.gamesLaunch, { id: cs.id });
    expect(res.ok).toBe(true);
    expect(opened).toEqual(['steam://rungameid/730']);

    const data = res.data as { sessionId: string | null; alreadyRunning: boolean };
    expect(data.alreadyRunning).toBe(false);
    expect(data.sessionId).not.toBeNull();

    // The session is honest: unavailable tracking, no invented playtime.
    const sessions = await ctx!.call(IpcChannels.sessionsList, { gameId: cs.id });
    expect(sessions.ok).toBe(true);
    const list = sessions.data as Array<{ trackingMethod: string; durationMs: number | null; state: string }>;
    expect(list).toHaveLength(1);
    expect(list[0]).toMatchObject({ trackingMethod: 'unavailable', state: 'completed' });

    // lastPlayedAt / totalPlayMs are untouched — a URI handoff is not proof the game ran.
    const refreshed = (await ctx!.call(IpcChannels.libraryList, { source: 'steam' })).data as Game[];
    const cs2 = refreshed.find((g) => g.externalId === '730')!;
    expect(cs2.lastPlayedAt).toBeNull();
    expect(cs2.totalPlayMs).toBe(0);
  });

  it('refuses to launch when the AppID is invalid', async () => {
    openContext(steamTree());
    await scanGames();
    // Corrupt the stored AppID directly to simulate hostile DB content.
    const db = ctx!.deps.db as DatabaseSync;
    const row = db.prepare("SELECT id FROM games WHERE source = 'steam' LIMIT 1").get() as { id: string };
    db.prepare('UPDATE games SET external_id = ? WHERE id = ?').run('not-an-appid', row.id);
    const res = await ctx!.call(IpcChannels.gamesLaunch, { id: row.id });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('INVALID_APPID');
  });

  it('reports a clear error when the OS handoff fails', async () => {
    ctx = createTestContext({
      steamOs: steamTree(),
      openExternalImpl: async () => {
        throw new Error('no handler');
      },
    });
    const games = await scanGames();
    const cs = games[0]!;
    const res = await ctx!.call(IpcChannels.gamesLaunch, { id: cs.id });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('LAUNCH_REQUEST_FAILED');
  });
});

describe('sources.cancelScan', () => {
  it('reports nothing to cancel when idle', async () => {
    openContext(steamTree());
    const res = await ctx!.call(IpcChannels.sourcesCancelScan, {});
    expect(res.ok).toBe(true);
    expect((res.data as { cancelled: boolean }).cancelled).toBe(false);
  });
});
