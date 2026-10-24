/**
 * Scan persistence: scan rows, file records, error records, and the
 * result queries behind results.summary / results.duplicates / results.search.
 *
 * This module is deliberately free of 'electron' imports so backend tests
 * can exercise it against :memory: databases.
 */
import type { DatabaseSync } from 'node:sqlite';
import path from 'node:path';
import { normalizeForSearch } from './normalize';
import type {
  DirSizeEntry,
  DuplicateGroup,
  LargestFileEntry,
  ResultsSummary,
  ScanListEntry,
  ScanState,
  TypeSummaryEntry,
} from '../../../shared/types';

export interface ScanRow {
  id: number;
  root_path: string;
  state: ScanState;
  files: number;
  dirs: number;
  bytes: number;
  excluded_count: number;
  symlink_count: number;
  changed_count: number;
  error_count: number;
  started_at: string;
  finished_at: string | null;
  error: string | null;
}

export interface ScanCounters {
  files: number;
  dirs: number;
  bytes: number;
  excluded: number;
  symlinks: number;
  changed: number;
  errors: number;
}

export function createScan(db: DatabaseSync, rootPath: string): number {
  const result = db
    .prepare('INSERT INTO scans (root_path, state, started_at) VALUES (?, ?, ?)')
    .run(rootPath, 'running', new Date().toISOString());
  return Number(result.lastInsertRowid);
}

export function getScan(db: DatabaseSync, scanId: number): ScanRow | null {
  const row = db.prepare('SELECT * FROM scans WHERE id = ?').get(scanId) as ScanRow | undefined;
  return row ?? null;
}

export function listScans(db: DatabaseSync): ScanListEntry[] {
  const rows = db
    .prepare(
      'SELECT id, root_path, state, files, bytes, started_at, finished_at FROM scans ORDER BY id DESC',
    )
    .all() as Array<{
    id: number;
    root_path: string;
    state: ScanState;
    files: number;
    bytes: number;
    started_at: string;
    finished_at: string | null;
  }>;
  return rows.map((r) => ({
    id: r.id,
    rootPath: r.root_path,
    state: r.state,
    files: r.files,
    bytes: r.bytes,
    startedAt: r.started_at,
    finishedAt: r.finished_at,
  }));
}

export function updateScanCounters(db: DatabaseSync, scanId: number, c: ScanCounters): void {
  db.prepare(
    `UPDATE scans SET files = ?, dirs = ?, bytes = ?, excluded_count = ?,
       symlink_count = ?, changed_count = ?, error_count = ? WHERE id = ?`,
  ).run(c.files, c.dirs, c.bytes, c.excluded, c.symlinks, c.changed, c.errors, scanId);
}

export function finishScan(
  db: DatabaseSync,
  scanId: number,
  state: ScanState,
  c: ScanCounters,
  error: string | null,
): void {
  db.prepare(
    `UPDATE scans SET state = ?, files = ?, dirs = ?, bytes = ?, excluded_count = ?,
       symlink_count = ?, changed_count = ?, error_count = ?,
       finished_at = ?, error = ? WHERE id = ?`,
  ).run(
    state,
    c.files,
    c.dirs,
    c.bytes,
    c.excluded,
    c.symlinks,
    c.changed,
    c.errors,
    new Date().toISOString(),
    error,
    scanId,
  );
}

/**
 * Reconcile scans left in 'running' state by a previous process that exited
 * (or was killed) before the scan reached a terminal state — e.g. quit during
 * a scan whose asynchronous cancellation cleanup never got to persist.
 * Such scans can never resume, so they are closed out as 'failed' with an
 * explanatory error instead of being presented as running forever.
 * Returns the number of scans reconciled.
 */
export function markRunningScansInterrupted(db: DatabaseSync): number {
  const result = db
    .prepare(
      `UPDATE scans SET state = 'failed', error = ?, finished_at = ?
       WHERE state = 'running'`,
    )
    .run(
      'Interrupted: the application closed while this scan was running.',
      new Date().toISOString(),
    );
  return Number(result.changes);
}

/** Filesystem identity of a recorded file, from `fs.stat` (dev + inode). */
export interface FileIdentity {
  dev: number;
  ino: number;
}

/**
 * Identity key for duplicate accounting. Two paths with the same
 * (dev, ino) are hard links to ONE underlying file: deleting one link
 * reclaims nothing, so only the first path per identity may count toward
 * a duplicate group / its savings. A missing identity, or ino 0 (some
 * platforms report no usable inode), is treated as distinct per row.
 */
function identityKey(dev: number | null, ino: number | null, rowId: number): string {
  return dev !== null && ino !== null && ino !== 0 ? `${dev}:${ino}` : `row:${rowId}`;
}

export function recordFile(
  db: DatabaseSync,
  scanId: number,
  filePath: string,
  sizeBytes: number,
  isSymlink: boolean,
  identity?: FileIdentity | null,
): number {
  const dev = identity && identity.ino !== 0 ? identity.dev : null;
  const ino = identity && identity.ino !== 0 ? identity.ino : null;
  const result = db
    .prepare(
      'INSERT OR IGNORE INTO files (scan_id, path, size_bytes, is_symlink, dev, ino, path_search) VALUES (?, ?, ?, ?, ?, ?, ?)',
    )
    .run(scanId, filePath, sizeBytes, isSymlink ? 1 : 0, dev, ino, normalizeForSearch(filePath));
  if (result.changes === 0) {
    const existing = db
      .prepare('SELECT id FROM files WHERE scan_id = ? AND path = ?')
      .get(scanId, filePath) as { id: number };
    db.prepare(
      'UPDATE files SET dev = COALESCE(dev, ?), ino = COALESCE(ino, ?), path_search = ? WHERE id = ?',
    ).run(dev, ino, normalizeForSearch(filePath), existing.id);
    return existing.id;
  }
  return Number(result.lastInsertRowid);
}

export function recordScanError(db: DatabaseSync, scanId: number, errorPath: string, code: string): void {
  db.prepare('INSERT INTO scan_errors (scan_id, path, code) VALUES (?, ?, ?)').run(
    scanId,
    errorPath,
    code,
  );
}

export function listScanErrors(
  db: DatabaseSync,
  scanId: number,
): Array<{ path: string; code: string }> {
  return db
    .prepare('SELECT path, code FROM scan_errors WHERE scan_id = ? ORDER BY id')
    .all(scanId) as Array<{ path: string; code: string }>;
}

export function updateFileHash(db: DatabaseSync, fileId: number, sha256: string): void {
  db.prepare('UPDATE files SET sha256 = ? WHERE id = ?').run(sha256, fileId);
}

export function deleteFile(db: DatabaseSync, fileId: number): void {
  db.prepare('DELETE FROM files WHERE id = ?').run(fileId);
}

const LARGEST_FILES_LIMIT = 100;
const DIR_SIZES_LIMIT = 100;
export const SEARCH_RESULT_LIMIT = 500;

function extensionOf(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  return ext; // "" when the file has no extension
}

export function getSummary(db: DatabaseSync, scanId: number): ResultsSummary {
  const scan = getScan(db, scanId);
  const totalFiles = scan?.files ?? 0;
  const totalBytes = scan?.bytes ?? 0;

  const largestRows = db
    .prepare(
      'SELECT path, size_bytes FROM files WHERE scan_id = ? AND is_symlink = 0 ORDER BY size_bytes DESC, path ASC LIMIT ?',
    )
    .all(scanId, LARGEST_FILES_LIMIT) as Array<{ path: string; size_bytes: number }>;
  const largest: LargestFileEntry[] = largestRows.map((r) => ({ path: r.path, size: r.size_bytes }));

  const rows = db
    .prepare('SELECT path, size_bytes FROM files WHERE scan_id = ? AND is_symlink = 0')
    .all(scanId) as Array<{ path: string; size_bytes: number }>;

  const dirAgg = new Map<string, { bytes: number; files: number }>();
  const typeAgg = new Map<string, { files: number; bytes: number }>();
  for (const row of rows) {
    const dir = path.dirname(row.path);
    const d = dirAgg.get(dir) ?? { bytes: 0, files: 0 };
    d.bytes += row.size_bytes;
    d.files += 1;
    dirAgg.set(dir, d);

    const ext = extensionOf(row.path);
    const t = typeAgg.get(ext) ?? { files: 0, bytes: 0 };
    t.files += 1;
    t.bytes += row.size_bytes;
    typeAgg.set(ext, t);
  }

  const dirSizes: DirSizeEntry[] = [...dirAgg.entries()]
    .map(([dirPath, agg]) => ({ path: dirPath, bytes: agg.bytes, files: agg.files }))
    .sort((a, b) => b.bytes - a.bytes || a.path.localeCompare(b.path))
    .slice(0, DIR_SIZES_LIMIT);

  const typeSummary: TypeSummaryEntry[] = [...typeAgg.entries()]
    .map(([ext, agg]) => ({ ext, files: agg.files, bytes: agg.bytes }))
    .sort((a, b) => b.bytes - a.bytes || a.ext.localeCompare(b.ext));

  return { totalFiles, totalBytes, largestFiles: largest, dirSizes, typeSummary };
}

/**
 * Only hash-confirmed groups: ≥2 DISTINCT files sharing an identical
 * SHA-256. Files that changed mid-scan are deleted before hashing, so
 * they can never appear here. Hard-link aliases are collapsed by
 * (dev, ino) identity before counting: two paths to the same inode are
 * one file, and a group needs at least two distinct inodes before any
 * savings (size × (distinct files − 1)) can be advertised.
 */
export function getDuplicateGroups(db: DatabaseSync, scanId: number): DuplicateGroup[] {
  const rows = db
    .prepare(
      `SELECT id, path, size_bytes AS sizeBytes, sha256, dev, ino FROM files
       WHERE scan_id = ? AND sha256 IS NOT NULL AND is_symlink = 0
       ORDER BY sizeBytes DESC, sha256 ASC, path ASC`,
    )
    .all(scanId) as Array<{
    id: number;
    path: string;
    sizeBytes: number;
    sha256: string;
    dev: number | null;
    ino: number | null;
  }>;

  const groups = new Map<string, { sizeBytes: number; sha256: string; files: string[]; seen: Set<string> }>();
  for (const row of rows) {
    let group = groups.get(row.sha256);
    if (!group) {
      group = { sizeBytes: row.sizeBytes, sha256: row.sha256, files: [], seen: new Set() };
      groups.set(row.sha256, group);
    }
    const key = identityKey(row.dev, row.ino, row.id);
    if (group.seen.has(key)) continue; // hard-link alias of a file already counted
    group.seen.add(key);
    group.files.push(row.path);
  }
  return [...groups.values()]
    .filter((g) => g.files.length >= 2)
    .map((g) => ({ sizeBytes: g.sizeBytes, sha256: g.sha256, files: g.files }));
}

function escapeLike(raw: string): string {
  return raw.replace(/\\/g, '\\\\').replace(/%/g, '\\%').replace(/_/g, '\\_');
}

/**
 * Case-insensitive substring search over recorded paths, capped.
 * Both sides go through the same Unicode-aware normalization: the query
 * here, and the stored `path_search` key at record/migration time.
 * (SQLite's lower() folds ASCII only and would miss non-ASCII names.)
 */
export function searchFiles(db: DatabaseSync, scanId: number, query: string): Array<{ path: string; size: number }> {
  const pattern = `%${escapeLike(normalizeForSearch(query))}%`;
  return db
    .prepare(
      `SELECT path, size_bytes AS size FROM files
       WHERE scan_id = ? AND is_symlink = 0 AND path_search LIKE ? ESCAPE '\\'
       ORDER BY path ASC LIMIT ?`,
    )
    .all(scanId, pattern, SEARCH_RESULT_LIMIT) as Array<{ path: string; size: number }>;
}
