/** SQLite schema migrations. Applied in order; each runs at most once. */
import type { DatabaseSync } from 'node:sqlite';

interface Migration {
  version: number;
  name: string;
  sql: string;
}

const MIGRATIONS: Migration[] = [
  {
    version: 1,
    name: 'initial library schema',
    sql: `
      CREATE TABLE games (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL DEFAULT 'manual',
        external_id TEXT,
        title TEXT NOT NULL,
        exe_path TEXT,
        canonical_path TEXT,
        working_dir TEXT,
        args_json TEXT NOT NULL DEFAULT '[]',
        favorite INTEGER NOT NULL DEFAULT 0,
        hidden INTEGER NOT NULL DEFAULT 0,
        added_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_played_at TEXT,
        total_play_ms INTEGER NOT NULL DEFAULT 0,
        UNIQUE(source, canonical_path)
      );
      CREATE INDEX idx_games_title ON games(title COLLATE NOCASE);
      CREATE INDEX idx_games_favorite ON games(favorite);
      CREATE TABLE sessions (
        id TEXT PRIMARY KEY,
        game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        duration_ms INTEGER,
        state TEXT NOT NULL DEFAULT 'running',
        tracking_method TEXT NOT NULL DEFAULT 'observed',
        last_checkpoint_at TEXT,
        notes TEXT
      );
      CREATE INDEX idx_sessions_game ON sessions(game_id);
      CREATE INDEX idx_sessions_started ON sessions(started_at);
      CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      );
      CREATE TABLE scan_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        scanned_at TEXT NOT NULL,
        status TEXT NOT NULL,
        games_found INTEGER NOT NULL DEFAULT 0,
        error TEXT
      );
    `,
  },
  {
    version: 2,
    name: 'steam source columns',
    sql: `
      ALTER TABLE games ADD COLUMN install_dir TEXT;
      ALTER TABLE games ADD COLUMN launch_uri TEXT;
      ALTER TABLE games ADD COLUMN launch_capability TEXT;
      ALTER TABLE games ADD COLUMN launch_reason TEXT;
      CREATE UNIQUE INDEX idx_games_source_external ON games(source, external_id);
    `,
  },
];

export function getAppliedVersions(db: DatabaseSync): number[] {
  db.exec(
    'CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)',
  );
  const rows = db
    .prepare('SELECT version FROM schema_version ORDER BY version')
    .all() as { version: number }[];
  return rows.map((r) => r.version);
}

export function runMigrations(db: DatabaseSync): number[] {
  const applied = new Set(getAppliedVersions(db));
  const now = new Date().toISOString();
  for (const m of MIGRATIONS) {
    if (applied.has(m.version)) continue;
    db.exec('BEGIN');
    try {
      db.exec(m.sql);
      db.prepare('INSERT INTO schema_version (version, applied_at) VALUES (?, ?)').run(
        m.version,
        now,
      );
      db.exec('COMMIT');
    } catch (err) {
      db.exec('ROLLBACK');
      throw err;
    }
  }
  return getAppliedVersions(db);
}
