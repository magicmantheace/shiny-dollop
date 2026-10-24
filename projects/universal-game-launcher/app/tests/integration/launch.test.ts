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
