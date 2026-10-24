import { describe, expect, it } from 'vitest';
import { openDatabase } from '../../electron/main/db/database';
import { getAppliedVersions, runMigrations } from '../../electron/main/db/migrations';

describe('migrations', () => {
  it('creates the games/backups/backup_files/schedules tables on a fresh database', () => {
    const db = openDatabase(':memory:');
    try {
      expect(getAppliedVersions(db)).toEqual([1]);
      const tables = db
        .prepare("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
        .all() as { name: string }[];
      const names = tables.map((t) => t.name);
      for (const t of ['games', 'backups', 'backup_files', 'schedules', 'schema_migrations']) {
        expect(names).toContain(t);
      }
      const gameCols = (
        db.prepare('PRAGMA table_info(games)').all() as { name: string }[]
      ).map((c) => c.name);
      for (const c of ['id', 'name', 'save_path', 'source', 'created_at']) {
        expect(gameCols).toContain(c);
      }
      const backupCols = (
        db.prepare('PRAGMA table_info(backups)').all() as { name: string }[]
      ).map((c) => c.name);
      for (const c of ['id', 'game_id', 'created_at', 'label', 'file_count', 'total_bytes', 'backup_dir', 'notes']) {
        expect(backupCols).toContain(c);
      }
    } finally {
      db.close();
    }
  });

  it('is idempotent: re-running migrations changes nothing', () => {
    const db = openDatabase(':memory:');
    try {
      const before = getAppliedVersions(db);
      runMigrations(db);
      runMigrations(db);
      expect(getAppliedVersions(db)).toEqual(before);
    } finally {
      db.close();
    }
  });
});
