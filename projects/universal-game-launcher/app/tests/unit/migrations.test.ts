import { describe, expect, it } from 'vitest';
import { openDatabase } from '../../electron/main/data/database';
import { getAppliedVersions, runMigrations } from '../../electron/main/data/migrations';

describe('migrations', () => {
  it('applies all migrations to a fresh database', () => {
    const db = openDatabase(':memory:');
    try {
      expect(getAppliedVersions(db)).toEqual([1, 2]);
      const tables = db
        .prepare("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
        .all() as { name: string }[];
      const names = tables.map((t) => t.name);
      expect(names).toContain('games');
      expect(names).toContain('sessions');
      expect(names).toContain('settings');
      expect(names).toContain('scan_log');
      // v2: steam source columns + dedup index.
      const cols = db.prepare('PRAGMA table_info(games)').all() as { name: string }[];
      const colNames = cols.map((c) => c.name);
      for (const c of ['install_dir', 'launch_uri', 'launch_capability', 'launch_reason']) {
        expect(colNames).toContain(c);
      }
      const indexes = db
        .prepare("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'games'")
        .all() as { name: string }[];
      expect(indexes.map((i) => i.name)).toContain('idx_games_source_external');
    } finally {
      db.close();
    }
  });

  it('is idempotent: re-running changes nothing', () => {
    const db = openDatabase(':memory:');
    try {
      const before = getAppliedVersions(db);
      db.prepare('INSERT INTO games (id, title, added_at, updated_at) VALUES (?, ?, ?, ?)').run(
        'g1',
        'Test',
        new Date().toISOString(),
        new Date().toISOString(),
      );
      expect(runMigrations(db)).toEqual(before);
      const count = (db.prepare('SELECT COUNT(*) AS c FROM games').get() as { c: number }).c;
      expect(count).toBe(1);
    } finally {
      db.close();
    }
  });
});
