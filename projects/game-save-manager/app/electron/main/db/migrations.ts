/**
 * Schema migrations. Each migration is a versioned, idempotent step;
 * the schema_migrations table records what has already been applied.
 */
import type { DatabaseSync } from 'node:sqlite';

interface Migration {
  version: number;
  description: string;
  sql: string;
}

const MIGRATIONS: Migration[] = [
  {
    version: 1,
    description: 'initial schema: games, backups, backup_files, schedules',
    sql: `
      CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        save_path TEXT NOT NULL,
        source TEXT NOT NULL,
        created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        label TEXT,
        file_count INTEGER NOT NULL,
        total_bytes INTEGER NOT NULL,
        backup_dir TEXT NOT NULL,
        notes TEXT
      );
      CREATE TABLE IF NOT EXISTS backup_files (
        backup_id INTEGER NOT NULL REFERENCES backups(id) ON DELETE CASCADE,
        rel_path TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        PRIMARY KEY (backup_id, rel_path)
      );
      CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER NOT NULL UNIQUE REFERENCES games(id) ON DELETE CASCADE,
        interval_minutes INTEGER NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        last_run_at TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_backups_game_id ON backups(game_id);
      CREATE INDEX IF NOT EXISTS idx_backups_game_created ON backups(game_id, created_at);
    `,
  },
];

function ensureMigrationsTable(db: DatabaseSync): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      version INTEGER PRIMARY KEY,
      applied_at TEXT NOT NULL
    );
  `);
}

export function getAppliedVersions(db: DatabaseSync): number[] {
  ensureMigrationsTable(db);
  const rows = db.prepare('SELECT version FROM schema_migrations ORDER BY version').all() as {
    version: number;
  }[];
  return rows.map((r) => r.version);
}

/** Apply every migration that has not been applied yet. Idempotent. */
export function runMigrations(db: DatabaseSync): void {
  ensureMigrationsTable(db);
  const applied = new Set(getAppliedVersions(db));
  for (const m of MIGRATIONS) {
    if (applied.has(m.version)) continue;
    db.exec(m.sql);
    db.prepare('INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)').run(
      m.version,
      new Date().toISOString(),
    );
  }
}
