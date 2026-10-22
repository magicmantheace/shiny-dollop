/** Game library persistence. All SQL lives here; callers work with typed Games. */
import type { DatabaseSync, SQLInputValue } from 'node:sqlite';
import { existsSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import path from 'node:path';
import type { Game, GameSource, LaunchCapability, SortKey } from '../../../shared/types';
import {
  ValidationError,
  assertDirectoryUsable,
  assertExecutableUsable,
  canonicalKey,
  canonicalizePath,
  defaultTitleFor,
  validateArgsArray,
} from '../launch/validation';
import { isValidCoverFilename } from '../files/cover-store';

interface GameRow {
  id: string;
  source: string;
  external_id: string | null;
  title: string;
  exe_path: string | null;
  canonical_path: string | null;
  install_dir: string | null;
  launch_uri: string | null;
  launch_capability: string | null;
  launch_reason: string | null;
  cover_path: string | null;
  working_dir: string | null;
  args_json: string;
  favorite: number;
  hidden: number;
  added_at: string;
  updated_at: string;
  last_played_at: string | null;
  total_play_ms: number;
}

function rowToGame(row: GameRow): Game {
  const exePath = row.exe_path;
  const installDir = row.install_dir;
  // Missing-ness is computed at read time: manual games check the exe,
  // store games check the install dir. Removed installs flip to missing
  // instead of losing their rows and history.
  const missing =
    exePath !== null ? !existsSync(exePath) : installDir !== null ? !existsSync(installDir) : false;
  return {
    id: row.id,
    source: row.source as GameSource,
    externalId: row.external_id,
    title: row.title,
    exePath,
    canonicalPath: row.canonical_path,
    installDir,
    launchUri: row.launch_uri,
    launchCapability: (row.launch_capability as LaunchCapability | null) ?? 'direct',
    launchReason: row.launch_reason,
    workingDir: row.working_dir,
    args: JSON.parse(row.args_json) as string[],
    favorite: row.favorite === 1,
    hidden: row.hidden === 1,
    coverPath: row.cover_path,
    missing,
    addedAt: row.added_at,
    updatedAt: row.updated_at,
    lastPlayedAt: row.last_played_at,
    totalPlayMs: row.total_play_ms,
  };
}

export interface ListQuery {
  search?: string;
  source?: GameSource;
  favoritesOnly?: boolean;
  includeHidden?: boolean;
  sort?: SortKey;
}

const SORT_SQL: Record<SortKey, string> = {
  title: 'title COLLATE NOCASE ASC',
  added: 'added_at DESC',
  lastPlayed: 'last_played_at DESC NULLS LAST, title COLLATE NOCASE ASC',
  playtime: 'total_play_ms DESC, title COLLATE NOCASE ASC',
};

export function listGames(db: DatabaseSync, query: ListQuery = {}): Game[] {
  const where: string[] = [];
  const params: SQLInputValue[] = [];
  if (!query.includeHidden) {
    where.push('hidden = 0');
  }
  if (query.source) {
    where.push('source = ?');
    params.push(query.source);
  }
  if (query.favoritesOnly) {
    where.push('favorite = 1');
  }
  const search = query.search?.trim();
  if (search) {
    where.push('title LIKE ? COLLATE NOCASE');
    params.push(`%${search.replace(/[%_]/g, '')}%`);
  }
  const sort = SORT_SQL[query.sort ?? 'title'];
  const sql = `SELECT * FROM games${where.length ? ` WHERE ${where.join(' AND ')}` : ''} ORDER BY ${sort}`;
  const rows = db.prepare(sql).all(...params) as unknown as GameRow[];
  return rows.map(rowToGame);
}

export function getGame(db: DatabaseSync, id: string): Game | null {
  const row = db.prepare('SELECT * FROM games WHERE id = ?').get(id) as unknown as GameRow | undefined;
  return row ? rowToGame(row) : null;
}

export interface AddManualInput {
  path: string;
  workingDir?: string;
  args?: string[];
}

/**
 * Register a manually chosen executable. Validates the target, rejects
 * duplicates by canonical path, and never modifies the target file.
 */
export async function addManualGame(db: DatabaseSync, input: AddManualInput): Promise<Game> {
  const exePath = canonicalizePath(input.path);
  if (process.platform === 'win32' && path.extname(exePath).toLowerCase() === '.lnk') {
    throw new ValidationError(
      'SHORTCUT_UNSUPPORTED',
      'Windows shortcuts (.lnk) are not supported yet. Please choose the .exe directly.',
    );
  }
  await assertExecutableUsable(exePath);
  const key = canonicalKey(exePath);
  const dup = db
    .prepare("SELECT id, title FROM games WHERE source = 'manual' AND canonical_path = ?")
    .get(key) as { id: string; title: string } | undefined;
  if (dup) {
    throw new ValidationError(
      'DUPLICATE',
      `This executable is already in your library as "${dup.title}".`,
    );
  }
  const args = validateArgsArray(input.args);
  let workingDir: string | null = null;
  if (input.workingDir !== undefined && input.workingDir.trim() !== '') {
    await assertDirectoryUsable(input.workingDir);
    workingDir = canonicalizePath(input.workingDir);
  }
  const now = new Date().toISOString();
  const id = randomUUID();
  db.prepare(
    `INSERT INTO games (id, source, title, exe_path, canonical_path, working_dir, args_json, added_at, updated_at)
     VALUES (?, 'manual', ?, ?, ?, ?, ?, ?, ?)`,
  ).run(id, defaultTitleFor(exePath), exePath, key, workingDir, JSON.stringify(args), now, now);
  const created = getGame(db, id);
  if (!created) throw new Error('Failed to read back inserted game.');
  return created;
}

export interface UpdateGameInput {
  id: string;
  title?: string;
  workingDir?: string | null;
  args?: string[];
  hidden?: boolean;
  /** Validated cover filename, or null to clear. */
  coverPath?: string | null;
}

export async function updateGame(db: DatabaseSync, input: UpdateGameInput): Promise<Game> {
  const existing = db.prepare('SELECT * FROM games WHERE id = ?').get(input.id) as
    | GameRow
    | undefined;
  if (!existing) {
    throw new ValidationError('NOT_FOUND', 'Game not found in the library.');
  }
  const sets: string[] = ['updated_at = ?'];
  const params: SQLInputValue[] = [new Date().toISOString()];
  if (input.title !== undefined) {
    const title = input.title.trim();
    if (!title) throw new ValidationError('INVALID_TITLE', 'Title must not be empty.');
    sets.push('title = ?');
    params.push(title.slice(0, 256));
  }
  if (input.workingDir !== undefined) {
    if (input.workingDir === null || input.workingDir.trim() === '') {
      sets.push('working_dir = NULL');
    } else {
      await assertDirectoryUsable(input.workingDir);
      sets.push('working_dir = ?');
      params.push(canonicalizePath(input.workingDir));
    }
  }
  if (input.args !== undefined) {
    sets.push('args_json = ?');
    params.push(JSON.stringify(validateArgsArray(input.args)));
  }
  if (input.hidden !== undefined) {
    sets.push('hidden = ?');
    params.push(input.hidden ? 1 : 0);
  }
  if (input.coverPath !== undefined) {
    if (input.coverPath === null) {
      sets.push('cover_path = NULL');
    } else {
      // The filename must be exactly one this app wrote (uuid + image ext);
      // anything else is rejected rather than trusted.
      if (!isValidCoverFilename(input.coverPath)) {
        throw new ValidationError('INVALID_COVER', 'Cover filename is not from this app.');
      }
      sets.push('cover_path = ?');
      params.push(input.coverPath);
    }
  }
  params.push(input.id);
  db.prepare(`UPDATE games SET ${sets.join(', ')} WHERE id = ?`).run(...params);
  const updated = getGame(db, input.id);
  if (!updated) throw new Error('Failed to read back updated game.');
  return updated;
}

export function setFavorite(db: DatabaseSync, id: string, favorite: boolean): Game {
  const result = db
    .prepare('UPDATE games SET favorite = ?, updated_at = ? WHERE id = ?')
    .run(favorite ? 1 : 0, new Date().toISOString(), id);
  if (result.changes === 0) {
    throw new ValidationError('NOT_FOUND', 'Game not found in the library.');
  }
  const game = getGame(db, id);
  if (!game) throw new Error('Failed to read back updated game.');
  return game;
}

/**
 * Remove a library entry. Deletes only the app's own database rows
 * (games + sessions via cascade). Never touches the target executable.
 */
export function removeGame(db: DatabaseSync, id: string): void {
  const result = db.prepare('DELETE FROM games WHERE id = ?').run(id);
  if (result.changes === 0) {
    throw new ValidationError('NOT_FOUND', 'Game not found in the library.');
  }
}

/** Record a finished play session against the game's totals. */
export function recordPlaytime(
  db: DatabaseSync,
  gameId: string,
  endedAtIso: string,
  durationMs: number,
): void {
  db.prepare(
    `UPDATE games SET last_played_at = ?, total_play_ms = total_play_ms + ?, updated_at = ?
     WHERE id = ?`,
  ).run(endedAtIso, Math.max(0, Math.round(durationMs)), new Date().toISOString(), gameId);
}
