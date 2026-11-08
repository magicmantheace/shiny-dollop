/** DB-level tests for Steam sync: idempotency, edit preservation, missing flips. */
import { afterEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import type { DatabaseSync } from 'node:sqlite';
import { openDatabase } from '../../electron/main/data/database';
import { getGame, listGames, setFavorite } from '../../electron/main/data/games';
import { syncSteamGames, type DiscoveredGame } from '../../electron/main/sources/steam/sync';

let db: DatabaseSync | null = null;
const tmpDirs: string[] = [];

afterEach(() => {
  db?.close();
  db = null;
  for (const d of tmpDirs.splice(0)) {
    fs.rmSync(d, { recursive: true, force: true });
  }
});

function memDb(): DatabaseSync {
  db = openDatabase(':memory:');
  return db;
}

function discovered(appid: string, title: string, installDir: string): DiscoveredGame {
  return { appid, title, installDir, present: fs.existsSync(installDir) };
}

describe('syncSteamGames', () => {
  it('inserts new games and is idempotent on re-scan', () => {
    const d = memDb();
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ugl-'));
    tmpDirs.push(dir);
    const found = [discovered('730', 'Counter-Strike 2', dir)];
    expect(syncSteamGames(d, found)).toMatchObject({ added: 1, updated: 0 });
    expect(syncSteamGames(d, found)).toMatchObject({ added: 0, updated: 1 });
    expect(listGames(d, { source: 'steam' })).toHaveLength(1);
  });

  it('computes missing from install_dir existence on the real filesystem', () => {
    const d = memDb();
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ugl-'));
    tmpDirs.push(dir);
    syncSteamGames(d, [discovered('730', 'CS2', dir)]);
    const game = listGames(d, { source: 'steam' })[0]!;
    expect(game.missing).toBe(false);
    expect(game.installDir).toBe(dir);

    fs.rmSync(dir, { recursive: true, force: true });
    const gone = getGame(d, game.id)!;
    expect(gone.missing).toBe(true);
  });

  it('never overwrites user-owned columns on re-scan', () => {
    const d = memDb();
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ugl-'));
    tmpDirs.push(dir);
    syncSteamGames(d, [discovered('730', 'Counter-Strike 2', dir)]);
    const game = listGames(d, { source: 'steam' })[0]!;
    setFavorite(d, game.id, true);
    // Manifest renamed the game; re-scan must keep the user's title.
    const updated = getGame(d, game.id)!;
    d.prepare('UPDATE games SET title = ? WHERE id = ?').run('My CS2', game.id);
    void updated;
    syncSteamGames(d, [discovered('730', 'Counter-Strike 2 Renamed', dir)]);
    const kept = getGame(d, game.id)!;
    expect(kept.title).toBe('My CS2');
    expect(kept.favorite).toBe(true);
    // But scanner-owned columns refresh.
    expect(kept.launchUri).toBe('steam://rungameid/730');
    expect(kept.launchCapability).toBe('native-uri');
  });

  it('keeps rows for games absent from discovery (history preserved)', () => {
    const d = memDb();
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ugl-'));
    tmpDirs.push(dir);
    syncSteamGames(d, [discovered('730', 'CS2', dir), discovered('440', 'TF2', dir)]);
    const result = syncSteamGames(d, [discovered('730', 'CS2', dir)]);
    expect(result.untouched).toBe(1);
    expect(listGames(d, { source: 'steam' })).toHaveLength(2);
  });

  it('rejects an invalid appid instead of writing a bad row', () => {
    const d = memDb();
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ugl-'));
    tmpDirs.push(dir);
    expect(() => syncSteamGames(d, [discovered('not-an-id', 'Evil', dir)])).toThrow();
    expect(listGames(d, { source: 'steam' })).toHaveLength(0);
  });
});
