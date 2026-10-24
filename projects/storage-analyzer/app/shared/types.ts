/**
 * Canonical data types for the storage-analyzer IPC contract.
 * This file (plus ipc-channels.ts, schemas.ts, api-types.ts) is the source
 * of truth for the renderer: mirror field names exactly.
 *
 * NOTE on scanId: scans are identified by their numeric SQLite row id
 * (`scans.id`), returned by `scan.start`. It is stable across app restarts.
 */

export type ScanState = 'running' | 'cancelled' | 'complete' | 'failed';

export interface IpcErrorBody {
  code: string;
  message: string;
}

/** Uniform envelope for every invoke() response. */
export type IpcResult<T> = { ok: true; data: T } | { ok: false; error: IpcErrorBody };

/** Warning returned by scan.start for sensitive roots (scan still runs). */
export type ScanStartWarning = 'protected-path';

export interface ScanStartInput {
  rootPath: string;
  exclusions: string[];
}

export interface ScanStartResult {
  scanId: number;
  warning?: ScanStartWarning;
}

export interface ScanIdInput {
  scanId: number;
}

export interface ScanCancelResult {
  ok: true;
}

export interface ScanStatus {
  state: ScanState;
  files: number;
  dirs: number;
  bytes: number;
  error?: string;
  startedAt: string;
  finishedAt: string | null;
  /** Extra: permission-denied / loop / unreadable entries recorded, scan kept going. */
  errors: number;
  /** Extra: files that changed between size-read and hash (skipped, never hashed). */
  changedFiles: number;
}

export interface ScanListEntry {
  id: number;
  rootPath: string;
  state: ScanState;
  files: number;
  bytes: number;
  startedAt: string;
  finishedAt: string | null;
}

export interface ScanListResult {
  scans: ScanListEntry[];
}

export interface LargestFileEntry {
  path: string;
  size: number;
}

export interface DirSizeEntry {
  path: string;
  bytes: number;
  files: number;
}

export interface TypeSummaryEntry {
  /** Lower-cased extension WITH leading dot (e.g. ".iso"); "" when the file has none. */
  ext: string;
  files: number;
  bytes: number;
}

export interface ResultsSummary {
  totalFiles: number;
  totalBytes: number;
  largestFiles: LargestFileEntry[];
  dirSizes: DirSizeEntry[];
  typeSummary: TypeSummaryEntry[];
}

export interface DuplicateGroup {
  sizeBytes: number;
  sha256: string;
  files: string[];
}

export interface DuplicateGroupsResult {
  groups: DuplicateGroup[];
}

export interface SearchInput {
  scanId: number;
  query: string;
}

export interface SearchHit {
  path: string;
  size: number;
}

export interface SearchResults {
  files: SearchHit[];
}

export interface ExportReportInput {
  scanId: number;
  format: 'csv' | 'json';
  outPath: string;
}

export interface ExportReportResult {
  outPath: string;
}

export interface ScanProgressEvent {
  scanId: number;
  files: number;
  dirs: number;
  bytes: number;
  currentPath: string;
}

export interface ScanFinishedEvent {
  scanId: number;
  state: ScanState;
}

/** Unsubscribe function returned by event subscription methods. */
export type Unsubscribe = () => void;
