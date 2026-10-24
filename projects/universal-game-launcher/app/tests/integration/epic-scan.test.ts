/**
 * Integration tests for the Epic source: IPC status/scan round-trips,
 * idempotent re-scans, user-edit preservation, and the open-client launch
 * handoff (with a stubbed OS opener — no real Epic client).
 */
import { afterEach, describe, expect, it } from 'vitest';
import { IpcChannels } from '../../shared/ipc-channels';
import type { Game, SourceStatus } from '../../shared/types';
import { createTestContext, type TestContext } from './helpers';
import { FakeEpicOs, fakeEpicInstall, itemManifest } from '../epic-helpers';

function epicTree(): FakeEpicOs {
  const os = new FakeEpicOs();
  os.platform = 'win32';
  fakeEpicInstall(os);
  const dir = 'C:\\ProgramData\\Epic\\EpicGamesLauncher\\Data\\Manifests';
  os.addFile(
    `${dir}\\deadbeef1234.cafef00d5678.item`,
    itemManifest({ AppName: 'Fortnite', DisplayName: 'Fortnite' }),
  );
  os.addDir('C:\\Program Files\\Epic Games\\Fortnite');
  os.addFile(
    `${dir}\\aaaabbbb.ccccdddd.item`,
    itemManifest({
      AppName: 'RocketLeague',
      DisplayName: 'Rocket League',
      InstallLocation: 'D:\\Games\\RocketLeague',
    }),
  );
  return os;
}

let ctx: TestContext | null = null;
afterEach(() => {
  ctx?.close();
  ctx = null;
});

function openContext(os: FakeEpicOs) {
  const opened: string[] = [];
  ctx = createTestContext({
    epicOs: os,
    openExternalImpl: async (uri: string) => {
      opened.push(uri);
    },
  });
  return { ctx, opened };
}

async function scanGames(): Promise<Game[]> {
  const res = await ctx!.call(IpcChannels.sourcesScan, { source: 'epic' });
  expect(res.ok).toBe(true);
  const list = await ctx!.call(IpcChannels.libraryList, { source: 'epic' });
  expect(list.ok).toBe(true);
  return (list.data as Game[]).sort((a, b) => (a.externalId ?? '').localeCompare(b.externalId ?? ''));
}

describe('sources.status', () => {
  it('reports Epic detected with the detection method', async () => {
    openContext(epicTree());
    const res = await ctx!.call(IpcChannels.sourcesStatus, {});
    expect(res.ok).toBe(true);
    const epic = (res.data as SourceStatus[]).find((s) => s.source === 'epic')!;
    expect(epic.available).toBe(true);
    expect(epic.reason).toContain('ProgramData');
  });

  it('reports Epic not found honestly when absent', async () => {
    openContext(new FakeEpicOs());
    const res = await ctx!.call(IpcChannels.sourcesStatus, {});
    expect(res.ok).toBe(true);
    const epic = (res.data as SourceStatus[]).find((s) => s.source === 'epic')!;
    expect(epic.available).toBe(false);
    expect(epic.reason).toContain('not found');
  });
});

describe('sources.scan', () => {
  it('imports discovered items as epic entries with open-client capability', async () => {
    openContext(epicTree());
    const games = await scanGames();
    expect(games).toHaveLength(2);
    const fn = games.find((g) => g.externalId === 'Fortnite')!;
    expect(fn).toMatchObject({
      source: 'epic',
      title: 'Fortnite',
      launchCapability: 'open-client',
      launchUri: 'com.epicgames.launcher://',
    });
    expect(fn.installDir).toBe('C:\\Program Files\\Epic Games\\Fortnite');
  });

  it('re-scans are idempotent and preserve user edits', async () => {
    openContext(epicTree());
    await scanGames();
    const games = await scanGames();
    const fn = games.find((g) => g.externalId === 'Fortnite')!;
    await ctx!.call(IpcChannels.librarySetFavorite, { id: fn.id, favorite: true });
    await ctx!.call(IpcChannels.libraryUpdate, { id: fn.id, title: 'My FN' });

    const again = await scanGames();
    expect(again).toHaveLength(2);
    const kept = again.find((g) => g.externalId === 'Fortnite')!;
    expect(kept.favorite).toBe(true);
    expect(kept.title).toBe('My FN');
  });

  it('fails honestly when Epic is absent', async () => {
    openContext(new FakeEpicOs());
    const res = await ctx!.call(IpcChannels.sourcesScan, { source: 'epic' });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('SCAN_FAILED');
  });

  it('a failed Epic scan does not touch Steam rows', async () => {
    openContext(new FakeEpicOs());
    // Seed a steam row directly.
    const db = ctx!.deps.db;
    db.prepare(
      `INSERT INTO games (id, source, external_id, title, added_at, updated_at)
       VALUES ('s1', 'steam', '730', 'CS2', '2026-01-01', '2026-01-01')`,
    ).run();
    const res = await ctx!.call(IpcChannels.sourcesScan, { source: 'epic' });
    expect(res.ok).toBe(false);
    const list = await ctx!.call(IpcChannels.libraryList, { source: 'steam' });
    expect(list.ok).toBe(true);
    expect((list.data as Game[])).toHaveLength(1);
  });
});

describe('games.launch for Epic', () => {
  it('opens the Epic Games Launcher and records an untracked session', async () => {
    const { opened } = openContext(epicTree());
    const games = await scanGames();
    const fn = games.find((g) => g.externalId === 'Fortnite')!;

    const res = await ctx!.call(IpcChannels.gamesLaunch, { id: fn.id });
    expect(res.ok).toBe(true);
    expect(opened).toEqual(['com.epicgames.launcher://']);

    const data = res.data as { sessionId: string | null; alreadyRunning: boolean };
    expect(data.alreadyRunning).toBe(false);
    expect(data.sessionId).not.toBeNull();

    const sessions = await ctx!.call(IpcChannels.sessionsList, { gameId: fn.id });
    const list = sessions.data as Array<{ trackingMethod: string; state: string }>;
    expect(list).toHaveLength(1);
    expect(list[0]).toMatchObject({ trackingMethod: 'unavailable', state: 'completed' });

    // No invented playtime: a launcher handoff is not proof the game ran.
    const refreshed = (await ctx!.call(IpcChannels.libraryList, { source: 'epic' })).data as Game[];
    const again = refreshed.find((g) => g.externalId === 'Fortnite')!;
    expect(again.lastPlayedAt).toBeNull();
    expect(again.totalPlayMs).toBe(0);
  });

  it('refuses when the stored URI is not the verified launcher scheme', async () => {
    openContext(epicTree());
    const games = await scanGames();
    const fn = games[0]!;
    const db = ctx!.deps.db;
    db.prepare('UPDATE games SET launch_uri = ? WHERE id = ?').run('com.epicgames.launcher://evil', fn.id);
    const res = await ctx!.call(IpcChannels.gamesLaunch, { id: fn.id });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('INVALID_LAUNCH_URI');
  });
});
