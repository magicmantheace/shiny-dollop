/**
 * Engine tests against MockOsLayer: preview, activation (success + failure
 * rollback), rollback, restore-all, and snapshots. All state is synthetic.
 */
import { describe, expect, it } from 'vitest';
import { MockOsLayer } from '../electron/main/os-layer/mock.js';
import { GppDatabase } from '../electron/main/store/database.js';
import {
  activateProfile,
  previewProfile,
  restoreAll,
  rollbackProfile,
  takeSnapshot,
  validateParams,
} from '../electron/main/engine/index.js';
import { seedProfile, SEED_PROFILE_NAME } from '../electron/main/seed.js';
import type { ActivationProgress, Profile } from '../shared/gpp-types.js';

const GUID = '381b4222-f694-41f0-9685-ff5bb260df2e';
const HIGH_PERF = '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c';

function makeProfile(changes: Profile['changes'], name = 'Test'): Profile {
  const now = new Date().toISOString();
  return { id: 'p1', name, changes, createdAt: now, updatedAt: now };
}

function memDb(): GppDatabase {
  return new GppDatabase(':memory:');
}

describe('previewProfile', () => {
  it('resolves from/to for every change, marks reversible and supported', async () => {
    const os = new MockOsLayer();
    const profile = makeProfile([
      { kind: 'game-mode', params: { enabled: 'true' } },
      { kind: 'power-plan', params: { guid: HIGH_PERF } },
    ]);
    const planned = await previewProfile(profile, os);
    expect(planned).toHaveLength(2);
    expect(planned[0]).toMatchObject({
      kind: 'game-mode',
      from: 'disabled',
      to: 'enabled',
      reversible: true,
      supported: true,
    });
    expect(planned[1]).toMatchObject({ kind: 'power-plan', from: GUID, to: HIGH_PERF, supported: true });
    expect(planned[0]!.changeId).not.toBe(planned[1]!.changeId);
  });

  it('reflects current mock state in `from`', async () => {
    const os = new MockOsLayer({ initial: { gameModeEnabled: true } });
    const profile = makeProfile([{ kind: 'game-mode', params: { enabled: 'false' } }]);
    const [p] = await previewProfile(profile, os);
    expect(p!.from).toBe('enabled');
    expect(p!.to).toBe('disabled');
  });

  it('marks unsupported capabilities with a reason and never reads the OS', async () => {
    const os = new MockOsLayer({ unsupportedCapabilities: new Set(['power-plan']) });
    const profile = makeProfile([{ kind: 'power-plan', params: { guid: HIGH_PERF } }]);
    const [p] = await previewProfile(profile, os);
    expect(p!.supported).toBe(false);
    expect(p!.unsupportedReason).toMatch(/power-plan/);
    expect(os.appliedCalls).toBe(0);
  });

  it('flags an empty power-plan GUID as unsupported with a pick-in-UI reason', async () => {
    const os = new MockOsLayer();
    const profile = makeProfile([{ kind: 'power-plan', params: { guid: '' } }]);
    const [p] = await previewProfile(profile, os);
    expect(p!.supported).toBe(false);
    expect(p!.unsupportedReason).toMatch(/pick a power plan/i);
  });

  it('flags unknown change kinds without touching the OS', async () => {
    const os = new MockOsLayer();
    const profile = makeProfile([{ kind: 'overclock' as never, params: {} }]);
    const [p] = await previewProfile(profile, os);
    expect(p!.supported).toBe(false);
    expect(p!.reversible).toBe(false);
    expect(p!.unsupportedReason).toMatch(/Unknown change kind/);
    expect(os.appliedCalls).toBe(0);
  });
});

describe('activateProfile — success path', () => {
  it('define → preview → approve → apply → exact values in mock → rollback → prior values restored', async () => {
    const os = new MockOsLayer();
    const db = memDb();
    const progress: ActivationProgress[] = [];
    const profile = makeProfile([
      { kind: 'game-mode', params: { enabled: 'true' } },
      { kind: 'power-plan', params: { guid: HIGH_PERF } },
      { kind: 'process-priority', params: { imageName: 'game.exe', priority: 'high' } },
      { kind: 'fullscreen-optimizations', params: { childKey: 'test-game', disableFse: 'true' } },
    ]);

    const planned = await previewProfile(profile, os);
    expect(planned.every((p) => p.supported)).toBe(true);

    const result = await activateProfile(profile, os, {
      db,
      onProgress: (p) => progress.push(p),
    });
    expect(result.ok).toBe(true);
    expect(result.error).toBeUndefined();
    expect(result.applied).toHaveLength(4);
    expect(result.skipped).toHaveLength(0);

    // exact values in the mock
    const s = os.snapshot;
    expect(s.gameModeEnabled).toBe(true);
    expect(s.activePowerGuid).toBe(HIGH_PERF);
    expect(s.processPriorities['game.exe']).toBe('high');
    expect(s.fullscreenOptimizations['test-game']).toBe('disabled');

    // journal exactness
    const journal = db.listJournal();
    expect(journal).toHaveLength(4);
    expect(journal[0]).toMatchObject({ changeKind: 'game-mode', before: 'disabled', after: 'enabled' });
    expect(journal[1]).toMatchObject({ changeKind: 'power-plan', before: GUID, after: HIGH_PERF });

    // progress events covered the full lifecycle
    const phases = progress.map((p) => p.phase);
    expect(phases).toContain('applying');
    expect(phases.filter((x) => x === 'applied')).toHaveLength(4);

    // rollback restores exact prior values
    const rb = await rollbackProfile(profile.id, os, db, () => profile);
    expect(rb.ok).toBe(true);
    expect(rb.rolledBack).toHaveLength(4);
    const s2 = os.snapshot;
    expect(s2.gameModeEnabled).toBe(false);
    expect(s2.activePowerGuid).toBe(GUID);
    expect(s2.processPriorities['game.exe']).toBe('normal');
    expect(s2.fullscreenOptimizations['test-game']).toBe('enabled');
    expect(db.listUnrolledBack(profile.id)).toHaveLength(0);
    db.close();
  });

  it('skips unsupported changes without attempting them', async () => {
    const os = new MockOsLayer({ unsupportedCapabilities: new Set(['game-mode']) });
    const db = memDb();
    const profile = makeProfile([
      { kind: 'game-mode', params: { enabled: 'true' } },
      { kind: 'power-plan', params: { guid: HIGH_PERF } },
    ]);
    const result = await activateProfile(profile, os, { db });
    expect(result.ok).toBe(true);
    expect(result.applied).toHaveLength(1);
    expect(result.skipped).toHaveLength(1);
    expect(result.skipped[0]!.kind).toBe('game-mode');
    expect(result.skipped[0]!.reason).toMatch(/game-mode/);
    expect(os.snapshot.gameModeEnabled).toBe(false); // never attempted
    expect(os.snapshot.activePowerGuid).toBe(HIGH_PERF);
    expect(db.listJournal()).toHaveLength(1);
    db.close();
  });

  it('refuses to apply a power-plan change with an empty GUID', async () => {
    const os = new MockOsLayer();
    const db = memDb();
    const profile = makeProfile([
      { kind: 'game-mode', params: { enabled: 'true' } },
      { kind: 'power-plan', params: { guid: '' } },
    ]);
    const result = await activateProfile(profile, os, { db });
    expect(result.ok).toBe(true);
    expect(result.applied).toHaveLength(1); // game-mode applied
    expect(result.skipped).toHaveLength(1);
    expect(result.skipped[0]!.kind).toBe('power-plan');
    expect(os.snapshot.activePowerGuid).toBe(GUID); // unchanged
    db.close();
  });
});

describe('activateProfile — mid-apply failure', () => {
  it('automatically rolls back the partial activation in reverse order', async () => {
    const os = new MockOsLayer({ failOnApplyAt: 2 });
    const db = memDb();
    const profile = makeProfile([
      { kind: 'game-mode', params: { enabled: 'true' } },
      { kind: 'power-plan', params: { guid: HIGH_PERF } },
      { kind: 'process-priority', params: { imageName: 'game.exe', priority: 'high' } },
    ]);
    const result = await activateProfile(profile, os, { db });
    expect(result.ok).toBe(false);
    expect(result.error).toMatch(/Activation failed/);
    expect(result.error).toMatch(/Rolled back 1\/1/);
    expect(result.applied).toHaveLength(1);
    expect(result.rolledBack).toHaveLength(1);
    // mock state fully restored
    expect(os.snapshot.gameModeEnabled).toBe(false);
    expect(os.snapshot.activePowerGuid).toBe(GUID);
    // journal entry marked rolled back
    const journal = db.listJournal();
    expect(journal).toHaveLength(1);
    expect(journal[0]!.rolledBackAt).toBeDefined();
    expect(db.listUnrolledBack(profile.id)).toHaveLength(0);
    db.close();
  });

  it('reports when a rollback step itself fails', async () => {
    // Fail on the 2nd apply; then make restore fail by denying... instead:
    // use failOnApplyAt=1 so nothing was applied — rollback list is empty.
    const os = new MockOsLayer({ failOnApplyAt: 1 });
    const db = memDb();
    const profile = makeProfile([{ kind: 'game-mode', params: { enabled: 'true' } }]);
    const result = await activateProfile(profile, os, { db });
    expect(result.ok).toBe(false);
    expect(result.applied).toHaveLength(0);
    expect(result.rolledBack).toHaveLength(0);
    db.close();
  });
});

describe('restoreAll', () => {
  it('rolls back all un-rolled-back entries newest-first across profiles', async () => {
    const os = new MockOsLayer();
    const db = memDb();
    const a = makeProfile([{ kind: 'game-mode', params: { enabled: 'true' } }], 'A');
    a.id = 'a';
    const b = makeProfile([{ kind: 'power-plan', params: { guid: HIGH_PERF } }], 'B');
    b.id = 'b';
    await activateProfile(a, os, { db });
    await activateProfile(b, os, { db });
    expect(os.snapshot.gameModeEnabled).toBe(true);
    expect(os.snapshot.activePowerGuid).toBe(HIGH_PERF);

    const restoredKinds: string[] = [];
    const origRestore = os.restore.bind(os);
    os.restore = async (kind, params, value) => {
      restoredKinds.push(kind);
      return origRestore(kind, params, value);
    };

    const result = await restoreAll(os, db, (id) => (id === 'a' ? a : b));
    expect(result.ok).toBe(true);
    expect(result.rolledBack).toHaveLength(2);
    // newest-first: b's power-plan entry rolled back before a's game-mode entry
    expect(restoredKinds).toEqual(['power-plan', 'game-mode']);
    expect(os.snapshot.gameModeEnabled).toBe(false);
    expect(os.snapshot.activePowerGuid).toBe(GUID);
    db.close();
  });

  it('is a no-op when a failed activation already auto-rolled-back', async () => {
    const os = new MockOsLayer({ failOnApplyAt: 2 });
    const db = memDb();
    const profile = makeProfile([
      { kind: 'game-mode', params: { enabled: 'true' } },
      { kind: 'power-plan', params: { guid: HIGH_PERF } },
    ]);
    await activateProfile(profile, os, { db });
    const result = await restoreAll(os, db, () => profile);
    expect(result.ok).toBe(true);
    expect(result.rolledBack).toHaveLength(0);
    db.close();
  });
});

describe('restoreAll — dependent history after a restore failure', () => {
  it('skips older entries for a failed setting but still restores independent settings, and a retry recovers the original state', async () => {
    const os = new MockOsLayer(); // Game Mode initially disabled, power plan = Balanced GUID
    const db = memDb();
    const e = makeProfile([{ kind: 'power-plan', params: { guid: HIGH_PERF } }], 'E');
    e.id = 'e';
    const a = makeProfile([{ kind: 'game-mode', params: { enabled: 'true' } }], 'A');
    a.id = 'a';
    const b = makeProfile([{ kind: 'game-mode', params: { enabled: 'false' } }], 'B');
    b.id = 'b';
    const getProfile = (id: string) => (id === 'a' ? a : id === 'b' ? b : e);

    await activateProfile(e, os, { db }); // power plan: Balanced -> HIGH_PERF (oldest)
    await activateProfile(a, os, { db }); // game-mode: disabled -> enabled
    await activateProfile(b, os, { db }); // game-mode: enabled -> disabled (newest)
    expect(os.snapshot.gameModeEnabled).toBe(false);
    expect(os.snapshot.activePowerGuid).toBe(HIGH_PERF);

    // Fail only the newer game-mode restore (B: restore to 'enabled').
    let failNewerGameMode = true;
    const origRestore = os.restore.bind(os);
    os.restore = async (kind, params, value) => {
      if (failNewerGameMode && kind === 'game-mode' && value === 'enabled') {
        throw new Error('injected restore failure');
      }
      return origRestore(kind, params, value);
    };

    const first = await restoreAll(os, db, getProfile);
    expect(first.ok).toBe(false);
    expect(first.errors.join(' ')).toMatch(/injected restore failure/);
    // The older game-mode entry (A) must NOT be retired/restored while B is
    // still live — doing so would invalidate B's recorded baseline.
    const unrolled = db.listUnrolledBack();
    expect(unrolled.map((x) => x.profileId).sort()).toEqual(['a', 'b']);
    expect(first.rolledBack).toHaveLength(1); // only the independent power-plan entry
    // Independent setting was still restored despite the game-mode failure.
    expect(os.snapshot.activePowerGuid).toBe(GUID);
    expect(os.snapshot.gameModeEnabled).toBe(false);

    // Second restore-all (failure cleared) must recover the ORIGINAL state:
    // B restores to 'enabled', then A restores to 'disabled'.
    failNewerGameMode = false;
    const second = await restoreAll(os, db, getProfile);
    expect(second.ok).toBe(true);
    expect(second.rolledBack).toHaveLength(2);
    expect(os.snapshot.gameModeEnabled).toBe(false); // original disabled state, not 'enabled'
    expect(db.listUnrolledBack()).toHaveLength(0);
    db.close();
  });
});

describe('rollbackProfile — out-of-order rollback over a shared setting', () => {
  it('rebases the newer profile baseline so restore-all still recovers the original state', async () => {
    const os = new MockOsLayer(); // Game Mode initially disabled
    const db = memDb();
    const a = makeProfile([{ kind: 'game-mode', params: { enabled: 'true' } }], 'A');
    a.id = 'a';
    const b = makeProfile([{ kind: 'game-mode', params: { enabled: 'false' } }], 'B');
    b.id = 'b';
    const getProfile = (id: string) => (id === 'a' ? a : b);

    await activateProfile(a, os, { db }); // disabled -> enabled (A.before = disabled)
    await activateProfile(b, os, { db }); // enabled -> disabled (B.before = enabled)
    expect(os.snapshot.gameModeEnabled).toBe(false);

    // Rolling back the OLDER profile must not restore its `before` over the
    // newer profile's live state, and must rebase B's baseline to A's before.
    let restoreCalls = 0;
    const origRestore = os.restore.bind(os);
    os.restore = async (kind, params, value) => {
      restoreCalls += 1;
      return origRestore(kind, params, value);
    };
    const rb = await rollbackProfile('a', os, db, getProfile);
    expect(rb.ok).toBe(true);
    expect(rb.rolledBack).toHaveLength(1);
    expect(restoreCalls).toBe(0); // OS untouched: current state is B's, not A's
    expect(os.snapshot.gameModeEnabled).toBe(false);
    const bEntry = db.listJournal().find((e) => e.profileId === 'b')!;
    expect(bEntry.before).toBe('disabled'); // rebased from 'enabled'
    expect(bEntry.rolledBackAt).toBeUndefined();

    const all = await restoreAll(os, db, getProfile);
    expect(all.ok).toBe(true);
    expect(os.snapshot.gameModeEnabled).toBe(false); // original state recovered
    expect(db.listUnrolledBack()).toHaveLength(0);
    db.close();
  });

  it('in-order rollback of the newest profile still restores through the OS', async () => {
    const os = new MockOsLayer();
    const db = memDb();
    const a = makeProfile([{ kind: 'game-mode', params: { enabled: 'true' } }], 'A');
    a.id = 'a';
    const b = makeProfile([{ kind: 'game-mode', params: { enabled: 'false' } }], 'B');
    b.id = 'b';
    const getProfile = (id: string) => (id === 'a' ? a : b);
    await activateProfile(a, os, { db });
    await activateProfile(b, os, { db });
    const rb = await rollbackProfile('b', os, db, getProfile);
    expect(rb.ok).toBe(true);
    expect(os.snapshot.gameModeEnabled).toBe(true); // B.before, restored live
    const all = await restoreAll(os, db, getProfile);
    expect(all.ok).toBe(true);
    expect(os.snapshot.gameModeEnabled).toBe(false);
    db.close();
  });
});

describe('takeSnapshot', () => {
  it('records synthetic values with the exact approximate note', async () => {
    const os = new MockOsLayer({ initial: { cpuPercent: 33.3, memoryMb: 4096 } });
    const db = memDb();
    const snap = await takeSnapshot('before', os, db);
    expect(snap.label).toBe('before');
    expect(snap.cpuPercent).toBe(33.3);
    expect(snap.memoryMb).toBe(4096);
    expect(snap.note).toBe('approximate — point-in-time estimate, not a benchmark');
    expect(db.listSnapshots()).toHaveLength(1);
    db.close();
  });
});

describe('validateParams', () => {
  it('rejects malformed GUIDs, empty GUIDs, realtime priority, missing fields', () => {
    expect(validateParams('power-plan', { guid: 'not-a-guid' })).toMatch(/Malformed/);
    expect(validateParams('power-plan', { guid: '' })).toMatch(/No power-plan GUID/);
    expect(validateParams('power-plan', { guid: HIGH_PERF })).toBeUndefined();
    expect(validateParams('process-priority', { imageName: 'g.exe', priority: 'realtime' })).toMatch(/only above-normal/);
    expect(validateParams('process-priority', { imageName: '', priority: 'high' })).toMatch(/imageName/);
    expect(validateParams('process-priority', { imageName: 'g.exe', priority: 'high' })).toBeUndefined();
    expect(validateParams('process-priority', { imageName: 'explor*', priority: 'high' })).toMatch(/wildcard/i);
    expect(validateParams('process-priority', { imageName: 'explorer.exe', priority: 'high' })).toMatch(/system process/i);
    expect(validateParams('fullscreen-optimizations', { childKey: '' })).toMatch(/childKey/);
    expect(validateParams('game-mode', {})).toBeUndefined();
  });
});

describe('seedProfile', () => {
  it('seeds Balanced Gaming once, with an unset power-plan GUID', () => {
    const db = memDb();
    expect(seedProfile(db)).toBe(true);
    const profiles = db.listProfiles();
    expect(profiles).toHaveLength(1);
    expect(profiles[0]!.name).toBe(SEED_PROFILE_NAME);
    expect(profiles[0]!.changes).toHaveLength(2);
    expect(profiles[0]!.changes[1]).toEqual({ kind: 'power-plan', params: { guid: '' } });
    expect(seedProfile(db)).toBe(false);
    expect(db.listProfiles()).toHaveLength(1);
    db.close();
  });

  it('the seeded profile previews game-mode as supported and power-plan as pick-in-UI', async () => {
    const db = memDb();
    seedProfile(db);
    const os = new MockOsLayer();
    const profile = db.listProfiles()[0]!;
    const planned = await previewProfile(profile, os);
    expect(planned[0]!.supported).toBe(true);
    expect(planned[1]!.supported).toBe(false);
    expect(planned[1]!.unsupportedReason).toMatch(/pick a power plan/i);
    db.close();
  });
});
