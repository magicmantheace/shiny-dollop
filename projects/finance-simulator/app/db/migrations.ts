/**
 * Schema migrations. Versioned, idempotent steps recorded in the
 * `schema_version` table (single row holding the current version).
 * Re-running is always safe.
 *
 * NOTE: this module must NOT import 'electron' — backend tests construct
 * DatabaseSync directly and call runMigrations themselves.
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
    description: 'initial schema: debts, income_sources',
    sql: `
      CREATE TABLE IF NOT EXISTS debts (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        balance_cents INTEGER NOT NULL CHECK (balance_cents >= 0),
        apr_percent REAL NOT NULL CHECK (apr_percent >= 0 AND apr_percent <= 100),
        min_payment_cents INTEGER NOT NULL CHECK (min_payment_cents >= 0),
        created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS income_sources (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
        frequency TEXT NOT NULL CHECK (frequency IN ('monthly','biweekly','weekly','once')),
        created_at TEXT NOT NULL
      );
    `,
  },
];

export const SCHEMA_VERSION = MIGRATIONS.length;

export function runMigrations(db: DatabaseSync): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS schema_version (
      version INTEGER NOT NULL
    );
  `);
  const rows = db.prepare('SELECT version FROM schema_version').all() as { version: number }[];
  const current = rows.length > 0 ? (rows[0] as { version: number }).version : 0;
  for (const migration of MIGRATIONS) {
    if (migration.version <= current) continue;
    db.exec(migration.sql);
    db.exec('DELETE FROM schema_version;');
    db.prepare('INSERT INTO schema_version (version) VALUES (?)').run(migration.version);
  }
}
