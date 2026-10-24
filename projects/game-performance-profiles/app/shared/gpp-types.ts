/**
 * Shared type contract for Windows Game Performance Profiles.
 *
 * Imported by the Electron main process, the preload script, the renderer,
 * and the test suite. Worker B: build the renderer against these types —
 * they are the stable IPC contract and will not be renamed.
 */

/** The four OS change kinds this app can apply. Never extended without a spec update. */
export type ChangeKind =
  | 'game-mode'
  | 'power-plan'
  | 'process-priority'
  | 'fullscreen-optimizations';

export const CHANGE_KINDS: readonly ChangeKind[] = [
  'game-mode',
  'power-plan',
  'process-priority',
  'fullscreen-optimizations',
] as const;

/** One desired change inside a profile. */
export interface ChangeSpec {
  kind: ChangeKind;
  /** String-keyed parameters; validated per kind before any OS touch. */
  params: Record<string, string>;
}

/** A named, persisted set of performance changes. */
export interface Profile {
  id: string;
  name: string;
  changes: ChangeSpec[];
  createdAt: string;
  updatedAt: string;
}

/** One row of a profile preview: current value vs desired value. */
export interface PlannedChange {
  changeId: string;
  kind: ChangeKind;
  /** Human-readable target, e.g. process image name or registry description. */
  target: string;
  /** Current value as read from the OS layer (opaque string). */
  from: string;
  /** Desired value derived from params (opaque string). */
  to: string;
  reversible: boolean;
  supported: boolean;
  unsupportedReason?: string;
}

/** One OS capability, as reported by startup probing. */
export interface Capability {
  id: string;
  name: string;
  description: string;
  supported: boolean;
  reason?: string;
}

/** One applied OS change, recorded before it was made so rollback is exact. */
export interface JournalEntry {
  id: string;
  profileId: string;
  profileName: string;
  changeKind: ChangeKind;
  target: string;
  before: string;
  after: string;
  appliedAt: string;
  /** ISO timestamp once rolled back; undefined while the change is still live. */
  rolledBackAt?: string | undefined;
}

/** Point-in-time resource observation. Not a benchmark. */
export interface ResourceSnapshot {
  id: string;
  label: string;
  takenAt: string;
  cpuPercent: number;
  memoryMb: number;
  note: string;
}

/** Exact note carried by every snapshot. */
export const SNAPSHOT_NOTE = 'approximate — point-in-time estimate, not a benchmark';

/** Progress events emitted on `gpp:activation-progress` during activation. */
export interface ActivationProgress {
  changeId: string;
  kind: ChangeKind;
  target: string;
  index: number;
  total: number;
  phase: 'applying' | 'applied' | 'rolling-back' | 'rolled-back' | 'failed';
}

/** A change the engine declined to attempt during activation. */
export interface SkippedChange {
  changeId: string;
  kind: ChangeKind;
  target: string;
  reason: string;
}

export interface ActivationResult {
  ok: boolean;
  /** Journal entry ids applied in this activation (in apply order). */
  applied: string[];
  /** Journal entry ids rolled back during automatic failure rollback. */
  rolledBack: string[];
  /** Changes skipped because they were unsupported or invalid. Never attempted. */
  skipped: SkippedChange[];
  error?: string;
}

export interface RollbackResult {
  ok: boolean;
  /** Journal entry ids rolled back, newest-first. */
  rolledBack: string[];
  errors: string[];
}

export interface RestoreAllResult {
  ok: boolean;
  rolledBack: string[];
  errors: string[];
}

// ---------------------------------------------------------------------------
// IPC request / response shapes (one per channel)
// ---------------------------------------------------------------------------

export interface CapabilitiesResponse {
  capabilities: Capability[];
}
export interface ProfilesListResponse {
  profiles: Profile[];
}
export interface ProfileResponse {
  profile: Profile;
}
export interface PreviewResponse {
  planned: PlannedChange[];
}
export interface ActivateResponse {
  result: ActivationResult;
}
export interface RollbackResponse {
  result: RollbackResult;
}
export interface RestoreAllResponse {
  result: RestoreAllResult;
}
export interface JournalListResponse {
  entries: JournalEntry[];
}
export interface SnapshotResponse {
  snapshot: ResourceSnapshot;
}
export interface SnapshotsListResponse {
  snapshots: ResourceSnapshot[];
}
export interface OkResponse {
  ok: true;
}
export interface ErrorResponse {
  error: string;
}

export interface CreateProfileInput {
  name: string;
  changes: ChangeSpec[];
}
export interface UpdateProfileInput {
  id: string;
  name?: string;
  changes?: ChangeSpec[];
}
export interface DeleteProfileInput {
  id: string;
}
export interface PreviewProfileInput {
  profileId: string;
}
export interface ActivateProfileInput {
  profileId: string;
  /** Must be exactly true; the renderer sets this from an explicit user confirmation. */
  approved: boolean;
}
export interface RollbackProfileInput {
  profileId: string;
}
export interface TakeSnapshotInput {
  label: string;
}

/**
 * Typed renderer API exposed by the preload script as `window.gpp`.
 * Channel names are fixed; Worker B must not rename them here.
 */
export interface GppApi {
  getCapabilities(): Promise<CapabilitiesResponse>;
  listProfiles(): Promise<ProfilesListResponse>;
  createProfile(input: CreateProfileInput): Promise<ProfileResponse | ErrorResponse>;
  updateProfile(input: UpdateProfileInput): Promise<ProfileResponse | ErrorResponse>;
  deleteProfile(input: DeleteProfileInput): Promise<OkResponse | ErrorResponse>;
  previewProfile(input: PreviewProfileInput): Promise<PreviewResponse | ErrorResponse>;
  activateProfile(input: ActivateProfileInput): Promise<ActivateResponse | ErrorResponse>;
  rollbackProfile(input: RollbackProfileInput): Promise<RollbackResponse | ErrorResponse>;
  restoreAll(): Promise<RestoreAllResponse>;
  listJournal(): Promise<JournalListResponse>;
  takeSnapshot(input: TakeSnapshotInput): Promise<SnapshotResponse | ErrorResponse>;
  listSnapshots(): Promise<SnapshotsListResponse>;
  /** Subscribe to `gpp:activation-progress`; returns an unsubscribe function. */
  onActivationProgress(cb: (p: ActivationProgress) => void): () => void;
}

/** The twelve invoke channels. Do not rename — Worker B builds against these. */
export const IPC_CHANNELS = {
  capabilities: 'gpp:capabilities',
  profilesList: 'gpp:profiles:list',
  profilesCreate: 'gpp:profiles:create',
  profilesUpdate: 'gpp:profiles:update',
  profilesDelete: 'gpp:profiles:delete',
  profilesPreview: 'gpp:profiles:preview',
  profilesActivate: 'gpp:profiles:activate',
  profilesRollback: 'gpp:profiles:rollback',
  restoreAll: 'gpp:profiles:restoreAll',
  journalList: 'gpp:journal:list',
  snapshotsTake: 'gpp:snapshots:take',
  snapshotsList: 'gpp:snapshots:list',
} as const;

export const ACTIVATION_PROGRESS_EVENT = 'gpp:activation-progress';
