import { chmodSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import type { Game, Session } from '../../shared/types';
import { createTestContext, type TestContext } from './helpers';

let ctx: TestContext | null = null;
afterEach(() => {
  ctx?.close();
  ctx = null;
});

function makeExe(name = 'game.sh'): string {
  const dir = mkdtempSync(path.join(tmpdir(), 'ugl-launch-'));
  const exe = path.join(dir, name);
  writeFileSync(exe, '#!/bin/sh\necho hi\n');
  chmodSync(exe, 0o755);
  return exe;
}

async function addGame(exe: string): Promise<Game> {
  const res = await ctx!.call('library.addManual', { path: exe });
  if (!res.ok) throw new Error(`add failed: ${res.error?.message}`);
  return res.data as Game;
}

describe('launch integration (stubbed spawn)', () => {
  it('launches via the stored path and records a completed session on exit', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const game = await addGame(exe);

    const launched = (await ctx.call('games.launch', { id: game.id })) as {
      ok: boolean;
      data: { sessionId: string; alreadyRunning: boolean };
    };
    expect(launched.ok).toBe(true);
    expect(launched.data.alreadyRunning).toBe(false);

    // The spawn used the database path with shell disabled and structured argv.
    expect(ctx.stub.calls).toHaveLength(1);
    expect(ctx.stub.calls[0]!.exe).toBe(exe);
    expect(ctx.stub.calls[0]!.args).toEqual([]);
    expect(ctx.stub.calls[0]!.opts.shell).toBe(false);

    ctx.stub.closeLast(0);
    const sessions = (await ctx.call('sessions.list', { gameId: game.id })) as {
      ok: boolean;
      data: Session[];
    };
    expect(sessions.data).toHaveLength(1);
    expect(sessions.data[0]!.state).toBe('completed');
    expect(sessions.data[0]!.endedAt).not.toBeNull();
    expect(sessions.data[0]!.durationMs).toBeGreaterThanOrEqual(0);

    const games = (await ctx.call('library.list', {})) as { ok: boolean; data: Game[] };
    expect(games.data[0]!.lastPlayedAt).not.toBeNull();
    expect(games.data[0]!.totalPlayMs).toBeGreaterThanOrEqual(0);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });

  it('returns the existing session on rapid double-launch (no duplicate process)', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const game = await addGame(exe);
    const first = (await ctx.call('games.launch', { id: game.id })) as {
      ok: boolean;
      data: { sessionId: string; alreadyRunning: boolean };
    };
    const second = (await ctx.call('games.launch', { id: game.id })) as {
      ok: boolean;
      data: { sessionId: string; alreadyRunning: boolean };
    };
    expect(second.data.alreadyRunning).toBe(true);
    expect(second.data.sessionId).toBe(first.data.sessionId);
    expect(ctx.stub.calls).toHaveLength(1);
    ctx.stub.closeLast(0);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });

  it('launching an unknown id fails cleanly', async () => {
    ctx = createTestContext();
    const res = await ctx.call('games.launch', { id: 'nope' });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('NOT_FOUND');
    expect(ctx.stub.calls).toHaveLength(0);
  });

  it('launching a game whose file vanished fails with an actionable error', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const game = await addGame(exe);
    rmSync(exe);
    const res = await ctx.call('games.launch', { id: game.id });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('FILE_NOT_FOUND');
    expect(ctx.stub.calls).toHaveLength(0);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });

  it('spawn errors finalize the session as interrupted without inventing time', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const game = await addGame(exe);
    const launched = (await ctx.call('games.launch', { id: game.id })) as {
      ok: boolean;
      data: { sessionId: string };
    };
    ctx.stub.errorLast('ENOENT');
    const sessions = (await ctx.call('sessions.list', { gameId: game.id })) as {
      ok: boolean;
      data: Session[];
    };
    expect(sessions.data).toHaveLength(1);
    expect(sessions.data[0]!.state).toBe('interrupted');
    expect(sessions.data[0]!.durationMs).toBeLessThanOrEqual(5000);
    expect(launched.data.sessionId).toBe(sessions.data[0]!.id);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });

  it('shutdown conservatively interrupts a still-running session', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const game = await addGame(exe);
    await ctx.call('games.launch', { id: game.id });
    // App quits without the process exiting.
    ctx.launcher.shutdown();
    const sessions = (await ctx.call('sessions.list', { gameId: game.id })) as {
      ok: boolean;
      data: Session[];
    };
    expect(sessions.data[0]!.state).toBe('interrupted');
    // Ended at the last checkpoint (== start here), so no phantom playtime.
    expect(sessions.data[0]!.durationMs).toBeLessThanOrEqual(5000);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });

  it('live session duration comes from the monotonic clock, not the wall clock', async () => {
    // The wall clock barely advances during this test (~ms), while the
    // injected monotonic clock advances 90 s. A wall-clock implementation
    // would record ~0 ms; the recorded duration must be the monotonic one
    // so system-clock jumps during play cannot inflate or erase playtime.
    let mono = 1_000_000;
    ctx = createTestContext({ monotonicNow: () => mono });
    const exe = makeExe();
    const game = await addGame(exe);
    const launched = (await ctx.call('games.launch', { id: game.id })) as {
      ok: boolean;
      data: { sessionId: string };
    };
    expect(launched.ok).toBe(true);
    mono += 90_000;
    ctx.stub.closeLast(0);
    const sessions = (await ctx.call('sessions.list', { gameId: game.id })) as {
      ok: boolean;
      data: Session[];
    };
    expect(sessions.data).toHaveLength(1);
    expect(sessions.data[0]!.state).toBe('completed');
    expect(sessions.data[0]!.durationMs).toBe(90_000);
    const games = (await ctx.call('library.list', {})) as { ok: boolean; data: Game[] };
    expect(games.data[0]!.totalPlayMs).toBe(90_000);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });

  it('disabling tracking mid-game finalizes the live session and records nothing further', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const game = await addGame(exe);
    const launched = (await ctx.call('games.launch', { id: game.id })) as {
      ok: boolean;
      data: { sessionId: string };
    };
    expect(launched.ok).toBe(true);

    // The user turns tracking off while the game is still running.
    const upd = await ctx.call('settings.update', { trackingEnabled: false });
    expect(upd.ok).toBe(true);

    // The live session is finalized at that moment — not left running
    // until the process exits.
    const sessions = (await ctx.call('sessions.list', { gameId: game.id })) as {
      ok: boolean;
      data: Session[];
    };
    expect(sessions.data).toHaveLength(1);
    expect(sessions.data[0]!.state).toBe('interrupted');
    expect(sessions.data[0]!.endedAt).not.toBeNull();
    expect(sessions.data[0]!.notes).toContain('Tracking was turned off');
    const totalsAtDisable = (
      (await ctx.call('library.list', {})) as { ok: boolean; data: Game[] }
    ).data[0]!.totalPlayMs;

    // The game is still tracked as running (a second launch is a no-op),
    // but its eventual exit records nothing more.
    expect(ctx.launcher.runningCount()).toBe(1);
    const again = (await ctx.call('games.launch', { id: game.id })) as {
      ok: boolean;
      data: { alreadyRunning: boolean };
    };
    expect(again.data.alreadyRunning).toBe(true);
    ctx.stub.closeLast(0);
    expect(ctx.launcher.runningCount()).toBe(0);
    const after = (await ctx.call('sessions.list', { gameId: game.id })) as {
      ok: boolean;
      data: Session[];
    };
    expect(after.data).toHaveLength(1);
    const totalsAfterExit = (
      (await ctx.call('library.list', {})) as { ok: boolean; data: Game[] }
    ).data[0]!.totalPlayMs;
    expect(totalsAfterExit).toBe(totalsAtDisable);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });

  it('tracking disabled: launches without recording a session', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const game = await addGame(exe);
    await ctx.call('settings.update', { trackingEnabled: false });
    const launched = (await ctx.call('games.launch', { id: game.id })) as {
      ok: boolean;
      data: { sessionId: string | null };
    };
    expect(launched.ok).toBe(true);
    expect(launched.data.sessionId).toBeNull();
    expect(ctx.stub.calls).toHaveLength(1);
    const sessions = (await ctx.call('sessions.list', {})) as { ok: boolean; data: Session[] };
    expect(sessions.data).toHaveLength(0);
    ctx.stub.closeLast(0);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });
});
