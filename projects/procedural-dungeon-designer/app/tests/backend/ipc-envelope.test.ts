import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { PDD_CHANNELS } from '../../electron/main/channels.js';
import { createHandlers } from '../../electron/main/ipc.js';
import { insertDungeon } from '../../electron/main/store.js';
import { isPddError, pddError, PDD_ERROR_CODES } from '../../shared/errors.js';
import {
  errorEnvelope,
  isIpcEnvelope,
  successEnvelope,
  unwrapIpcEnvelope,
} from '../../shared/ipc-envelope.js';
import type { DungeonMap, SavedDungeon } from '../../shared/types.js';
import { makeFixture } from './helpers.js';

// Regression tests for the IPC error contract: Electron serializes errors
// thrown through ipcMain.handle down to their message, so a thrown
// { code, message } loses its code before the renderer can display it.
// Handlers must therefore RETURN a structured envelope as response data,
// and the preload unwraps it back into a thrown { code, message }.

function tinySavedDungeon(): SavedDungeon {
  const row = '#'.repeat(12);
  const map: DungeonMap = {
    params: {
      seed: 'tiny',
      gridWidth: 12,
      gridHeight: 12,
      roomCount: 3,
      theme: 'sunken-crypt',
      difficulty: 1,
    },
    gridWidth: 12,
    gridHeight: 12,
    tiles: Array.from({ length: 12 }, () => row),
    rooms: [
      {
        id: 'room-1',
        name: 'Tiny Vault',
        x: 1,
        y: 1,
        w: 3,
        h: 3,
        cx: 2,
        cy: 2,
        isEntrance: true,
        placements: [],
      },
    ],
    budgetLimit: 3,
    budgetUsed: 0,
  };
  return {
    id: 'tiny-1',
    name: 'Tiny',
    createdAt: '2026-10-24T00:00:00.000Z',
    updatedAt: '2026-10-24T00:00:00.000Z',
    map,
  };
}

describe('ipc envelope (shared wrap/unwrap logic)', () => {
  it('success envelope unwraps to the value', () => {
    const envelope = successEnvelope({ answer: 42 });
    expect(isIpcEnvelope(envelope)).toBe(true);
    expect(unwrapIpcEnvelope(envelope)).toEqual({ answer: 42 });
  });

  it('error envelope unwraps by throwing the named { code, message } error', () => {
    const envelope = errorEnvelope(
      pddError(PDD_ERROR_CODES.BUDGET_EXCEEDED, 'over budget'),
    );
    expect(isIpcEnvelope(envelope)).toBe(true);
    let thrown: unknown;
    try {
      unwrapIpcEnvelope(envelope);
    } catch (err) {
      thrown = err;
    }
    expect(thrown).toMatchObject({
      code: 'BUDGET_EXCEEDED',
      message: 'over budget',
    });
    expect(isPddError(thrown)).toBe(true);
  });

  it('rejects values that are not envelopes', () => {
    expect(isIpcEnvelope(null)).toBe(false);
    expect(isIpcEnvelope({ code: 'BUDGET_EXCEEDED', message: 'x' })).toBe(false);
    expect(isIpcEnvelope({ ok: true })).toBe(false);
    expect(isIpcEnvelope({ ok: false })).toBe(false);
  });
});

describe('ipc handlers return envelopes instead of throwing', () => {
  it('a successful call resolves to a success envelope carrying the value', async () => {
    const { service, db } = makeFixture();
    const handlers = createHandlers(service);
    const result = await handlers[PDD_CHANNELS.themesList]!();
    expect(isIpcEnvelope(result)).toBe(true);
    expect(result).toMatchObject({ ok: true });
    const themes = unwrapIpcEnvelope(result as never) as Array<{ id: string }>;
    expect(themes.map((t) => t.id)).toContain('sunken-crypt');
    db.close();
  });

  it('an over-budget placement resolves to an error envelope keeping BUDGET_EXCEEDED', async () => {
    const { service, db } = makeFixture();
    insertDungeon(db, tinySavedDungeon());
    const handlers = createHandlers(service);
    // Pale Warden costs 10 against a budget limit of 3: the service throws
    // BUDGET_EXCEEDED. Through the real bridge this must arrive as data,
    // not as a thrown error whose code Electron would strip.
    const result = await handlers[PDD_CHANNELS.placementsAdd]!('tiny-1', {
      roomId: 'room-1',
      kind: 'encounter',
      key: 'pale-warden',
    });
    expect(result).toEqual({
      ok: false,
      error: {
        code: 'BUDGET_EXCEEDED',
        message: expect.stringContaining('exceed the budget'),
      },
    });
    // And unwrapping (what the preload does) restores the named error.
    expect(() => unwrapIpcEnvelope(result as never)).toThrowError(
      expect.objectContaining({ code: 'BUDGET_EXCEEDED' }),
    );
    db.close();
  });

  it('invalid arguments resolve to an error envelope, not a throw', async () => {
    const { service, db } = makeFixture();
    const handlers = createHandlers(service);
    const result = await handlers[PDD_CHANNELS.generate]!({ seed: '' });
    expect(isIpcEnvelope(result)).toBe(true);
    expect(result).toMatchObject({ ok: false, error: { code: 'PARAMS_INVALID' } });
    db.close();
  });
});

describe('preload envelope handling (source guard)', () => {
  function readPreloadSource(): string {
    const candidates = [
      join(process.cwd(), 'electron/preload/preload.ts'),
      join(process.cwd(), 'projects/procedural-dungeon-designer/app/electron/preload/preload.ts'),
    ];
    for (const candidate of candidates) {
      if (existsSync(candidate)) return readFileSync(candidate, 'utf8');
    }
    throw new Error(`preload.ts not found; tried: ${candidates.join(', ')}`);
  }

  it('unwraps the envelope returned by ipcRenderer.invoke and rethrows its error', () => {
    const source = readPreloadSource();
    // The sandboxed preload cannot import shared/ipc-envelope at runtime,
    // so it carries an inline copy of the unwrap logic. Guard that the
    // copy exists and actually throws the envelope's named error, so the
    // two implementations cannot silently drift apart.
    expect(source).toContain('unwrapEnvelope');
    expect(source).toContain('envelope.ok');
    expect(source).toContain('throw envelope.error');
  });
});
