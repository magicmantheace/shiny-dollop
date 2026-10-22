/** Play-session persistence and crash recovery. */
import type { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import type { Session, SessionState, TrackingMethod } from '../../../shared/types';

interface SessionRow {
  id: string;
  game_id: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  state: string;
  tracking_method: string;
  last_checkpoint_at: string | null;
  notes: string | null;
  game_title: string;
}

function rowToSession(row: SessionRow): Session {
  return {
    id: row.id,
    gameId: row.game_id,
    gameTitle: row.game_title,
    startedAt: row.started_at,
    endedAt: row.ended_at,
    durationMs: row.duration_ms,
    state: row.state as SessionState,
    trackingMethod: row.tracking_method as TrackingMethod,
    notes: row.notes,
  };
}

/** Defensive duration: never negative, rounded to whole milliseconds. */
export function computeDurationMs(startedAtIso: string, endedAtIso: string): number {
  const ms = Date.parse(endedAtIso) - Date.parse(startedAtIso);
  if (!Number.isFinite(ms) || ms < 0) return 0;
  return Math.round(ms);
}

export function createSession(
  db: DatabaseSync,
  gameId: string,
  trackingMethod: TrackingMethod = 'observed',
): Session {
  const id = randomUUID();
  const now = new Date().toISOString();
  db.prepare(
    `INSERT INTO sessions (id, game_id, started_at, state, tracking_method, last_checkpoint_at)
     VALUES (?, ?, ?, 'running', ?, ?)`,
  ).run(id, gameId, now, trackingMethod, now);
  const row = db
    .prepare(
      `SELECT s.*, g.title AS game_title FROM sessions s JOIN games g ON g.id = s.game_id WHERE s.id = ?`,
    )
    .get(id) as SessionRow;
  return rowToSession(row);
}

export function checkpointSession(db: DatabaseSync, sessionId: string): void {
  db.prepare(
    `UPDATE sessions SET last_checkpoint_at = ? WHERE id = ? AND state = 'running'`,
  ).run(new Date().toISOString(), sessionId);
}

export interface FinalizeInput {
  endedAtIso?: string;
  state: SessionState;
  notes?: string | null;
}

export function finalizeSession(db: DatabaseSync, sessionId: string, input: FinalizeInput): Session {
  const row = db.prepare('SELECT * FROM sessions WHERE id = ?').get(sessionId) as
    | SessionRow
    | undefined;
  if (!row) throw new Error(`Session ${sessionId} not found.`);
  const endedAt = input.endedAtIso ?? new Date().toISOString();
  const durationMs = computeDurationMs(row.started_at, endedAt);
  db.prepare(
    `UPDATE sessions SET ended_at = ?, duration_ms = ?, state = ?, notes = COALESCE(?, notes) WHERE id = ?`,
  ).run(endedAt, durationMs, input.state, input.notes ?? null, sessionId);
  const updated = db
    .prepare(
      `SELECT s.*, g.title AS game_title FROM sessions s JOIN games g ON g.id = s.game_id WHERE s.id = ?`,
    )
    .get(sessionId) as SessionRow;
  return rowToSession(updated);
}

/**
 * Crash/restart recovery. Sessions left 'running' are finalized as
 * 'interrupted' at their last checkpoint — never at "now", so no phantom
 * playtime is invented between the last observation and the restart.
 * Returns the number of sessions recovered.
 */
export function recoverInterruptedSessions(db: DatabaseSync): number {
  const running = db.prepare(`SELECT * FROM sessions WHERE state = 'running'`).all() as SessionRow[];
  for (const row of running) {
    const end = row.last_checkpoint_at ?? row.started_at;
    const durationMs = computeDurationMs(row.started_at, end);
    db.prepare(
      `UPDATE sessions SET ended_at = ?, duration_ms = ?, state = 'interrupted',
       notes = COALESCE(notes, 'App closed or crashed during this session; ended conservatively at last checkpoint.')
       WHERE id = ?`,
    ).run(end, durationMs, row.id);
  }
  return running.length;
}

export function listSessions(
  db: DatabaseSync,
  query: { gameId?: string; limit?: number } = {},
): Session[] {
  const where: string[] = [];
  const params: unknown[] = [];
  if (query.gameId) {
    where.push('s.game_id = ?');
    params.push(query.gameId);
  }
  const limit = Math.min(Math.max(query.limit ?? 100, 1), 500);
  const sql = `SELECT s.*, g.title AS game_title FROM sessions s
    JOIN games g ON g.id = s.game_id
    ${where.length ? `WHERE ${where.join(' AND ')}` : ''}
    ORDER BY s.started_at DESC LIMIT ${limit}`;
  const rows = db.prepare(sql).all(...params) as SessionRow[];
  return rows.map(rowToSession);
}

/** Clear session history. Touches only the app's own records, never game files. */
export function clearSessions(db: DatabaseSync): void {
  db.exec('DELETE FROM sessions');
}
