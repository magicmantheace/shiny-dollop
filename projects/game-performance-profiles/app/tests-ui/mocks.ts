/**
 * Mock `window.gpp` bridge for hermetic UI tests.
 *
 * No test here touches real IPC: every test installs a fake bridge with
 * `installGppMock()` and asserts on the calls it received plus the rendered
 * output. `clearGppMock()` removes it so the missing-bridge path can be
 * tested too.
 */
import type {
  ActivationProgress,
  ActivationResult,
  Capability,
  ChangeKind,
  GppApi,
  JournalEntry,
  PlannedChange,
  Profile,
  ResourceSnapshot,
  RollbackResult,
  RestoreAllResult,
} from '../shared/gpp-types';

export const KINDS: ChangeKind[] = [
  'game-mode',
  'power-plan',
  'process-priority',
  'fullscreen-optimizations',
];

export function mockCapabilities(
  overrides: Partial<Record<ChangeKind, Partial<Capability>>> = {},
): Capability[] {
  return KINDS.map((kind) => ({
    id: kind,
    name: kind,
    description: `${kind} description`,
    supported: true,
    ...overrides[kind],
  }));
}

export function mockProfile(overrides: Partial<Profile> = {}): Profile {
  return {
    id: 'profile-1',
    name: 'Test Profile',
    changes: [
      { kind: 'game-mode', params: { enabled: 'true' } },
      { kind: 'power-plan', params: { guid: '381b4222-f694-41f0-9685-ff5bb260df2e' } },
    ],
    createdAt: '2026-10-23T10:00:00Z',
    updatedAt: '2026-10-23T10:00:00Z',
    ...overrides,
  };
}

export function mockPlanned(overrides: Partial<PlannedChange> = {}): PlannedChange {
  return {
    changeId: 'change-1',
    kind: 'game-mode',
    target: 'Windows Game Mode',
    from: 'off',
    to: 'on',
    reversible: true,
    supported: true,
    ...overrides,
  };
}

export function mockJournalEntry(overrides: Partial<JournalEntry> = {}): JournalEntry {
  return {
    id: 'journal-1',
    profileId: 'profile-1',
    profileName: 'Test Profile',
    changeKind: 'game-mode',
    target: 'Windows Game Mode',
    before: 'off',
    after: 'on',
    appliedAt: '2026-10-23T11:00:00Z',
    ...overrides,
  };
}

export function mockSnapshot(overrides: Partial<ResourceSnapshot> = {}): ResourceSnapshot {
  return {
    id: 'snap-1',
    label: 'before',
    takenAt: '2026-10-23T11:00:00Z',
    cpuPercent: 12.5,
    memoryMb: 4096,
    note: 'approximate — point-in-time estimate, not a benchmark',
    ...overrides,
  };
}

export function mockActivationResult(
  overrides: Partial<ActivationResult> = {},
): ActivationResult {
  return {
    ok: true,
    applied: ['journal-1'],
    rolledBack: [],
    skipped: [],
    ...overrides,
  };
}

export function mockRollbackResult(
  overrides: Partial<RollbackResult> = {},
): RollbackResult {
  return { ok: true, rolledBack: ['journal-1'], errors: [], ...overrides };
}

export function mockRestoreAllResult(
  overrides: Partial<RestoreAllResult> = {},
): RestoreAllResult {
  return { ok: true, rolledBack: ['journal-1', 'journal-2'], errors: [], ...overrides };
}

export interface MockGpp extends GppApi {
  calls: Record<string, unknown[][]>;
  progressListeners: Array<(p: ActivationProgress) => void>;
  emitProgress(p: ActivationProgress): void;
}

function record(calls: Record<string, unknown[][]>, name: string, args: unknown[]) {
  (calls[name] ??= []).push(args);
}

export function installGppMock(overrides: Partial<GppApi> = {}): MockGpp {
  const calls: Record<string, unknown[][]> = {};
  const progressListeners: Array<(p: ActivationProgress) => void> = [];

  const mock: MockGpp = {
    calls,
    progressListeners,
    emitProgress(p: ActivationProgress) {
      for (const cb of progressListeners) cb(p);
    },
    async getCapabilities() {
      record(calls, 'getCapabilities', []);
      return { capabilities: mockCapabilities() };
    },
    async listProfiles() {
      record(calls, 'listProfiles', []);
      return { profiles: [] };
    },
    async createProfile(input) {
      record(calls, 'createProfile', [input]);
      return { profile: mockProfile({ name: input.name, changes: input.changes }) };
    },
    async updateProfile(input) {
      record(calls, 'updateProfile', [input]);
      return {
        profile: mockProfile({
          id: input.id,
          ...(input.name ? { name: input.name } : {}),
          ...(input.changes ? { changes: input.changes } : {}),
        }),
      };
    },
    async deleteProfile(input) {
      record(calls, 'deleteProfile', [input]);
      return { ok: true as const };
    },
    async previewProfile(input) {
      record(calls, 'previewProfile', [input]);
      return { planned: [mockPlanned()] };
    },
    async activateProfile(input) {
      record(calls, 'activateProfile', [input]);
      return { result: mockActivationResult() };
    },
    async rollbackProfile(input) {
      record(calls, 'rollbackProfile', [input]);
      return { result: mockRollbackResult() };
    },
    async restoreAll() {
      record(calls, 'restoreAll', []);
      return { result: mockRestoreAllResult() };
    },
    async listJournal() {
      record(calls, 'listJournal', []);
      return { entries: [] };
    },
    async takeSnapshot(input) {
      record(calls, 'takeSnapshot', [input]);
      return { snapshot: mockSnapshot({ label: input.label }) };
    },
    async listSnapshots() {
      record(calls, 'listSnapshots', []);
      return { snapshots: [] };
    },
    onActivationProgress(cb) {
      record(calls, 'onActivationProgress', []);
      progressListeners.push(cb);
      return () => {
        const i = progressListeners.indexOf(cb);
        if (i >= 0) progressListeners.splice(i, 1);
      };
    },
  };

  // Overrides replace the defaults but are wrapped so calls are still
  // recorded — tests can assert on both the calls and custom responses.
  for (const [name, fn] of Object.entries(overrides)) {
    if (typeof fn === 'function') {
      (mock as unknown as Record<string, unknown>)[name] = (...args: unknown[]) => {
        record(calls, name, args);
        return (fn as (...a: unknown[]) => unknown)(...args);
      };
    }
  }

  (window as unknown as { gpp: GppApi }).gpp = mock;
  return mock;
}

export function clearGppMock(): void {
  delete (window as unknown as { gpp?: GppApi }).gpp;
}

export function callArgs(mock: MockGpp, name: string, n = 0): unknown[] {
  const list = mock.calls[name];
  if (!list || !list[n]) throw new Error(`No call recorded for ${name}[${n}]`);
  return list[n];
}

export function callCount(mock: MockGpp, name: string): number {
  return mock.calls[name]?.length ?? 0;
}
