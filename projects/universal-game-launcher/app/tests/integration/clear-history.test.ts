/** Regression tests for the clear-history defect: clearing must reset session
 * rows AND the derived per-game aggregates (playtime, last-played) in one
 * transaction, and must handle a currently-running session explicitly. */
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import type { Game, Session } from '../../shared/types';
import { openDatabase } from '../../electron/main/data/database';
import { getGame } from '../../electron/main/data/games';
import { clearPlayHistory, createSession, finalizeSession } from '../../electron/main/data/sessions';
import { createTestContext, type TestContext } from './helpers';

let ctx: TestContext | null = null;
const tempDirs: string[] = [];
afterEach(() => {
  ctx?.close();
  ctx = null;
  for (const d of tempDirs.splice(0)) rmSync(d, { recursive: true, force: true });
});

function makeExe(name = 'game.sh'): string {
  const dir = mkdtempSync(path.join(tmpdir(), 'ugl-clear-'));
  tempDirs.push(dir);
  const exe = path.join(dir, name);
  writeFileSync(exe, '#!/bin/sh\necho hi\n');
  chmodSync(exe, 0o755);
  return exe;
}

async function addGame(exe: string, title?: string): Promise<Game> {
  const res = await ctx!.call('library.addManual', { path: exe, title });
  if (!res.ok) throw new Error(`add failed: ${res.error?.message}`);
  return res.data as Game;
}

/** Record a finished session directly in the DB (simulates past play). */
function seedSession(gameId: string, durationMs: number): void {
  const db = ctx!.deps.db;
  const s = createSession(db, gameId, 'observed');
  const ended = new Date(Date.parse(s.startedAt) + durationMs).toISOString();
  finalizeSession(db, s.id, { state: 'completed', endedAtIso: ended });
  db.prepare('UPDATE games SET last_played_at = ?, total_play_ms = total_play_ms + ? WHERE id = ?').run(
    ended,
    durationMs,
    gameId,
  );
}

async function gameById(id: string): Promise<Game> {
  const res = (await ctx!.call('library.list', {})) as { ok: boolean; data: Game[] };
  const g = res.data.find((x) => x.id === id);
  if (!g) throw new Error('game missing from library');
  return g;
}

describe('clear play history', () => {
  it('clears sessions AND per-game aggregates across multiple games', async () => {
    ctx = createTestContext();
    const g1 = await addGame(makeExe('a.sh'), 'Game A');
    const g2 = await addGame(makeExe('b.sh'), 'Game B');
    seedSession(g1.id, 60_000);
    seedSession(g1.id, 30_000);
    seedSession(g2.id, 120_000);

    const before = (await ctx.call('sessions.list', {})) as { ok: boolean; data: Session[] };
    expect(before.data).toHaveLength(3);

    const cleared = await ctx.call('sessions.clear', {});
    expect(cleared.ok).toBe(true);

    const after = (await ctx.call('sessions.list', {})) as { ok: boolean; data: Session[] };
    expect(after.data).toHaveLength(0);

    const ga = await gameById(g1.id);
    const gb = await gameById(g2.id);
    expect(ga.totalPlayMs).toBe(0);
    expect(ga.lastPlayedAt).toBeNull();
    expect(gb.totalPlayMs).toBe(0);
    expect(gb.lastPlayedAt).toBeNull();
  });

  it('clearing with no history is a harmless no-op', async () => {
    ctx = createTestContext();
    const g = await addGame(makeExe(), 'Quiet Game');
    const res = await ctx.call('sessions.clear', {});
    expect(res.ok).toBe(true);
    const games = (await ctx.call('library.list', {})) as { ok: boolean; data: Game[] };
    expect(games.data).toHaveLength(1);
    expect(games.data[0]!.title).toBe('Quiet Game');
    expect(games.data[0]!.totalPlayMs).toBe(0);
  });

  it('clearing during an active session re-keys it: only post-clear time is recorded', async () => {
    ctx = createTestContext();
    const game = await addGame(makeExe(), 'Live Game');
    seedSession(game.id, 3_600_000); // one hour of old history

    const launched = (await ctx.call('games.launch', { id: game.id })) as {
      ok: boolean;
      data: { sessionId: string; alreadyRunning: boolean };
    };
    expect(launched.ok).toBe(true);
    const oldSessionId = launched.data.sessionId;
    expect(oldSessionId).not.toBeNull();

    // Let a little time pass, then clear while the "game" is running.
    await new Promise((r) => setTimeout(r, 50));
    const cleared = await ctx.call('sessions.clear', {});
    expect(cleared.ok).toBe(true);

    // Old rows gone, aggregates zeroed, but the game is still tracked.
    const sessions = (await ctx.call('sessions.list', {})) as { ok: boolean; data: Session[] };
    expect(sessions.data).toHaveLength(1);
    expect(sessions.data[0]!.id).not.toBe(oldSessionId);
    expect(sessions.data[0]!.state).toBe('running');
    const clearedAt = Date.parse(sessions.data[0]!.startedAt);
    expect(Date.now() - clearedAt).toBeLessThan(10_000);

    const mid = await gameById(game.id);
    expect(mid.totalPlayMs).toBe(0);
    expect(mid.lastPlayedAt).toBeNull();

    // Process exits after the clear: only post-clear duration is recorded,
    // never the pre-clear hour.
    await new Promise((r) => setTimeout(r, 50));
    ctx.stub.closeLast(0);

    const done = (await ctx.call('sessions.list', {})) as { ok: boolean; data: Session[] };
    expect(done.data).toHaveLength(1);
    expect(done.data[0]!.state).toBe('completed');
    expect(done.data[0]!.durationMs ?? 0).toBeLessThan(60_000);

    const fin = await gameById(game.id);
    expect(fin.totalPlayMs).toBeLessThan(60_000);
    expect(fin.totalPlayMs).toBeGreaterThanOrEqual(0);
    expect(fin.lastPlayedAt).not.toBeNull();
  });

  it('clearing with tracking disabled leaves the running game alone', async () => {
    ctx = createTestContext();
    await ctx.call('settings.update', { trackingEnabled: false });
    const game = await addGame(makeExe(), 'Untracked');
    const launched = (await ctx.call('games.launch', { id: game.id })) as {
      ok: boolean;
      data: { sessionId: string | null; alreadyRunning: boolean };
    };
    expect(launched.ok).toBe(true);
    expect(launched.data.sessionId).toBeNull();

    const cleared = await ctx.call('sessions.clear', {});
    expect(cleared.ok).toBe(true);
    ctx.stub.closeLast(0); // must not throw with no session row
    const sessions = (await ctx.call('sessions.list', {})) as { ok: boolean; data: Session[] };
    expect(sessions.data).toHaveLength(0);
  });

  it('aggregates stay cleared after a database restart', async () => {
    const dir = mkdtempSync(path.join(tmpdir(), 'ugl-clear-db-'));
    tempDirs.push(dir);
    const dbPath = path.join(dir, 'library.db');
    const exe = makeExe('restart.sh');

    const db1 = openDatabase(dbPath);
    const { addManualGame } = await import('../../electron/main/data/games');
    const created = await addManualGame(db1, { path: exe, title: 'Restart Game' });
    const s = createSession(db1, created.id, 'observed');
    finalizeSession(db1, s.id, { state: 'completed' });
    db1.prepare('UPDATE games SET last_played_at = ?, total_play_ms = ? WHERE id = ?').run(
      new Date().toISOString(),
      99999,
      created.id,
    );
    clearPlayHistory(db1);
    db1.close();

    const db2 = openDatabase(dbPath);
    const reloaded = getGame(db2, created.id);
    expect(reloaded?.totalPlayMs).toBe(0);
    expect(reloaded?.lastPlayedAt).toBeNull();
    const rows = db2.prepare('SELECT COUNT(*) AS n FROM sessions').get() as { n: number };
    expect(rows.n).toBe(0);
    db2.close();
  });

  it('clearing never touches installed games or other library metadata', async () => {
    ctx = createTestContext();
    const exe = makeExe('untouched.sh');
    const game = await addGame(exe, 'Keep Me');
    await ctx.call('library.setFavorite', { id: game.id, favorite: true });
    seedSession(game.id, 5000);
    await ctx.call('sessions.clear', {});
    const g = await gameById(game.id);
    expect(g.title).toBe('Keep Me');
    expect(g.favorite).toBe(true);
    expect(g.missing).toBe(false);
  });
});
