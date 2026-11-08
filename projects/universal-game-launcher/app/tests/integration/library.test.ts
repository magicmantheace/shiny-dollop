import { chmodSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import type { Game } from '../../shared/types';
import { createTestContext, type TestContext } from './helpers';

let ctx: TestContext | null = null;
afterEach(() => {
  ctx?.close();
  ctx = null;
});

function makeExe(name = 'game.sh'): string {
  const dir = mkdtempSync(path.join(tmpdir(), 'ugl-lib-'));
  const exe = path.join(dir, name);
  writeFileSync(exe, '#!/bin/sh\necho hi\n');
  chmodSync(exe, 0o755);
  return exe;
}

async function addGame(exe: string, extra: Record<string, unknown> = {}): Promise<Game> {
  const res = await ctx!.call('library.addManual', { path: exe, ...extra });
  expect(res.ok).toBe(true);
  return res.data as Game;
}

describe('library IPC integration', () => {
  it('adds, lists, updates, favorites, removes and re-adds a game', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const game = await addGame(exe);
    expect(game.title).toBe('game');
    expect(game.missing).toBe(false);

    const list1 = (await ctx.call('library.list', {})) as { ok: boolean; data: Game[] };
    expect(list1.data).toHaveLength(1);

    const updated = (await ctx.call('library.update', { id: game.id, title: 'Renamed' })) as {
      ok: boolean;
      data: Game;
    };
    expect(updated.data.title).toBe('Renamed');

    const fav = (await ctx.call('library.setFavorite', { id: game.id, favorite: true })) as {
      ok: boolean;
      data: Game;
    };
    expect(fav.data.favorite).toBe(true);

    const favOnly = (await ctx.call('library.list', { favoritesOnly: true })) as {
      ok: boolean;
      data: Game[];
    };
    expect(favOnly.data).toHaveLength(1);

    const removed = await ctx.call('library.remove', { id: game.id });
    expect(removed.ok).toBe(true);
    const list2 = (await ctx.call('library.list', {})) as { ok: boolean; data: Game[] };
    expect(list2.data).toHaveLength(0);

    // Re-add works after removal.
    await addGame(exe);
    const list3 = (await ctx.call('library.list', {})) as { ok: boolean; data: Game[] };
    expect(list3.data).toHaveLength(1);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });

  it('rejects duplicates by canonical path', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    await addGame(exe);
    const dup = await ctx.call('library.addManual', { path: exe });
    expect(dup.ok).toBe(false);
    expect(dup.error?.code).toBe('DUPLICATE');
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });

  it('rejects a missing executable with an actionable error', async () => {
    ctx = createTestContext();
    const res = await ctx.call('library.addManual', { path: '/nope/never-there-ugl.exe' });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('FILE_NOT_FOUND');
    expect(res.error?.message).toContain('not found');
  });

  it('reports a game as missing after its file is deleted', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const game = await addGame(exe);
    rmSync(exe);
    const list = (await ctx.call('library.list', {})) as { ok: boolean; data: Game[] };
    expect(list.data[0]!.missing).toBe(true);
    // The library entry still exists (nothing was deleted by the app).
    expect(list.data[0]!.id).toBe(game.id);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });

  it('search is case-insensitive and sort orders work', async () => {
    ctx = createTestContext();
    const e1 = makeExe('zebra.sh');
    const e2 = makeExe('apple.sh');
    await addGame(e1);
    const g2 = await addGame(e2);
    await ctx.call('library.update', { id: g2.id, title: 'Apple Game' });

    const search = (await ctx.call('library.list', { search: 'APPLE' })) as {
      ok: boolean;
      data: Game[];
    };
    expect(search.data).toHaveLength(1);
    expect(search.data[0]!.title).toBe('Apple Game');

    const sorted = (await ctx.call('library.list', { sort: 'title' })) as {
      ok: boolean;
      data: Game[];
    };
    expect(sorted.data.map((g) => g.title)).toEqual(['Apple Game', 'zebra']);
    rmSync(path.dirname(e1), { recursive: true, force: true });
    rmSync(path.dirname(e2), { recursive: true, force: true });
  });

  it('remove is non-destructive: the target file survives', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const game = await addGame(exe);
    await ctx.call('library.remove', { id: game.id });
    const { existsSync } = await import('node:fs');
    expect(existsSync(exe)).toBe(true);
    rmSync(path.dirname(exe), { recursive: true, force: true });
  });
});
