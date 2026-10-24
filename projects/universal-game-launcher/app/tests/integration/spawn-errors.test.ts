/** Regression tests for async spawn failures: every spawn site must handle the
 * async 'error' event, distinguish "launch requested" from "process confirmed
 * started", and never let an unhandled error crash the app. */
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Game, Session } from '../../shared/types';
import { IpcChannels } from '../../shared/ipc-channels';
import { FakeBattleNetOs, fakeBattleNetInstall } from '../battlenet-helpers';
import { createTestContext, type TestContext } from './helpers';

let ctx: TestContext | null = null;
const tempDirs: string[] = [];
afterEach(() => {
  ctx?.close();
  ctx = null;
  for (const d of tempDirs.splice(0)) rmSync(d, { recursive: true, force: true });
});

function windowsOs(): FakeBattleNetOs {
  const os = new FakeBattleNetOs();
  os.platform = 'win32';
  return fakeBattleNetInstall(os);
}

function makeExe(name = 'game.sh'): string {
  const dir = mkdtempSync(path.join(tmpdir(), 'ugl-spawn-'));
  tempDirs.push(dir);
  const exe = path.join(dir, name);
  writeFileSync(exe, '#!/bin/sh\necho hi\n');
  chmodSync(exe, 0o755);
  return exe;
}

/** Let the IPC handler run until it is awaiting the spawn/error race. */
async function tick(): Promise<void> {
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
}

describe('Battle.net openClient async failures', () => {
  it('reports success only after the OS confirms the process started', async () => {
    ctx = createTestContext({ battleNetOs: windowsOs() });
    const res = await ctx.call(IpcChannels.sourcesOpenClient, { source: 'battlenet' });
    expect(res.ok).toBe(true);
    expect((res.data as { opened: boolean }).opened).toBe(true);
    expect(ctx.stub.calls).toHaveLength(1);
  });

  it('handles an async ENOENT as moved/uninstalled instead of crashing', async () => {
    ctx = createTestContext({ battleNetOs: windowsOs() });
    ctx.stub.autoSpawn = false;
    const promise = ctx.call(IpcChannels.sourcesOpenClient, { source: 'battlenet' });
    await tick();
    ctx.stub.errorLast('spawn Battle.net.exe ENOENT', 'ENOENT');
    const res = await promise;
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('LAUNCH_FAILED');
    expect(res.error?.message).toContain('moved or uninstalled');
  });

  it('handles an async EACCES with a permission-denied message', async () => {
    ctx = createTestContext({ battleNetOs: windowsOs() });
    ctx.stub.autoSpawn = false;
    const promise = ctx.call(IpcChannels.sourcesOpenClient, { source: 'battlenet' });
    await tick();
    ctx.stub.errorLast('spawn Battle.net.exe EACCES', 'EACCES');
    const res = await promise;
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('LAUNCH_FAILED');
    expect(res.error?.message).toContain('permission denied');
  });

  it('handles a synchronous spawn throw without crashing', async () => {
    ctx = createTestContext({ battleNetOs: windowsOs() });
    ctx.launcher = new (await import('../../electron/main/launch/launcher')).GameLauncher({
      db: ctx.deps.db,
      spawnImpl: () => {
        throw new Error('sync boom');
      },
      battleNetOs: windowsOs(),
    });
    // Rebuild deps with the throwing launcher.
    const { createHandlers } = await import('../../electron/main/ipc/handlers');
    const handlers = createHandlers();
    const def = handlers.find((h) => h.channel === IpcChannels.sourcesOpenClient)!;
    const deps = { ...ctx.deps, launcher: ctx.launcher };
    let result: { ok: boolean; error?: { code: string } };
    try {
      const parsed = (def.schema as { parse: (p: unknown) => unknown }).parse({
        source: 'battlenet',
      });
      await def.run(parsed as never, deps);
      result = { ok: true };
    } catch (err) {
      result = { ok: false, error: { code: (err as { code?: string }).code ?? '?' } };
    }
    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe('LAUNCH_REQUEST_FAILED');
  });

  it('an async error never becomes an unhandled error event', async () => {
    ctx = createTestContext({ battleNetOs: windowsOs() });
    ctx.stub.autoSpawn = false;
    const onUncaught = vi.fn();
    process.once('uncaughtException', onUncaught);
    try {
      const promise = ctx.call(IpcChannels.sourcesOpenClient, { source: 'battlenet' });
      await tick();
      ctx.stub.errorLast('boom', 'ENOENT');
      await promise;
      await tick();
    } finally {
      process.removeListener('uncaughtException', onUncaught);
    }
    expect(onUncaught).not.toHaveBeenCalled();
  });
});

describe('manual launch async failures', () => {
  async function addGame(exe: string): Promise<Game> {
    const res = await ctx!.call('library.addManual', { path: exe });
    if (!res.ok) throw new Error(`add failed: ${res.error?.message}`);
    return res.data as Game;
  }

  it('async spawn error finalizes the session as interrupted without crashing', async () => {
    ctx = createTestContext();
    const game = await addGame(makeExe());
    ctx.stub.autoSpawn = false;
    const promise = ctx.call('games.launch', { id: game.id });
    await tick();
    ctx.stub.errorLast('spawn game.sh ENOENT', 'ENOENT');
    const launched = await promise;
    // launch() resolved before the async error (spawnImpl returned); the
    // failure is recorded on the session, not thrown to the caller.
    expect(launched.ok).toBe(true);
    await tick();
    const sessions = (await ctx.call('sessions.list', { gameId: game.id })) as {
      ok: boolean;
      data: Session[];
    };
    expect(sessions.data).toHaveLength(1);
    expect(sessions.data[0]!.state).toBe('interrupted');
    expect(sessions.data[0]!.notes).toContain('failed to start');
    expect(ctx.launcher.runningCount()).toBe(0);
  });

  it('unexpected early termination records a completed session, no crash', async () => {
    ctx = createTestContext();
    const game = await addGame(makeExe());
    const launched = await ctx.call('games.launch', { id: game.id });
    expect(launched.ok).toBe(true);
    // Process exits almost immediately with a failure code.
    ctx.stub.closeLast(1);
    const sessions = (await ctx.call('sessions.list', { gameId: game.id })) as {
      ok: boolean;
      data: Session[];
    };
    expect(sessions.data).toHaveLength(1);
    expect(sessions.data[0]!.state).toBe('completed');
    expect(ctx.launcher.runningCount()).toBe(0);
  });
});
