/**
 * Read-only filesystem scan engine.
 *
 * - Async directory walk that never blocks the Electron main thread
 *   (yields via setImmediate between entries).
 * - Cancellable via AbortController; cancellation is checked per entry.
 * - NEVER follows symlinks/junctions: they are recorded as skipped entries.
 *   Visited (dev, ino) pairs plus resolved realpaths break hardlink/bind-mount
 *   directory loops.
 * - Permission-denied (and other per-entry) errors are recorded in
 *   scan_errors; the walk keeps going and never throws for them.
 * - Read-only by construction: only readdir / lstat-style stat /
 *   read-stream operations are used. Nothing is written, chmod'ed or deleted
 *   in the scanned tree.
 * - Duplicate detection is size-first, then SHA-256 stream-hash confirmed.
 *   A file whose size changed between the walk and the hash is skipped and
 *   counted as changedDuringScan — it can never form a false duplicate group.
 *   Candidates are also revalidated AFTER hashing (identity, size, mtime,
 *   ctime compared against the pre-read stat): a file changed during its own
 *   read stream is excluded the same way, never stored as a verified digest.
 * - Hard-link aliases are not duplicates: candidates retain their (dev, ino)
 *   identity, and a second path to an inode that is already a candidate in
 *   the same size group is never hashed or grouped — deleting one link to a
 *   file reclaims 0 bytes, so it must not inflate duplicate savings. The
 *   persistence layer collapses aliases by identity a second time when
 *   constructing groups.
 *
 * This module has no 'electron' imports: progress is reported through a
 * callback so backend tests can run it headless.
 */
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import type { Dirent, Stats } from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import type { DatabaseSync } from 'node:sqlite';
import {
  deleteFile,
  recordFile,
  updateScanCounters,
  finishScan,
  type ScanCounters,
} from '../db/scans';

export type ScanEndState = 'complete' | 'cancelled' | 'failed';

export interface ScanProgressData {
  files: number;
  dirs: number;
  bytes: number;
  currentPath: string;
}

export interface ScanTestHooks {
  /** Called for every directory entry, before processing. Test-only seam. */
  beforeEntry?: (fullPath: string) => void | Promise<void>;
  /** Called after the walk phase, before the hash phase. Test-only seam. */
  beforeHashPhase?: () => void | Promise<void>;
  /**
   * Called right after a candidate's bytes have been fully read for hashing,
   * before the post-read revalidation. Test-only seam for simulating a file
   * that changes while (or just after) it is being hashed.
   */
  afterHashRead?: (fullPath: string) => void | Promise<void>;
}

export interface StartScanJobOptions {
  scanId: number;
  rootPath: string;
  exclusions: string[];
  emitProgress: (data: ScanProgressData) => void;
  hooks?: ScanTestHooks;
}

export interface ScanJobResult {
  state: ScanEndState;
  files: number;
  dirs: number;
  bytes: number;
  excluded: number;
  symlinks: number;
  changed: number;
  errors: number;
  error?: string;
}

export interface ScanJob {
  promise: Promise<ScanJobResult>;
  cancel: () => void;
}

/** Progress events are throttled to ~4/sec. */
const PROGRESS_THROTTLE_MS = 250;

class ScanAborted extends Error {
  constructor() {
    super('Scan cancelled');
    this.name = 'ScanAborted';
  }
}

interface CandidateFile {
  id: number;
  path: string;
  dev: number;
  ino: number;
}

/**
 * Add a file to its size group, unless the group already holds a path to
 * the same underlying file (same dev + inode = a hard-link alias; ino 0
 * means the platform reported no usable inode, so never collapse on it).
 */
function addCandidate(ctx: WalkContext, size: number, candidate: CandidateFile): void {
  const group = ctx.sizeGroups.get(size) ?? [];
  if (
    candidate.ino !== 0 &&
    group.some((c) => c.dev === candidate.dev && c.ino === candidate.ino)
  ) {
    return;
  }
  group.push(candidate);
  ctx.sizeGroups.set(size, group);
}

interface WalkContext {
  counters: ScanCounters;
  sizeGroups: Map<number, CandidateFile[]>;
  lastEmit: number;
  recordErrorStmt: ReturnType<DatabaseSync['prepare']>;
}

function errnoCode(err: unknown): string {
  return (err as NodeJS.ErrnoException)?.code ?? 'UNKNOWN';
}

function yieldTick(): Promise<void> {
  return new Promise<void>((resolve) => setImmediate(resolve));
}

/** Relative path with forward slashes, lower-cased — for exclusion matching. */
export function normalizeRel(root: string, fullPath: string): string {
  return path.relative(root, fullPath).split(path.sep).join('/').toLowerCase();
}

function globToRegExp(glob: string): RegExp {
  let out = '';
  for (const ch of glob) {
    if (ch === '*') out += '.*';
    else if (ch === '?') out += '.';
    else out += ch.replace(/[.+^${}()|[\]\\]/, '\\$&');
  }
  return new RegExp(`^${out}$`);
}

/**
 * Exclusion matching against the relative path. A pattern without glob
 * characters is a case-insensitive substring; with `*`/`?` it is a glob
 * matched against the full relative path and against every trailing
 * segment suffix (so `*.log` matches `a/b/c.log`).
 */
export function isExcluded(relPath: string, patterns: string[]): boolean {
  for (const raw of patterns) {
    const pattern = raw.trim().toLowerCase().replace(/\\/g, '/');
    if (!pattern) continue;
    if (/[*?]/.test(pattern)) {
      const re = globToRegExp(pattern);
      if (re.test(relPath)) return true;
      const segments = relPath.split('/');
      for (let i = 1; i < segments.length; i++) {
        if (re.test(segments.slice(i).join('/'))) return true;
      }
    } else if (relPath.includes(pattern)) {
      return true;
    }
  }
  return false;
}

/**
 * Warn when the scan root is a Windows system location (drive root,
 * C:\Windows, Program Files, …). Returns the warning token or null.
 * Only meaningful on win32; always null elsewhere.
 */
export function detectProtectedPath(
  rootPath: string,
  platform: NodeJS.Platform = process.platform,
): 'protected-path' | null {
  if (platform !== 'win32') return null;
  const norm = rootPath.replace(/\//g, '\\').replace(/\\+$/, '').toLowerCase();
  if (/^[a-z]:$/.test(norm)) return 'protected-path';
  const driveMatch = /^([a-z]:)(\\.*)?$/.exec(norm);
  if (!driveMatch) return null;
  const rest = driveMatch[2] ?? '\\';
  const suffixes = [
    '\\windows',
    '\\program files',
    '\\program files (x86)',
    '\\programdata',
    '\\system volume information',
    '\\$recycle.bin',
    '\\recovery',
    '\\efi',
    '\\boot',
  ];
  for (const suffix of suffixes) {
    if (rest === suffix || rest.startsWith(`${suffix}\\`)) return 'protected-path';
  }
  return null;
}

async function sha256File(filePath: string, signal: AbortSignal): Promise<string> {
  const hash = createHash('sha256');
  const stream = fs.createReadStream(filePath);
  try {
    for await (const chunk of stream) {
      if (signal.aborted) throw new ScanAborted();
      hash.update(chunk as Buffer);
    }
  } finally {
    stream.destroy();
  }
  return hash.digest('hex');
}

export function startScanJob(db: DatabaseSync, options: StartScanJobOptions): ScanJob {
  const controller = new AbortController();
  const promise = runScanJob(db, options, controller.signal);
  return { promise, cancel: () => controller.abort() };
}

async function runScanJob(
  db: DatabaseSync,
  options: StartScanJobOptions,
  signal: AbortSignal,
): Promise<ScanJobResult> {
  const { scanId } = options;
  const root = path.resolve(options.rootPath);
  const counters: ScanCounters = {
    files: 0,
    dirs: 0,
    bytes: 0,
    excluded: 0,
    symlinks: 0,
    changed: 0,
    errors: 0,
  };
  const ctx: WalkContext = {
    counters,
    sizeGroups: new Map(),
    lastEmit: 0,
    recordErrorStmt: db.prepare('INSERT INTO scan_errors (scan_id, path, code) VALUES (?, ?, ?)'),
  };

  const persistCounters = (): void => {
    updateScanCounters(db, scanId, counters);
  };

  const emit = (currentPath: string, force = false): void => {
    const now = Date.now();
    if (!force && now - ctx.lastEmit < PROGRESS_THROTTLE_MS) return;
    ctx.lastEmit = now;
    persistCounters();
    options.emitProgress({ files: counters.files, dirs: counters.dirs, bytes: counters.bytes, currentPath });
  };

  const checkAborted = (): void => {
    if (signal.aborted) throw new ScanAborted();
  };

  const recordError = (errorPath: string, code: string): void => {
    ctx.recordErrorStmt.run(scanId, errorPath, code);
    counters.errors += 1;
  };

  try {
    db.exec('BEGIN');
    try {
      await walkDirectory(db, ctx, options, signal, root, checkAborted, recordError, emit);
    } finally {
      // Keep partial results on cancel/failure: never roll back the walk.
      db.exec('COMMIT');
    }

    if (options.hooks?.beforeHashPhase) {
      await options.hooks.beforeHashPhase();
    }
    checkAborted();

    await hashCandidates(db, ctx, options, signal, checkAborted, recordError, emit);

    emit(root, true);
    finishScan(db, scanId, 'complete', counters, null);
    return { state: 'complete', ...snapshot(counters) };
  } catch (err) {
    if (err instanceof ScanAborted || signal.aborted) {
      try {
        persistCounters();
      } catch {
        // Never fail cancellation on teardown.
      }
      finishScan(db, scanId, 'cancelled', counters, null);
      emit(root, true);
      return { state: 'cancelled', ...snapshot(counters) };
    }
    const message = err instanceof Error ? err.message : String(err);
    try {
      finishScan(db, scanId, 'failed', counters, message);
    } catch {
      // Never mask the original failure.
    }
    return { state: 'failed', error: message, ...snapshot(counters) };
  }
}

function snapshot(c: ScanCounters): ScanCounters {
  return { ...c };
}

async function walkDirectory(
  db: DatabaseSync,
  ctx: WalkContext,
  options: StartScanJobOptions,
  signal: AbortSignal,
  root: string,
  checkAborted: () => void,
  recordError: (p: string, code: string) => void,
  emit: (p: string, force?: boolean) => void,
): Promise<void> {
  const { counters } = ctx;
  const visitedDirs = new Set<string>();
  const visitedRealpaths = new Set<string>();

  let rootStat: Stats;
  try {
    rootStat = await fsp.stat(root);
    visitedRealpaths.add(await fsp.realpath(root));
  } catch (err) {
    recordError(root, errnoCode(err));
    throw err;
  }
  visitedDirs.add(`${rootStat.dev}:${rootStat.ino}`);

  const stack: string[] = [root];
  while (stack.length > 0) {
    checkAborted();
    const dir = stack.pop() as string;
    let entries: Dirent[];
    try {
      entries = await fsp.readdir(dir, { withFileTypes: true });
    } catch (err) {
      recordError(dir, errnoCode(err));
      continue;
    }
    counters.dirs += 1;

    for (const entry of entries) {
      checkAborted();
      const full = path.join(dir, entry.name);
      if (options.hooks?.beforeEntry) {
        await options.hooks.beforeEntry(full);
        checkAborted();
      }
      if (isExcluded(normalizeRel(root, full), options.exclusions)) {
        counters.excluded += 1;
        continue;
      }
      // Yield so the Electron main thread never blocks on huge trees.
      await yieldTick();

      // NEVER follow symlinks/junctions: record and skip.
      if (entry.isSymbolicLink()) {
        let linkSize = 0;
        try {
          linkSize = (await fsp.lstat(full)).size;
        } catch {
          // best effort; a vanished link still counts as skipped
        }
        recordFile(db, options.scanId, full, linkSize, true);
        counters.symlinks += 1;
        continue;
      }

      if (entry.isDirectory()) {
        let st: Stats;
        try {
          st = await fsp.stat(full);
        } catch (err) {
          recordError(full, errnoCode(err));
          continue;
        }
        if (!st.isDirectory()) {
          recordError(full, 'NOT_A_DIRECTORY');
          continue;
        }
        const key = `${st.dev}:${st.ino}`;
        let real: string | null = null;
        try {
          real = await fsp.realpath(full);
        } catch {
          // best effort; the (dev, ino) guard below still applies
        }
        if (visitedDirs.has(key) || (real !== null && visitedRealpaths.has(real))) {
          recordError(full, 'DIRECTORY_LOOP');
          continue;
        }
        visitedDirs.add(key);
        if (real !== null) visitedRealpaths.add(real);
        stack.push(full);
        continue;
      }

      if (entry.isFile()) {
        let st: Stats;
        try {
          st = await fsp.stat(full);
        } catch (err) {
          recordError(full, errnoCode(err));
          continue;
        }
        const fileId = recordFile(db, options.scanId, full, st.size, false, {
          dev: st.dev,
          ino: st.ino,
        });
        addCandidate(ctx, st.size, { id: fileId, path: full, dev: st.dev, ino: st.ino });
        counters.files += 1;
        counters.bytes += st.size;
        emit(full);
        continue;
      }

      // d_type unknown (some filesystems) or special file (socket/fifo):
      // resolve with lstat without following anything.
      try {
        const st = await fsp.lstat(full);
        if (st.isDirectory()) {
          // A directory whose d_type was unknown: treat like one, guarded.
          const key = `${st.dev}:${st.ino}`;
          if (!visitedDirs.has(key)) {
            visitedDirs.add(key);
            stack.push(full);
          } else {
            recordError(full, 'DIRECTORY_LOOP');
          }
        } else if (st.isFile()) {
          const fileId = recordFile(db, options.scanId, full, st.size, false, {
            dev: st.dev,
            ino: st.ino,
          });
          addCandidate(ctx, st.size, { id: fileId, path: full, dev: st.dev, ino: st.ino });
          counters.files += 1;
          counters.bytes += st.size;
          emit(full);
        } else if (st.isSymbolicLink()) {
          recordFile(db, options.scanId, full, st.size, true);
          counters.symlinks += 1;
        }
        // sockets, fifos, devices: ignored (not meaningful for storage analysis)
      } catch (err) {
        recordError(full, errnoCode(err));
      }
    }
  }
}

async function hashCandidates(
  db: DatabaseSync,
  ctx: WalkContext,
  options: StartScanJobOptions,
  signal: AbortSignal,
  checkAborted: () => void,
  recordError: (p: string, code: string) => void,
  emit: (p: string, force?: boolean) => void,
): Promise<void> {
  const { counters } = ctx;
  const updateHashStmt = db.prepare('UPDATE files SET sha256 = ? WHERE id = ?');

  db.exec('BEGIN');
  try {
    for (const [size, candidates] of ctx.sizeGroups) {
      // Size-first: only size>0 files with at least one same-size peer proceed.
      if (size === 0 || candidates.length < 2) continue;
      for (const candidate of candidates) {
        checkAborted();
        let st: Stats;
        try {
          st = await fsp.stat(candidate.path);
        } catch (err) {
          // Vanished between walk and hash: skip, never a false group.
          deleteFile(db, candidate.id);
          counters.changed += 1;
          recordError(candidate.path, errnoCode(err));
          continue;
        }
        if (st.size !== size) {
          // Changed between size-read and hash: skip, never a false group.
          deleteFile(db, candidate.id);
          counters.changed += 1;
          continue;
        }
        try {
          const digest = await sha256File(candidate.path, signal);
          if (options.hooks?.afterHashRead) {
            await options.hooks.afterHashRead(candidate.path);
          }
          // Revalidate after reading: a file that changed while its bytes
          // were streaming (append, in-place rewrite, replacement) must not
          // have its digest recorded — the bytes hashed may be a mix of two
          // versions, or already stale, and the group would be presented as
          // verified. Compare identity + size + timestamps against the
          // pre-read stat; any difference excludes the candidate.
          let after: Stats;
          try {
            after = await fsp.stat(candidate.path);
          } catch (err) {
            // Vanished during/just after its own read: skip, never a group.
            deleteFile(db, candidate.id);
            counters.changed += 1;
            recordError(candidate.path, errnoCode(err));
            continue;
          }
          if (
            after.dev !== st.dev ||
            after.ino !== st.ino ||
            after.size !== st.size ||
            after.mtimeMs !== st.mtimeMs ||
            after.ctimeMs !== st.ctimeMs
          ) {
            deleteFile(db, candidate.id);
            counters.changed += 1;
            continue;
          }
          updateHashStmt.run(digest, candidate.id);
        } catch (err) {
          if (err instanceof ScanAborted || signal.aborted) throw err;
          deleteFile(db, candidate.id);
          counters.changed += 1;
          recordError(candidate.path, errnoCode(err));
        }
        emit(candidate.path);
        await yieldTick();
      }
    }
  } finally {
    db.exec('COMMIT');
  }
}
