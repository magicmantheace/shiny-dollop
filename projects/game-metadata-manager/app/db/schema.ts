import { DatabaseSync } from 'node:sqlite';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

export const SCHEMA_VERSION = 1;

const MIGRATIONS: string[] = [
  // v1: initial schema
  `
  CREATE TABLE IF NOT EXISTS games (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    original_title TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    install_path  TEXT NOT NULL UNIQUE,
    artwork_id    TEXT NULL,
    tag_ids       TEXT NOT NULL DEFAULT '[]',
    collection_ids TEXT NOT NULL DEFAULT '[]',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS artwork (
    id        TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    provenance TEXT NOT NULL,
    mime      TEXT NOT NULL,
    added_at  TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS tags (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
  );
  CREATE TABLE IF NOT EXISTS collections (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
  );
  CREATE TABLE IF NOT EXISTS changes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id  TEXT NOT NULL,
    field    TEXT NOT NULL,
    before   TEXT NOT NULL,
    after    TEXT NOT NULL,
    at       TEXT NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_changes_game ON changes(game_id);
  `,
];

export function openDatabase(dbPath: string): DatabaseSync {
  mkdirSync(dirname(dbPath), { recursive: true });
  const db = new DatabaseSync(dbPath);
  db.exec('PRAGMA journal_mode = WAL;');
  db.exec('PRAGMA foreign_keys = ON;');
  db.exec(
    'CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);'
  );

  const row = db
    .prepare('SELECT version FROM schema_version')
    .get() as unknown as { version: number } | undefined;
  const current = row?.version ?? 0;

  if (current > SCHEMA_VERSION) {
    throw new Error(
      `Database schema version ${current} is newer than supported ${SCHEMA_VERSION}`
    );
  }

  for (let v = current + 1; v <= SCHEMA_VERSION; v++) {
    const sql = MIGRATIONS[v - 1];
    if (!sql) throw new Error(`Missing migration for schema version ${v}`);
    db.exec('BEGIN;');
    try {
      db.exec(sql);
      db.exec('DELETE FROM schema_version;');
      db.prepare('INSERT INTO schema_version (version) VALUES (?);').run(v);
      db.exec('COMMIT;');
    } catch (err) {
      db.exec('ROLLBACK;');
      throw err;
    }
  }

  return db;
}
