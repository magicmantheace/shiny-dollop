import { describe, expect, it } from 'vitest';
import { openDatabase } from '../../electron/main/data/database';
import {
  computeDurationMs,
  createSession,
  finalizeSession,
  listSessions,
  recoverInterruptedSessions,
} from '../../electron/main/data/sessions';

function seedGame(db: ReturnType<typeof openDatabase>): string {
  const now = new Date().toISOString();
  db.prepare(
    `INSERT INTO games (id, title, added_at, updated_at) VALUES ('game-1', 'Test Game', ?, ?)`,
  ).run(now, now);
  return 'game-1';
}

describe('computeDurationMs', () => {
  it('measures elapsed time', () => {
    expect(computeDurationMs('2026-01-01T00:00:00.000Z', '2026-01-01T00:01:30.000Z')).toBe(90000);
  });
  it('clamps negative durations to zero (clock skew)', () => {
    expect(computeDurationMs('2026-01-01T00:01:00.000Z', '2026-01-01T00:00:00.000Z')).toBe(0);
  });
  it('handles invalid input without NaN', () => {
    expect(computeDurationMs('bogus', '2026-01-01T00:00:00.000Z')).toBe(0);
  });
});

describe('session lifecycle', () => {
  it('creates a running session and finalizes it on close', () => {
    const db = openDatabase(':memory:');
    try {
      const gameId = seedGame(db);
      const s = createSession(db, gameId);
      expect(s.state).toBe('running');
      expect(s.endedAt).toBeNull();
      const done = finalizeSession(db, s.id, { state: 'completed' });
      expect(done.state).toBe('completed');
      expect(done.endedAt).not.toBeNull();
      expect(done.durationMs).toBeGreaterThanOrEqual(0);
      expect(listSessions(db)).toHaveLength(1);
    } finally {
      db.close();
    }
  });

  it('recovery finalizes at the last checkpoint, never inventing time', () => {
    const db = openDatabase(':memory:');
    try {
      const gameId = seedGame(db);
      const s = createSession(db, gameId);
      // Simulate 5 minutes of observed play, then a crash with no further checkpoints.
      const start = Date.parse(s.startedAt);
      const checkpoint = new Date(start + 5 * 60 * 1000).toISOString();
      db.prepare('UPDATE sessions SET last_checkpoint_at = ? WHERE id = ?').run(checkpoint, s.id);

      const recovered = recoverInterruptedSessions(db);
      expect(recovered).toBe(1);
      const [row] = listSessions(db);
      expect(row).toBeDefined();
      expect(row!.state).toBe('interrupted');
      expect(row!.endedAt).toBe(checkpoint);
      expect(row!.durationMs).toBe(5 * 60 * 1000);
    } finally {
      db.close();
    }
  });

  it('recovery without any checkpoint ends the session at its start (zero duration)', () => {
    const db = openDatabase(':memory:');
    try {
      const gameId = seedGame(db);
      createSession(db, gameId);
      db.prepare("UPDATE sessions SET last_checkpoint_at = NULL WHERE game_id = 'game-1'").run();
      recoverInterruptedSessions(db);
      const [row] = listSessions(db);
      expect(row!.state).toBe('interrupted');
      expect(row!.durationMs).toBe(0);
    } finally {
      db.close();
    }
  });
});
