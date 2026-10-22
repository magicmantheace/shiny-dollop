/** Unit tests for the Epic scan→library merge: idempotent, user edits preserved. */
import { afterEach, describe, expect, it } from 'vitest';
import type { DatabaseSync } from 'node:sqlite';
import { openDatabase } from '../../electron/main/data/database';
import { runMigrations } from '../../electron/main/data/migrations';
import { listGames } from '../../electron/main/data/games';
import { syncEpicGames } from '../../electron/main/sources/epic/sync';
import type { DiscoveredGame } from '../../electron/main/sources/epic/adapter';

let db: DatabaseSync | null = null;
afterEach(() => {
  db?.close();
  db = null;
});

function testDb(): DatabaseSync {
  db = openDatabase(':memory:');
  runMigrations(db);
  return db;
}

const FORTNITE: DiscoveredGame = {
  appName: 'Fortnite',
  title: 'Fortnite',
  installLocation: 'C:\\Program Files\\Epic Games\\Fortnite',
  present: true,
};

describe('syncEpicGames', () => {
  it('inserts discovered games with open-client capability', () => {
    const d = testDb();
    const r = syncEpicGames(d, [FORTNITE]);
    expect(r).toMatchObject({ added: 1, updated: 0 });
    const games = listGames(d, { source: 'epic' });
    expect(games).toHaveLength(1);
    expect(games[0]).toMatchObject({
      source: 'epic',
      externalId: 'Fortnite',
      title: 'Fortnite',
      launchCapability: 'open-client',
      launchUri: 'com.epicgames.launcher://',
    });
    expect(games[0]!.launchReason).toContain('not verified');
  });

  it('re-scans are idempotent and preserve user edits', () => {
    const d = testDb();
    syncEpicGames(d, [FORTNITE]);
    const before = listGames(d, { source: 'epic' })[0]!;
    d.prepare('UPDATE games SET favorite = 1, title = ? WHERE id = ?').run('My FN', before.id);

    const r = syncEpicGames(d, [{ ...FORTNITE, title: 'Fortnite' }]);
    expect(r).toMatchObject({ added: 0, updated: 1 });
    const after = listGames(d, { source: 'epic' });
    expect(after).toHaveLength(1);
    expect(after[0]!.favorite).toBe(true);
    expect(after[0]!.title).toBe('My FN');
  });

  it('keeps rows for items missing from a later scan', () => {
    const d = testDb();
    syncEpicGames(d, [FORTNITE]);
    const r = syncEpicGames(d, []);
    expect(r.untouched).toBe(1);
    expect(listGames(d, { source: 'epic' })).toHaveLength(1);
  });
});
