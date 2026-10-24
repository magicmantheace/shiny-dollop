/**
 * IPC handler tests. createHandlers() is exercised directly (no Electron
 * runtime needed) with an in-memory DB and MockOsLayer. Covers all twelve
 * channels, the approved===true gate, zod rejection of malformed input, and
 * progress event emission.
 */
import { describe, expect, it } from 'vitest';
import { createHandlers, type HandlerContext } from '../electron/main/ipc/handlers.js';
import { MockOsLayer } from '../electron/main/os-layer/mock.js';
import { GppDatabase } from '../electron/main/store/database.js';
import { ACTIVATION_PROGRESS_EVENT, type ActivationProgress } from '../shared/gpp-types.js';

const HIGH_PERF = '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c';

function ctx(os = new MockOsLayer()): { handlers: Record<string, (p: unknown) => Promise<unknown>>; db: GppDatabase; emitted: Array<{ event: string; payload: unknown }> } {
  const db = new GppDatabase(':memory:');
  const emitted: Array<{ event: string; payload: unknown }> = [];
  const context: HandlerContext = { db, os, emit: (event, payload) => emitted.push({ event, payload }) };
  return { handlers: createHandlers(context), db, emitted };
}

async function call(handlers: Record<string, (p: unknown) => Promise<unknown>>, channel: string, payload?: unknown) {
  return (await handlers[channel]!(payload)) as Record<string, unknown>;
}

describe('gpp:capabilities', () => {
  it('returns the four probed capabilities', async () => {
    const { handlers } = ctx();
    const res = await call(handlers, 'gpp:capabilities');
    const caps = res['capabilities'] as Array<{ id: string; supported: boolean }>;
    expect(caps.map((c) => c.id).sort()).toEqual([
      'fullscreen-optimizations',
      'game-mode',
      'power-plan',
      'process-priority',
    ]);
  });
});

describe('profile CRUD', () => {
  it('create → list → update → delete', async () => {
    const { handlers } = ctx();
    const created = (await call(handlers, 'gpp:profiles:create', {
      name: 'Racer',
      changes: [{ kind: 'game-mode', params: { enabled: 'true' } }],
    })) as { profile: { id: string; name: string } };
    expect(created.profile.name).toBe('Racer');

    const listed = (await call(handlers, 'gpp:profiles:list')) as { profiles: Array<{ id: string }> };
    expect(listed.profiles).toHaveLength(1);

    const updated = (await call(handlers, 'gpp:profiles:update', {
      id: created.profile.id,
      name: 'Racer 2',
    })) as { profile: { name: string } };
    expect(updated.profile.name).toBe('Racer 2');

    const del = await call(handlers, 'gpp:profiles:delete', { id: created.profile.id });
    expect(del).toEqual({ ok: true });
    const listed2 = (await call(handlers, 'gpp:profiles:list')) as { profiles: unknown[] };
    expect(listed2.profiles).toHaveLength(0);
  });

  it('rejects malformed input via zod', async () => {
    const { handlers } = ctx();
    expect(await call(handlers, 'gpp:profiles:create', { name: '', changes: [] })).toMatchObject({
      error: expect.any(String),
    });
    expect(
      await call(handlers, 'gpp:profiles:create', {
        name: 'X',
        changes: [{ kind: 'overclock', params: {} }],
      }),
    ).toMatchObject({ error: expect.any(String) });
    expect(await call(handlers, 'gpp:profiles:update', { id: 'nope', name: 'Y' })).toMatchObject({
      error: expect.stringContaining('not found'),
    });
    expect(await call(handlers, 'gpp:profiles:delete', { id: 'nope' })).toMatchObject({
      error: expect.stringContaining('not found'),
    });
  });
});

describe('gpp:profiles:activate approval gate', () => {
  it('rejects unless approved === true and touches nothing', async () => {
    const os = new MockOsLayer();
    const { handlers, db, emitted } = ctx(os);
    const created = (await call(handlers, 'gpp:profiles:create', {
      name: 'P',
      changes: [{ kind: 'game-mode', params: { enabled: 'true' } }],
    })) as { profile: { id: string } };

    // approved: false is rejected by the explicit-consent gate...
    const denied = await call(handlers, 'gpp:profiles:activate', { profileId: created.profile.id, approved: false });
    expect(denied).toMatchObject({ error: expect.stringContaining('explicit approval') });
    // ...and anything that is not exactly `true` is rejected (zod or gate).
    for (const approved of [undefined, null, 'true', 1]) {
      const res = await call(handlers, 'gpp:profiles:activate', { profileId: created.profile.id, approved });
      expect(res).toMatchObject({ error: expect.any(String) });
    }
    expect(os.appliedCalls).toBe(0);
    expect(os.snapshot.gameModeEnabled).toBe(false);
    expect(db.listJournal()).toHaveLength(0);
    expect(emitted).toHaveLength(0);
  });

  it('applies with approved: true and emits progress events', async () => {
    const os = new MockOsLayer();
    const { handlers, emitted } = ctx(os);
    const created = (await call(handlers, 'gpp:profiles:create', {
      name: 'P',
      changes: [
        { kind: 'game-mode', params: { enabled: 'true' } },
        { kind: 'power-plan', params: { guid: HIGH_PERF } },
      ],
    })) as { profile: { id: string } };

    const res = (await call(handlers, 'gpp:profiles:activate', {
      profileId: created.profile.id,
      approved: true,
    })) as { result: { ok: boolean; applied: string[] } };
    expect(res.result.ok).toBe(true);
    expect(res.result.applied).toHaveLength(2);

    const progressEvents = emitted.filter((e) => e.event === ACTIVATION_PROGRESS_EVENT);
    expect(progressEvents.length).toBeGreaterThan(0);
    const phases = progressEvents.map((e) => (e.payload as ActivationProgress).phase);
    expect(phases).toContain('applying');
    expect(phases).toContain('applied');
  });

  it('rejects unknown profile ids', async () => {
    const { handlers } = ctx();
    expect(await call(handlers, 'gpp:profiles:activate', { profileId: 'missing', approved: true })).toMatchObject({
      error: expect.stringContaining('not found'),
    });
    expect(await call(handlers, 'gpp:profiles:preview', { profileId: 'missing' })).toMatchObject({
      error: expect.stringContaining('not found'),
    });
  });
});

describe('gpp:profiles:preview', () => {
  it('returns planned changes with from/to', async () => {
    const { handlers } = ctx();
    const created = (await call(handlers, 'gpp:profiles:create', {
      name: 'P',
      changes: [{ kind: 'game-mode', params: { enabled: 'true' } }],
    })) as { profile: { id: string } };
    const res = (await call(handlers, 'gpp:profiles:preview', { profileId: created.profile.id })) as {
      planned: Array<{ kind: string; from: string; to: string; supported: boolean }>;
    };
    expect(res.planned).toHaveLength(1);
    expect(res.planned[0]).toMatchObject({ kind: 'game-mode', from: 'disabled', to: 'enabled', supported: true });
  });
});

describe('rollback / restoreAll / journal', () => {
  it('rollback restores state and journal lists entries', async () => {
    const os = new MockOsLayer();
    const { handlers } = ctx(os);
    const created = (await call(handlers, 'gpp:profiles:create', {
      name: 'P',
      changes: [{ kind: 'game-mode', params: { enabled: 'true' } }],
    })) as { profile: { id: string } };
    await call(handlers, 'gpp:profiles:activate', { profileId: created.profile.id, approved: true });
    expect(os.snapshot.gameModeEnabled).toBe(true);

    const rb = (await call(handlers, 'gpp:profiles:rollback', { profileId: created.profile.id })) as {
      result: { ok: boolean; rolledBack: string[] };
    };
    expect(rb.result.ok).toBe(true);
    expect(rb.result.rolledBack).toHaveLength(1);
    expect(os.snapshot.gameModeEnabled).toBe(false);

    const journal = (await call(handlers, 'gpp:journal:list')) as {
      entries: Array<{ rolledBackAt?: string }>;
    };
    expect(journal.entries).toHaveLength(1);
    expect(journal.entries[0]!.rolledBackAt).toBeDefined();
  });

  it('rollback with no entries succeeds trivially', async () => {
    const { handlers } = ctx();
    const res = (await call(handlers, 'gpp:profiles:rollback', { profileId: 'nothing' })) as {
      result: { ok: boolean; rolledBack: string[] };
    };
    expect(res.result).toMatchObject({ ok: true, rolledBack: [] });
  });

  it('restoreAll rolls back everything', async () => {
    const os = new MockOsLayer();
    const { handlers } = ctx(os);
    const created = (await call(handlers, 'gpp:profiles:create', {
      name: 'P',
      changes: [{ kind: 'game-mode', params: { enabled: 'true' } }],
    })) as { profile: { id: string } };
    await call(handlers, 'gpp:profiles:activate', { profileId: created.profile.id, approved: true });
    const res = (await call(handlers, 'gpp:profiles:restoreAll', {})) as {
      result: { ok: boolean; rolledBack: string[] };
    };
    expect(res.result.ok).toBe(true);
    expect(res.result.rolledBack).toHaveLength(1);
    expect(os.snapshot.gameModeEnabled).toBe(false);
  });
});

describe('snapshots', () => {
  it('take → list round-trips with the approximate note', async () => {
    const { handlers } = ctx();
    const taken = (await call(handlers, 'gpp:snapshots:take', { label: 'before' })) as {
      snapshot: { label: string; note: string; cpuPercent: number };
    };
    expect(taken.snapshot.label).toBe('before');
    expect(taken.snapshot.note).toBe('approximate — point-in-time estimate, not a benchmark');
    expect(typeof taken.snapshot.cpuPercent).toBe('number');
    const listed = (await call(handlers, 'gpp:snapshots:list')) as { snapshots: unknown[] };
    expect(listed.snapshots).toHaveLength(1);
    expect(await call(handlers, 'gpp:snapshots:take', { label: '' })).toMatchObject({
      error: expect.any(String),
    });
  });
});
