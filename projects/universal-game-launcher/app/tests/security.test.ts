/**
 * AT-07 security checks that can run headless (no shell, no real processes).
 * - The renderer cannot make the app run an arbitrary command or path.
 * - Launch never uses shell string concatenation; argv stays structured.
 * - Manifest/data strings never become commands (no manifest parsing in M1;
 *   the invariant is enforced structurally and asserted here).
 * - Errors crossing IPC are sanitized (no stacks, no unrelated paths).
 */
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import type { Game } from '../../shared/types';
import { createTestContext, type TestContext } from './integration/helpers';

let ctx: TestContext | null = null;
afterEach(() => {
  ctx?.close();
  ctx = null;
});

function makeExe(name = 'game.sh'): string {
  const dir = mkdtempSync(path.join(tmpdir(), 'ugl-sec-'));
  const exe = path.join(dir, name);
  writeFileSync(exe, '#!/bin/sh\necho hi\n');
  chmodSync(exe, 0o755);
  return exe;
}

describe('AT-07 security (headless)', () => {
  it('renderer cannot smuggle a raw path into launch: strict schema rejects extra fields', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const added = (await ctx.call('library.addManual', { path: exe })) as {
      ok: boolean;
      data: Game;
    };
    // An attacker-controlled payload carrying an arbitrary path is rejected
    // before it ever reaches the launcher.
    const evil = await ctx.call('games.launch', { id: added.data.id, path: '/tmp/evil.sh' });
    expect(evil.ok).toBe(false);
    expect(evil.error?.code).toBe('VALIDATION_ERROR');
    expect(ctx.stub.calls).toHaveLength(0);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });

  it('spawn is always invoked with shell:false and a structured argv array', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const added = (await ctx.call('library.addManual', {
      path: exe,
      args: ['--name', 'a; rm -rf /', '$(evil)', '`backtick`'],
    })) as { ok: boolean; data: Game };
    await ctx.call('games.launch', { id: added.data.id });
    expect(ctx.stub.calls).toHaveLength(1);
    const call = ctx.stub.calls[0]!;
    expect(call.opts.shell).toBe(false);
    // Metacharacters arrive as literal argv elements — never concatenated.
    expect(call.args).toEqual(['--name', 'a; rm -rf /', '$(evil)', '`backtick`']);
    expect(typeof call.exe).toBe('string');
    ctx.stub.closeLast(0);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });

  it('a hostile title cannot alter what gets executed', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const added = (await ctx.call('library.addManual', { path: exe })) as {
      ok: boolean;
      data: Game;
    };
    await ctx.call('library.update', { id: added.data.id, title: 'x"; rm -rf / #' });
    await ctx.call('games.launch', { id: added.data.id });
    expect(ctx.stub.calls[0]!.exe).toBe(exe);
    ctx.stub.closeLast(0);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });

  it('IPC errors are sanitized: no stack traces leak to the renderer', async () => {
    ctx = createTestContext();
    const res = await ctx.call('library.remove', { id: 'does-not-exist' });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('NOT_FOUND');
    expect(JSON.stringify(res)).not.toContain('at ');
    expect('stack' in (res.error ?? {})).toBe(false);
  });

  it('preload exposes no raw ipcRenderer: contract check', async () => {
    const fs = await import('node:fs');
    const preload = fs.readFileSync(
      new URL('../electron/preload/index.ts', import.meta.url),
      'utf8',
    );
    expect(preload).not.toMatch(/exposeInMainWorld\(\s*['"]ipcRenderer['"]/);
    expect(preload).toContain("exposeInMainWorld('gameLauncher'");
  });
});
