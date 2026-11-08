/** CRUD for per-game backup schedules. Pure SQL over DatabaseSync. */
import type { DatabaseSync } from 'node:sqlite';
import type { Schedule } from '../../../shared/types';
import { allRows, oneRow } from './rows';

interface ScheduleRow {
  id: number;
  game_id: number;
  interval_minutes: number;
  enabled: number;
  last_run_at: string | null;
}

function toSchedule(row: ScheduleRow): Schedule {
  return {
    id: row.id,
    gameId: row.game_id,
    intervalMinutes: row.interval_minutes,
    enabled: row.enabled === 1,
    lastRunAt: row.last_run_at,
  };
}

export function listSchedules(db: DatabaseSync): Schedule[] {
  const rows = allRows<ScheduleRow>(db.prepare('SELECT * FROM schedules ORDER BY game_id').all());
  return rows.map(toSchedule);
}

export function getSchedule(db: DatabaseSync, gameId: number): Schedule | null {
  const row = oneRow<ScheduleRow>(db.prepare('SELECT * FROM schedules WHERE game_id = ?').get(gameId));
  return row ? toSchedule(row) : null;
}

/** Upsert: one schedule per game. */
export function setSchedule(
  db: DatabaseSync,
  input: { gameId: number; intervalMinutes: number; enabled: boolean },
): Schedule {
  db.prepare(
    `INSERT INTO schedules (game_id, interval_minutes, enabled, last_run_at)
     VALUES (?, ?, ?, NULL)
     ON CONFLICT(game_id) DO UPDATE SET interval_minutes = excluded.interval_minutes, enabled = excluded.enabled`,
  ).run(input.gameId, input.intervalMinutes, input.enabled ? 1 : 0);
  const schedule = getSchedule(db, input.gameId);
  if (!schedule) throw new Error('Failed to read back upserted schedule');
  return schedule;
}

export function deleteSchedule(db: DatabaseSync, gameId: number): boolean {
  const result = db.prepare('DELETE FROM schedules WHERE game_id = ?').run(gameId);
  return Number(result.changes) > 0;
}

export function touchScheduleLastRun(db: DatabaseSync, gameId: number, at: string): void {
  db.prepare('UPDATE schedules SET last_run_at = ? WHERE game_id = ?').run(at, gameId);
}
