/**
 * Domain types shared by main, preload and renderer.
 * All timestamps are ISO-8601 UTC strings. All sizes are bytes.
 */

/** Where a tracked game entry came from. */
export type GameSource = 'manual' | 'steam' | 'epic' | 'battlenet' | 'discovered';

export interface Game {
  id: number;
  name: string;
  /** Absolute path of the folder whose contents get backed up. */
  savePath: string;
  source: GameSource;
  createdAt: string;
}

/** How much we trust a discovered save-folder candidate. */
export type EvidenceLabel = 'verified-path' | 'pattern-match' | 'manual';

export interface SaveCandidate {
  /** Game title as reported by the store client that owns it. */
  gameName: string;
  source: Exclude<GameSource, 'manual'>;
  /** Absolute candidate save folder. */
  savePath: string;
  evidence: EvidenceLabel;
  /** Human-readable explanation of why this path is a candidate. */
  detail: string;
}

export interface Backup {
  id: number;
  gameId: number;
  createdAt: string;
  label: string | null;
  fileCount: number;
  totalBytes: number;
  /** Absolute backup directory on disk. */
  backupDir: string;
  notes: string | null;
}

export interface BackupFileEntry {
  /** Forward-slash relative path inside the save folder (portable). */
  relPath: string;
  sha256: string;
  sizeBytes: number;
}

export interface BackupDetail extends Backup {
  files: BackupFileEntry[];
}

export interface SkippedFile {
  relPath: string;
  reason: string;
}

export interface CreateBackupResult {
  skipped: boolean;
  /** Present when skipped === true. */
  reason?: string;
  /** The backup that was created, or the unchanged latest backup when skipped. */
  backup: Backup;
  skippedFiles: SkippedFile[];
  /** Warnings, e.g. cloud-sync conflict copies that were backed up as-is. */
  notes: string[];
}

export interface CorruptFile {
  relPath: string;
  issue: 'missing' | 'checksum-mismatch' | 'size-mismatch';
  expected?: string;
  actual?: string;
}

export interface VerifyBackupResult {
  backupId: number;
  ok: boolean;
  checkedFiles: number;
  corrupt: CorruptFile[];
}

export interface RestoreBackupResult {
  backupId: number;
  /** The automatic pre-restore safety backup that was taken first. */
  safetyBackupId: number;
  restoredFiles: number;
  /** Post-restore checksum mismatches (empty on a clean restore). */
  mismatches: CorruptFile[];
}

export interface Schedule {
  id: number;
  gameId: number;
  intervalMinutes: number;
  enabled: boolean;
  lastRunAt: string | null;
}

/** Progress events streamed while a backup runs. */
export interface BackupProgressEvent {
  gameId: number;
  backupId?: number;
  phase: 'hash' | 'copy';
  done: number;
  total: number;
  currentFile?: string;
}

export interface BackupCompletedEvent {
  gameId: number;
  backupId: number;
  label: string | null;
  fileCount: number;
  totalBytes: number;
  skipped: boolean;
}

export interface BackupFailedEvent {
  gameId: number;
  code: string;
  message: string;
}

/** Uniform IPC envelope: every handler returns one of these. */
export type IpcResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string } };

/** The typed API exposed to the renderer as `window.saveManager`. */
export interface SaveManagerApi {
  games: {
    list: () => Promise<IpcResult<Game[]>>;
    add: (input: { name: string; savePath: string; source?: GameSource }) => Promise<IpcResult<Game>>;
    update: (input: { id: number; name?: string; savePath?: string }) => Promise<IpcResult<Game>>;
    remove: (input: { id: number }) => Promise<IpcResult<{ removed: boolean }>>;
    discoverCandidates: () => Promise<IpcResult<SaveCandidate[]>>;
    /** Opens a native folder picker; resolves to the chosen path or null. */
    chooseFolder: () => Promise<IpcResult<{ path: string | null }>>;
  };
  backups: {
    create: (input: { gameId: number; label?: string }) => Promise<IpcResult<CreateBackupResult>>;
    list: (input: { gameId: number }) => Promise<IpcResult<Backup[]>>;
    get: (input: { backupId: number }) => Promise<IpcResult<BackupDetail>>;
    verify: (input: { backupId: number }) => Promise<IpcResult<VerifyBackupResult>>;
    restore: (input: { backupId: number; confirmed: true }) => Promise<IpcResult<RestoreBackupResult>>;
  };
  schedules: {
    list: () => Promise<IpcResult<Schedule[]>>;
    set: (input: { gameId: number; intervalMinutes: number; enabled?: boolean }) => Promise<IpcResult<Schedule>>;
    delete: (input: { gameId: number }) => Promise<IpcResult<{ removed: boolean }>>;
  };
  events: {
    onBackupProgress: (listener: (e: BackupProgressEvent) => void) => () => void;
    onBackupCompleted: (listener: (e: BackupCompletedEvent) => void) => () => void;
    onBackupFailed: (listener: (e: BackupFailedEvent) => void) => () => void;
  };
}
