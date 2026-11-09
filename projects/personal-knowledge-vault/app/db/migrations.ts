/**
 * Schema migrations. Versioned, idempotent steps recorded in the
 * `schema_version` table (single row holding the current version).
 * Re-running is always safe.
 *
 * v1: notes, note_tags, sources, note_links, revisions, plus an FTS5
 * virtual table (notes_fts) kept in sync with row triggers, and
 * append-only enforcement on revisions (UPDATE is rejected at the DB
 * level; rows may only be INSERTed, or removed by cascading note delete).
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
    description: 'initial schema: notes, tags, sources, links, revisions, FTS5',
    sql: `
      CREATE TABLE IF NOT EXISTS notes (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        body TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'candidate'
          CHECK (status IN ('candidate', 'verified', 'rejected')),
        rejection_reason TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS note_tags (
        note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
        tag TEXT NOT NULL,
        PRIMARY KEY (note_id, tag)
      );

      CREATE TABLE IF NOT EXISTS sources (
        id TEXT PRIMARY KEY,
        note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
        title TEXT,
        author TEXT,
        url TEXT,
        doc_pointer TEXT,
        accessed_at TEXT
      );
      CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_note ON sources(note_id);

      CREATE TABLE IF NOT EXISTS note_links (
        note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
        target_note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
        PRIMARY KEY (note_id, target_note_id),
        CHECK (note_id != target_note_id)
      );

      CREATE TABLE IF NOT EXISTS revisions (
        id TEXT PRIMARY KEY,
        note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
        rev_no INTEGER NOT NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        tags_json TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('candidate', 'verified', 'rejected')),
        change_summary TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (note_id, rev_no)
      );
      CREATE INDEX IF NOT EXISTS idx_revisions_note ON revisions(note_id, rev_no);

      -- Full-text index over title/body/tags. note_id is UNINDEXED
      -- (a join key, never searched). Kept in sync by triggers below.
      CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts
        USING fts5(note_id UNINDEXED, title, body, tags);

      -- --- FTS sync triggers -------------------------------------------
      CREATE TRIGGER IF NOT EXISTS trg_notes_fts_insert AFTER INSERT ON notes
      BEGIN
        INSERT INTO notes_fts (note_id, title, body, tags)
        VALUES (
          new.id,
          new.title,
          new.body,
          (SELECT COALESCE(group_concat(tag, ' '), '') FROM note_tags WHERE note_id = new.id)
        );
      END;

      CREATE TRIGGER IF NOT EXISTS trg_notes_fts_update AFTER UPDATE OF title, body ON notes
      BEGIN
        UPDATE notes_fts
        SET title = new.title, body = new.body
        WHERE note_id = new.id;
      END;

      CREATE TRIGGER IF NOT EXISTS trg_notes_fts_delete AFTER DELETE ON notes
      BEGIN
        DELETE FROM notes_fts WHERE note_id = old.id;
      END;

      CREATE TRIGGER IF NOT EXISTS trg_tags_fts_insert AFTER INSERT ON note_tags
      BEGIN
        UPDATE notes_fts
        SET tags = (SELECT COALESCE(group_concat(tag, ' '), '') FROM note_tags WHERE note_id = new.note_id)
        WHERE note_id = new.note_id;
      END;

      CREATE TRIGGER IF NOT EXISTS trg_tags_fts_delete AFTER DELETE ON note_tags
      BEGIN
        UPDATE notes_fts
        SET tags = (SELECT COALESCE(group_concat(tag, ' '), '') FROM note_tags WHERE note_id = old.note_id)
        WHERE note_id = old.note_id;
      END;

      -- --- revision immutability ----------------------------------------
      -- Revisions are append-only: a row may be INSERTed, and rows vanish
      -- only when their parent note is deleted (FK cascade). Direct
      -- UPDATEs are rejected at the database level.
      CREATE TRIGGER IF NOT EXISTS trg_revisions_no_update BEFORE UPDATE ON revisions
      BEGIN
        SELECT RAISE(ABORT, 'revisions are append-only');
      END;
    `,
  },
];

export const SCHEMA_VERSION = MIGRATIONS.length;

/** Assert that this build of SQLite has FTS5 compiled in. */
export function assertFts5Available(db: DatabaseSync): void {
  const row = db
    .prepare("SELECT sqlite_compileoption_used('ENABLE_FTS5') AS enabled")
    .get() as { enabled: number };
  if (!row || row.enabled !== 1) {
    throw new Error('SQLite FTS5 is not available in this build (ENABLE_FTS5=0).');
  }
}

export function runMigrations(db: DatabaseSync): void {
  assertFts5Available(db);
  db.exec(`
    CREATE TABLE IF NOT EXISTS schema_version (
      version INTEGER NOT NULL
    );
  `);
  const rows = db.prepare('SELECT version FROM schema_version').all() as { version: number }[];
  const current = rows.length > 0 ? (rows[0] as { version: number }).version : 0;
  for (const migration of MIGRATIONS) {
    if (migration.version <= current) continue;
    db.exec('BEGIN');
    try {
      db.exec(migration.sql);
      db.exec('DELETE FROM schema_version;');
      db.prepare('INSERT INTO schema_version (version) VALUES (?)').run(migration.version);
      db.exec('COMMIT');
    } catch (err) {
      db.exec('ROLLBACK');
      throw err;
    }
  }
}
