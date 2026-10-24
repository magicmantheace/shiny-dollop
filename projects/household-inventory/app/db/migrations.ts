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
    description: 'initial schema: items, attachments, maintenance_events',
    sql: `
      CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL CHECK (length(name) > 0),
        category TEXT NOT NULL CHECK (length(category) > 0),
        location TEXT NOT NULL DEFAULT '',
        purchase_price_cents INTEGER NULL CHECK (purchase_price_cents IS NULL OR purchase_price_cents >= 0),
        purchase_date TEXT NULL,
        serial_number TEXT NULL,
        notes TEXT NOT NULL DEFAULT '',
        warranty_start TEXT NULL,
        warranty_end TEXT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS attachments (
        id TEXT PRIMARY KEY,
        item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
        original_name TEXT NOT NULL,
        stored_name TEXT NOT NULL UNIQUE,
        mime TEXT NOT NULL,
        size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
        sha256 TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('receipt','photo','manual','other')),
        created_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_attachments_item_id ON attachments(item_id);
      CREATE TABLE IF NOT EXISTS maintenance_events (
        id TEXT PRIMARY KEY,
        item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
        event_date TEXT NOT NULL,
        description TEXT NOT NULL CHECK (length(description) > 0),
        cost_cents INTEGER NULL CHECK (cost_cents IS NULL OR cost_cents >= 0),
        created_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_maintenance_item_id ON maintenance_events(item_id);
    `,
  },
];

export const SCHEMA_VERSION = MIGRATIONS.length;

export function runMigrations(db: DatabaseSync): void {
  // Foreign keys must be enforced per connection; migrations run on the same
  // connection the app uses, so set it here too (store.ts also sets it).
  db.exec('PRAGMA foreign_keys = ON;');
  db.exec(`
    CREATE TABLE IF NOT EXISTS schema_version (
      version INTEGER NOT NULL
    );
  `);
  const rows = db.prepare('SELECT version FROM schema_version').all() as { version: number }[];
  const current = rows[0]?.version ?? 0;
  for (const migration of MIGRATIONS) {
    if (migration.version <= current) continue;
    db.exec(migration.sql);
    db.exec('DELETE FROM schema_version;');
    db.prepare('INSERT INTO schema_version (version) VALUES (?)').run(migration.version);
  }
}
