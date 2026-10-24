/** Regression tests for the custom-title-on-Add defect: the Add Game dialog's
 * title field must reach the backend and persist, with filename fallback when
 * the field is empty. */
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import type { Game } from '../../shared/types';
import { openDatabase } from '../../electron/main/data/database';
import { addManualGame, getGame, updateGame } from '../../electron/main/data/games';
import { createTestContext, type TestContext } from './helpers';

let ctx: TestContext | null = null;
const tempDirs: string[] = [];
afterEach(() => {
  ctx?.close();
  ctx = null;
  for (const d of tempDirs.splice(0)) rmSync(d, { recursive: true, force: true });
});

function makeExe(name = 'mygame.exe'): string {
  const dir = mkdtempSync(path.join(tmpdir(), 'ugl-title-'));
  tempDirs.push(dir);
  const exe = path.join(dir, name);
  writeFileSync(exe, '#!/bin/sh\necho hi\n');
  chmodSync(exe, 0o755);
  return exe;
}

async function addViaIpc(exe: string, extra: Record<string, unknown> = {}) {
  return ctx!.call('library.addManual', { path: exe, ...extra });
}

describe('custom titles on Add Game', () => {
  it('saves the exact custom title entered in the dialog', async () => {
    ctx = createTestContext();
    const res = await addViaIpc(makeExe(), { title: 'My Custom Title' });
    expect(res.ok).toBe(true);
    expect((res.data as Game).title).toBe('My Custom Title');
  });

  it('falls back to the exe filename when no title is sent', async () => {
    ctx = createTestContext();
    const res = await addViaIpc(makeExe('coolgame.exe'));
    expect(res.ok).toBe(true);
    expect((res.data as Game).title).toBe('coolgame');
  });

  it('falls back to the exe filename when the title is blank/whitespace', async () => {
    ctx = createTestContext();
    const res = await addViaIpc(makeExe('blankgame.exe'), { title: '   ' });
    expect(res.ok).toBe(true);
    expect((res.data as Game).title).toBe('blankgame');
  });

  it('trims surrounding whitespace from a custom title', async () => {
    ctx = createTestContext();
    const res = await addViaIpc(makeExe(), { title: '  Spaced Title  ' });
    expect(res.ok).toBe(true);
    expect((res.data as Game).title).toBe('Spaced Title');
  });

  it('rejects an over-length title at the IPC schema boundary', async () => {
    ctx = createTestContext();
    const res = await addViaIpc(makeExe(), { title: 'x'.repeat(257) });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('VALIDATION_ERROR');
  });

  it('rejects a non-string title at the IPC schema boundary', async () => {
    ctx = createTestContext();
    const res = await addViaIpc(makeExe(), { title: 42 });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('VALIDATION_ERROR');
  });

  it('allows updating the title afterwards', async () => {
    ctx = createTestContext();
    const exe = makeExe();
    const added = (await addViaIpc(exe, { title: 'First' })) as { ok: boolean; data: Game };
    const updated = (await ctx.call('library.update', {
      id: added.data.id,
      title: 'Second Title',
    })) as { ok: boolean; data: Game };
    expect(updated.ok).toBe(true);
    expect(updated.data.title).toBe('Second Title');
  });

  it('persists a custom title across a database restart', async () => {
    const dir = mkdtempSync(path.join(tmpdir(), 'ugl-title-db-'));
    tempDirs.push(dir);
    const dbPath = path.join(dir, 'library.db');
    const exe = makeExe('persist.exe');

    const db1 = openDatabase(dbPath);
    const created = await addManualGame(db1, { path: exe, title: 'Survives Restart' });
    expect(created.title).toBe('Survives Restart');
    db1.close();

    const db2 = openDatabase(dbPath);
    const reloaded = getGame(db2, created.id);
    expect(reloaded?.title).toBe('Survives Restart');
    db2.close();
  });

  it('updateGame still rejects an empty title', async () => {
    ctx = createTestContext();
    const added = (await addViaIpc(makeExe(), { title: 'Keep Me' })) as {
      ok: boolean;
      data: Game;
    };
    const res = await ctx.call('library.update', { id: added.data.id, title: '  ' });
    expect(res.ok).toBe(false);
    // Original title untouched.
    const still = getGame(ctx.deps.db, added.data.id);
    expect(still?.title).toBe('Keep Me');
    // Direct data-layer check too.
    await expect(updateGame(ctx.deps.db, { id: added.data.id, title: '' })).rejects.toThrow();
  });
});
