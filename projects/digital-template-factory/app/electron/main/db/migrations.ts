/**
 * Schema migrations. Versioned, idempotent steps recorded in the
 * `schema_version` table. `templates` holds imported (external) template
 * bundles; bundled templates live in code and are never stored.
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
    description: 'initial schema: schema_version, templates, documents',
    sql: `
      CREATE TABLE IF NOT EXISTS templates (
        id TEXT PRIMARY KEY,
        manifest_version TEXT NOT NULL,
        name TEXT NOT NULL,
        version TEXT NOT NULL,
        manifest_json TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'imported',
        created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        template_id TEXT NOT NULL,
        data_json TEXT NOT NULL,
        tokens_json TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_documents_template_id
        ON documents(template_id);
    `,
  },
];

function ensureVersionTable(db: DatabaseSync): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS schema_version (
      version INTEGER PRIMARY KEY,
      applied_at TEXT NOT NULL
    );
  `);
}

function currentVersion(db: DatabaseSync): number {
  ensureVersionTable(db);
  const row = db
    .prepare('SELECT MAX(version) AS v FROM schema_version')
    .get() as { v: number | null } | undefined;
  return row?.v ?? 0;
}

/** Apply every pending migration inside one explicit transaction. */
export function runMigrations(db: DatabaseSync): void {
  const current = currentVersion(db);
  const pending = MIGRATIONS.filter((m) => m.version > current).sort(
    (a, b) => a.version - b.version,
  );
  for (const migration of pending) {
    db.exec('BEGIN IMMEDIATE');
    try {
      db.exec(migration.sql);
      db.prepare(
        'INSERT INTO schema_version (version, applied_at) VALUES (?, ?)',
      ).run(migration.version, new Date().toISOString());
      db.exec('COMMIT');
    } catch (err) {
      db.exec('ROLLBACK');
      throw err;
    }
  }
}
