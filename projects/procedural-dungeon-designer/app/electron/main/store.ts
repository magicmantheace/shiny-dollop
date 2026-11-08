// SQLite persistence (node:sqlite) for saved dungeons.
// The whole SavedDungeon is stored as JSON in `json`; id/name/seed/theme
// are denormalized into columns so listings and lookups stay cheap and
// inspectable without parsing every record.
import { DatabaseSync } from 'node:sqlite';
import type { SavedDungeon } from '../../shared/types.js';

export const SCHEMA_VERSION = 1;

export function nowIso(): string {
  return new Date().toISOString();
}

const MIGRATIONS = `
CREATE TABLE IF NOT EXISTS dungeons (
  id TEXT PRIMARY KEY,
  name TEXT,
  seed TEXT,
  theme TEXT,
  json TEXT,
  created_at TEXT,
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_dungeons_updated ON dungeons(updated_at DESC);
`;

export function openDatabase(dbPath: string): DatabaseSync {
  const db = new DatabaseSync(dbPath);
  db.exec('PRAGMA journal_mode = WAL;');
  db.exec('PRAGMA foreign_keys = ON;');
  db.exec(MIGRATIONS);
  db.exec(`PRAGMA user_version = ${SCHEMA_VERSION};`);
  return db;
}

interface DungeonRow {
  json: string;
}

function rowToSaved(row: DungeonRow): SavedDungeon {
  return JSON.parse(row.json) as SavedDungeon;
}

export function insertDungeon(db: DatabaseSync, saved: SavedDungeon): SavedDungeon {
  db.prepare(
    'INSERT INTO dungeons (id, name, seed, theme, json, created_at, updated_at) VALUES (?,?,?,?,?,?,?)',
  ).run(
    saved.id,
    saved.name,
    saved.map.params.seed,
    saved.map.params.theme,
    JSON.stringify(saved),
    saved.createdAt,
    saved.updatedAt,
  );
  return saved;
}

export function getDungeon(db: DatabaseSync, id: string): SavedDungeon | null {
  const row = db.prepare('SELECT json FROM dungeons WHERE id = ?').get(id) as unknown as
    | DungeonRow
    | undefined;
  return row ? rowToSaved(row) : null;
}

export function listDungeons(db: DatabaseSync): SavedDungeon[] {
  const rows = db
    .prepare('SELECT json FROM dungeons ORDER BY updated_at DESC, rowid DESC')
    .all() as unknown as DungeonRow[];
  return rows.map(rowToSaved);
}

export function updateDungeon(db: DatabaseSync, saved: SavedDungeon): boolean {
  const res = db
    .prepare(
      'UPDATE dungeons SET name = ?, seed = ?, theme = ?, json = ?, updated_at = ? WHERE id = ?',
    )
    .run(
      saved.name,
      saved.map.params.seed,
      saved.map.params.theme,
      JSON.stringify(saved),
      saved.updatedAt,
      saved.id,
    );
  return Number(res.changes) > 0;
}

export function deleteDungeon(db: DatabaseSync, id: string): boolean {
  const res = db.prepare('DELETE FROM dungeons WHERE id = ?').run(id);
  return Number(res.changes) > 0;
}
