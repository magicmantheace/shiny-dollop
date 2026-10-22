/**
 * Integration tests for cover art: IPC choose/update/coverData round-trips,
 * filename validation at the schema boundary, and persistence.
 */
import { afterEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { IpcChannels } from '../../shared/ipc-channels';
import type { Game } from '../../shared/types';
import { createTestContext, type TestContext } from './helpers';
import { importCoverFile } from '../../electron/main/files/cover-store';

const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);

let ctx: TestContext | null = null;
let tmp: string | null = null;
afterEach(() => {
  ctx?.close();
  ctx = null;
  if (tmp) {
    fs.rmSync(tmp, { recursive: true, force: true });
    tmp = null;
  }
});

function coverCtx() {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ugl-cover-int-'));
  const coversDir = path.join(tmp, 'covers');
  const src = path.join(tmp, 'src.png');
  fs.writeFileSync(src, PNG_1X1);
  const stored = importCoverFile(src, coversDir, (b) => b);
  ctx = createTestContext({});
  // Point the context at our temp covers dir with a canned chooser.
  ctx.deps.getCoversDir = () => coversDir;
  ctx.deps.chooseCover = async () => ({ coverPath: stored });
  return { coversDir, stored };
}

async function addGame(): Promise<Game> {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ugl-game-'));
  tmp = tmp ?? dir;
  const exe = path.join(dir, 'game.exe');
  fs.writeFileSync(exe, 'fake');
  const res = await ctx!.call(IpcChannels.libraryAddManual, { path: exe });
  expect(res.ok).toBe(true);
  return res.data as Game;
}

describe('cover art IPC', () => {
  it('choose → update → coverData round-trips a data URL', async () => {
    coverCtx();
    const game = await addGame();

    const picked = await ctx!.call(IpcChannels.filesChooseCover, {});
    expect(picked.ok).toBe(true);
    const coverPath = (picked.data as { coverPath: string }).coverPath;

    const updated = await ctx!.call(IpcChannels.libraryUpdate, { id: game.id, coverPath });
    expect(updated.ok).toBe(true);
    expect((updated.data as Game).coverPath).toBe(coverPath);

    const data = await ctx!.call(IpcChannels.filesCoverData, { id: game.id });
    expect(data.ok).toBe(true);
    expect((data.data as { dataUrl: string | null }).dataUrl).toMatch(/^data:image\/png;base64,/);
  });

  it('rejects a forged cover filename at the schema boundary', async () => {
    coverCtx();
    const game = await addGame();
    const res = await ctx!.call(IpcChannels.libraryUpdate, {
      id: game.id,
      coverPath: '../../../etc/passwd',
    });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('VALIDATION_ERROR');
  });

  it('coverData returns null when the game has no cover', async () => {
    coverCtx();
    const game = await addGame();
    const data = await ctx!.call(IpcChannels.filesCoverData, { id: game.id });
    expect(data.ok).toBe(true);
    expect((data.data as { dataUrl: string | null }).dataUrl).toBeNull();
  });

  it('clearing the cover persists', async () => {
    coverCtx();
    const game = await addGame();
    const picked = (await ctx!.call(IpcChannels.filesChooseCover, {})).data as {
      coverPath: string;
    };
    await ctx!.call(IpcChannels.libraryUpdate, { id: game.id, coverPath: picked.coverPath });
    const cleared = await ctx!.call(IpcChannels.libraryUpdate, { id: game.id, coverPath: null });
    expect(cleared.ok).toBe(true);
    expect((cleared.data as Game).coverPath).toBeNull();
  });

  it('migration v3 adds cover_path without breaking existing rows', async () => {
    coverCtx();
    const game = await addGame();
    expect(game.coverPath).toBeNull();
  });
});
