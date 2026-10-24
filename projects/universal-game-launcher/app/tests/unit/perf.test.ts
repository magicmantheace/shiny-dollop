/** Performance sanity: the library stays responsive with 500+ entries. */
import { afterEach, describe, expect, it } from 'vitest';
import type { DatabaseSync } from 'node:sqlite';
import { openDatabase } from '../../electron/main/data/database';
import { runMigrations } from '../../electron/main/data/migrations';
import { listGames } from '../../electron/main/data/games';

let db: DatabaseSync | null = null;
afterEach(() => {
  db?.close();
  db = null;
});

describe('library performance', () => {
  it('lists and filters 500 games quickly', () => {
    db = openDatabase(':memory:');
    runMigrations(db);
    const stmt = db.prepare(
      `INSERT INTO games (id, source, title, exe_path, canonical_path, favorite, added_at, updated_at, total_play_ms)
       VALUES (?, 'manual', ?, ?, ?, ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', ?)`,
    );
    db.exec('BEGIN');
    for (let i = 0; i < 500; i++) {
      stmt.run(
        `game-${i}`,
        `Game ${String(i).padStart(3, '0')}`,
        `/games/game-${i}/game.exe`,
        `/games/game-${i}/game.exe`,
        i % 7 === 0 ? 1 : 0,
        i * 1000,
      );
    }
    db.exec('COMMIT');

    const t0 = Date.now();
    const all = listGames(db, {});
    const tList = Date.now() - t0;
    expect(all).toHaveLength(500);

    const t1 = Date.now();
    const filtered = listGames(db, { search: 'Game 4', favoritesOnly: false, sort: 'playtime' });
    const tFilter = Date.now() - t1;
    expect(filtered.length).toBeGreaterThan(0);
    // Generous bounds for CI slowness — the point is no pathological blowup.
    expect(tList).toBeLessThan(1000);
    expect(tFilter).toBeLessThan(1000);
  });
});
