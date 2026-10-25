/**
 * Schema migrations. Each migration is a versioned, idempotent step;
 * the schema_migrations table records what has already been applied,
 * so re-running is always safe.
 */
import type { DatabaseSync } from 'node:sqlite';
import { normalizeForSearch } from './normalize';

interface Migration {
  version: number;
  description: string;
  sql: string;
}

const MIGRATIONS: Migration[] = [
  {
    version: 1,
    description: 'initial schema: scans, files, scan_errors',
    sql: `
      CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        root_path TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'running'
          CHECK (state IN ('running','cancelled','complete','failed')),
        files INTEGER NOT NULL DEFAULT 0,
        dirs INTEGER NOT NULL DEFAULT 0,
        bytes INTEGER NOT NULL DEFAULT 0,
        excluded_count INTEGER NOT NULL DEFAULT 0,
        symlink_count INTEGER NOT NULL DEFAULT 0,
        changed_count INTEGER NOT NULL DEFAULT 0,
        error_count INTEGER NOT NULL DEFAULT 0,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        error TEXT
      );
      CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
        path TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        sha256 TEXT,
        is_symlink INTEGER NOT NULL DEFAULT 0,
        UNIQUE(scan_id, path)
      );
      CREATE INDEX IF NOT EXISTS files_scan_size ON files(scan_id, size_bytes);
      CREATE INDEX IF NOT EXISTS files_scan_sha ON files(scan_id, sha256);
      CREATE TABLE IF NOT EXISTS scan_errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
        path TEXT NOT NULL,
        code TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS scan_errors_scan ON scan_errors(scan_id);
    `,
  },
  {
    version: 2,
    description:
      'files: hard-link identity (dev, ino) and Unicode-normalized search key (path_search)',
    sql: `
      ALTER TABLE files ADD COLUMN dev INTEGER;
      ALTER TABLE files ADD COLUMN ino INTEGER;
      ALTER TABLE files ADD COLUMN path_search TEXT;
      CREATE INDEX IF NOT EXISTS files_scan_search ON files(scan_id, path_search);
    `,
  },
];

export const SCHEMA_VERSION = MIGRATIONS.length;

export function runMigrations(db: DatabaseSync): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      version INTEGER PRIMARY KEY,
      description TEXT NOT NULL,
      applied_at TEXT NOT NULL
    );
  `);
  const applied = new Set<number>(
    db
      .prepare('SELECT version FROM schema_migrations')
      .all()
      .map((row) => (row as { version: number }).version),
  );
  const markApplied = db.prepare(
    'INSERT INTO schema_migrations (version, description, applied_at) VALUES (?, ?, ?)',
  );
  for (const migration of MIGRATIONS) {
    if (applied.has(migration.version)) continue;
    db.exec(migration.sql);
    markApplied.run(migration.version, migration.description, new Date().toISOString());
  }
  backfillFileSearchKeys(db);
}

/**
 * Fill `path_search` for rows recorded before migration v2 (or by any
 * path that left it null) using the same JS normalization queries use —
 * SQLite's lower() cannot do this, it folds ASCII only. Idempotent:
 * rows that already have a key are untouched.
 */
function backfillFileSearchKeys(db: DatabaseSync): void {
  const rows = db
    .prepare('SELECT id, path FROM files WHERE path_search IS NULL')
    .all() as Array<{ id: number; path: string }>;
  if (rows.length === 0) return;
  const update = db.prepare('UPDATE files SET path_search = ? WHERE id = ?');
  db.exec('BEGIN');
  try {
    for (const row of rows) {
      update.run(normalizeForSearch(row.path), row.id);
    }
    db.exec('COMMIT');
  } catch (err) {
    db.exec('ROLLBACK');
    throw err;
  }
}
