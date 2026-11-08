/** CRUD for tracked games. Pure SQL over an injected DatabaseSync. */
import type { DatabaseSync } from 'node:sqlite';
import type { Game, GameSource } from '../../../shared/types';
import { allRows, oneRow } from './rows';

interface GameRow {
  id: number;
  name: string;
  save_path: string;
  source: string;
  created_at: string;
}

function toGame(row: GameRow): Game {
  return {
    id: row.id,
    name: row.name,
    savePath: row.save_path,
    source: row.source as GameSource,
    createdAt: row.created_at,
  };
}

export function listGames(db: DatabaseSync): Game[] {
  const rows = allRows<GameRow>(db.prepare('SELECT * FROM games ORDER BY name COLLATE NOCASE').all());
  return rows.map(toGame);
}

export function getGame(db: DatabaseSync, id: number): Game | null {
  const row = oneRow<GameRow>(db.prepare('SELECT * FROM games WHERE id = ?').get(id));
  return row ? toGame(row) : null;
}

export function addGame(
  db: DatabaseSync,
  input: { name: string; savePath: string; source: GameSource },
): Game {
  const createdAt = new Date().toISOString();
  const result = db
    .prepare('INSERT INTO games (name, save_path, source, created_at) VALUES (?, ?, ?, ?)')
    .run(input.name, input.savePath, input.source, createdAt);
  const id = Number(result.lastInsertRowid);
  const game = getGame(db, id);
  if (!game) throw new Error('Failed to read back inserted game');
  return game;
}

export function updateGame(
  db: DatabaseSync,
  id: number,
  patch: { name?: string | undefined; savePath?: string | undefined },
): Game | null {
  const existing = getGame(db, id);
  if (!existing) return null;
  const name = patch.name ?? existing.name;
  const savePath = patch.savePath ?? existing.savePath;
  db.prepare('UPDATE games SET name = ?, save_path = ? WHERE id = ?').run(name, savePath, id);
  return getGame(db, id);
}

export function removeGame(db: DatabaseSync, id: number): boolean {
  const result = db.prepare('DELETE FROM games WHERE id = ?').run(id);
  return Number(result.changes) > 0;
}
