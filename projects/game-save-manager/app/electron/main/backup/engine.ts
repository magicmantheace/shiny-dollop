/**
 * Backup engine: walk → hash → change-detect → copy → manifest → verify →
 * restore. Never deletes or modifies the user's original save files.
 *
 * Win32-awareness: every path goes through node:path (win32 semantics on
 * Windows, incl. drive letters); manifest relative paths are normalized to
 * forward slashes so they stay portable; on win32, over-long absolute paths
 * get the \\?\ prefix before file operations. These paths cannot be validated
 * on Windows in this environment — see docs/IMPLEMENTATION_TRACKER.md.
 */
import type { DatabaseSync } from 'node:sqlite';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { getGame } from '../db/games';
import { getBackupDetail, getLatestBackup, getLatestManifestMap, insertBackup } from '../db/backups';
import { BackupError, BackupErrorCodes } from './errors';
import type {
  BackupFileEntry,
  CorruptFile,
  CreateBackupResult,
  Game,
  RestoreBackupResult,
  SkippedFile,
  VerifyBackupResult,
} from '../../../shared/types';

export interface EngineDeps {
  db: DatabaseSync;
  /** <userData>/SaveManager/backups — backups live at <root>/<gameId>/<timestamp>/. */
  backupsRoot: string;
}

export interface ProgressCallback {
  (progress: { phase: 'hash' | 'copy'; done: number; total: number; currentFile?: string }): void;
}

export interface CreateBackupOptions {
  // `| undefined` so zod-inferred optional payloads assign under
  // exactOptionalPropertyTypes.
  label?: string | undefined;
  /** Skip the change-detection check and always write a new version. */
  force?: boolean | undefined;
  onProgress?: ProgressCallback | undefined;
}

export interface RestoreBackupOptions {
  confirmed: true;
  onProgress?: ProgressCallback;
}

interface WalkedFile {
  /** Forward-slash relative path (portable manifest key). */
  relPath: string;
  absPath: string;
  sizeBytes: number;
}

/** Cloud-sync conflict copies: backed up as-is, but flagged in the manifest. */
const CONFLICT_NAME_RE = /(-CONFLICT|conflicted copy)/i;

function isConflictCopy(baseName: string): boolean {
  return CONFLICT_NAME_RE.test(baseName);
}

/**
 * Win32 long-path conversion, expressed with `path.win32` semantics so it
 * is testable on any platform. Only paths at/over the length threshold are
 * namespaced; shorter paths are returned resolved but otherwise unchanged.
 *
 * UNC paths need the extended form `\\?\UNC\server\share\...`: naively
 * prepending `\\?\` to `\\server\share\...` produces the invalid
 * `\\?\\server\share\...`. `path.win32.toNamespacedPath()` performs the
 * correct conversion for drive-letter, UNC, and device paths (and leaves
 * already-namespaced paths untouched), so delegate to it.
 */
export function win32LongPathPrefix(p: string): string {
  const absolute = path.win32.resolve(p);
  if (absolute.startsWith('\\\\?\\')) return absolute;
  return absolute.length >= 240 ? path.win32.toNamespacedPath(absolute) : absolute;
}

/**
 * On win32, prefix over-long absolute paths with \\?\ so CreateFileW accepts
 * them. No-op on other platforms (and on win32 for short paths).
 * NOTE: pending validation on real Windows — see IMPLEMENTATION_TRACKER.md.
 */
export function withLongPathPrefix(p: string): string {
  if (process.platform !== 'win32') return p;
  return win32LongPathPrefix(p);
}

/** Recursively list files under dir. Unreadable/locked files are skipped, never fatal. */
export async function walkSaveDir(saveDir: string): Promise<{ files: WalkedFile[]; skipped: SkippedFile[] }> {
  const files: WalkedFile[] = [];
  const skipped: SkippedFile[] = [];

  async function visit(dir: string): Promise<void> {
    let entries: fs.Dirent[];
    try {
      entries = await fs.promises.readdir(withLongPathPrefix(dir), { withFileTypes: true });
    } catch (err) {
      skipped.push({
        relPath: toRelPath(saveDir, dir),
        reason: `unreadable directory: ${(err as Error).message}`,
      });
      return;
    }
    for (const entry of entries) {
      const absPath = path.join(dir, entry.name);
      const relPath = toRelPath(saveDir, absPath);
      if (entry.isDirectory()) {
        await visit(absPath);
      } else if (entry.isSymbolicLink()) {
        // Follow the link: a dangling or non-file symlink is a skip, not a crash.
        try {
          const st = await fs.promises.stat(withLongPathPrefix(absPath));
          if (st.isFile()) {
            files.push({ relPath, absPath, sizeBytes: st.size });
          } else {
            skipped.push({ relPath, reason: 'symlink does not resolve to a file' });
          }
        } catch (err) {
          skipped.push({ relPath, reason: `unreadable symlink: ${(err as Error).message}` });
        }
      } else if (entry.isFile()) {
        // Stat here (not just readdir) so dangling symlinks / locked files
        // surface as skips rather than crashing the hash phase.
        try {
          const st = await fs.promises.stat(withLongPathPrefix(absPath));
          if (!st.isFile()) {
            skipped.push({ relPath, reason: 'not a regular file' });
            continue;
          }
          files.push({ relPath, absPath, sizeBytes: st.size });
        } catch (err) {
          skipped.push({ relPath, reason: `unreadable file: ${(err as Error).message}` });
        }
      }
      // Other kinds (sockets, fifos, reparse points that aren't files) are ignored.
    }
  }

  await visit(saveDir);
  files.sort((a, b) => (a.relPath < b.relPath ? -1 : a.relPath > b.relPath ? 1 : 0));
  return { files, skipped };
}

function toRelPath(saveDir: string, absPath: string): string {
  return path.relative(saveDir, absPath).split(path.sep).join('/');
}

/** SHA-256 of a file, streamed so multi-GB saves don't blow up memory. */
export async function hashFile(absPath: string): Promise<string> {
  return (await hashFileWithSize(absPath)).sha256;
}

/**
 * SHA-256 AND byte count of a file, measured over the SAME streamed bytes.
 * The size must come from the bytes actually read — never from an earlier
 * stat: a game can resize a save between the directory walk and hashing, and
 * recording the stale walk-time size produces a manifest whose size disagrees
 * with its own hash/copied bytes (the backup then fails verification).
 */
export async function hashFileWithSize(
  absPath: string,
): Promise<{ sha256: string; sizeBytes: number }> {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256');
    let sizeBytes = 0;
    const stream = fs.createReadStream(withLongPathPrefix(absPath));
    stream.on('data', (chunk: Buffer) => {
      sizeBytes += chunk.length;
      hash.update(chunk);
    });
    stream.on('error', reject);
    stream.on('end', () => resolve({ sha256: hash.digest('hex'), sizeBytes }));
  });
}

function sanitizeIsoTimestamp(iso: string): string {
  // 2026-10-23T10:30:00.000Z -> 2026-10-23T10-30-00-000Z (no : or .)
  return iso.replace(/[:.]/g, '-');
}

/**
 * Where backup metadata lives.
 *
 * NEW layout: `<backupDir>.manifest.json` — a SIBLING of the backup dir, never
 * inside the mirrored tree. (Previously the metadata was written to
 * `<backupDir>/manifest.json`, inside the tree: a user's own `manifest.json`
 * save file landed at that exact path first and was then overwritten by the
 * metadata — data loss on backup, and metadata bytes restored over the real
 * save on restore.)
 *
 * LEGACY layout: `<backupDir>/manifest.json` (in-tree). Reads check the
 * sibling location first and fall back to the legacy path, so backups made
 * before this change still verify and restore.
 */
export function siblingManifestPath(backupDir: string): string {
  return `${backupDir}.manifest.json`;
}

function legacyManifestPath(backupDir: string): string {
  return path.join(backupDir, 'manifest.json');
}

interface StoredManifestRead {
  manifest: StoredManifest;
  /** True when the metadata was found at the legacy in-tree location. */
  legacy: boolean;
}

function readStoredManifest(backupDir: string): StoredManifestRead | null {
  const sibling = siblingManifestPath(backupDir);
  if (fs.existsSync(withLongPathPrefix(sibling))) {
    try {
      const raw = fs.readFileSync(withLongPathPrefix(sibling), 'utf8');
      return { manifest: JSON.parse(raw) as StoredManifest, legacy: false };
    } catch {
      return null;
    }
  }
  try {
    const raw = fs.readFileSync(withLongPathPrefix(legacyManifestPath(backupDir)), 'utf8');
    return { manifest: JSON.parse(raw) as StoredManifest, legacy: true };
  } catch {
    return null;
  }
}

/** Backup dir, made unique if two backups land in the same millisecond. */
function uniqueBackupDir(backupsRoot: string, gameId: number, createdAt: string): string {
  const base = path.join(backupsRoot, String(gameId), sanitizeIsoTimestamp(createdAt));
  let dir = base;
  let n = 1;
  while (fs.existsSync(withLongPathPrefix(dir))) {
    dir = `${base}-${n++}`;
  }
  return dir;
}

/** Case-folded resolved path for comparisons (win32 paths are case-insensitive). */
function normalizeForCompare(p: string): string {
  const resolved = path.resolve(p);
  return process.platform === 'win32' ? resolved.toLowerCase() : resolved;
}

/** True when `child` equals `parent` or lives anywhere underneath it. */
export function isPathWithin(parent: string, child: string): boolean {
  const rel = path.relative(normalizeForCompare(parent), normalizeForCompare(child));
  return rel === '' || (rel !== '..' && !rel.startsWith(`..${path.sep}`) && !path.isAbsolute(rel));
}

/**
 * Reject overlapping source/destination roots BEFORE walking or writing.
 *
 * If the save folder contains the backup storage folder, walking the saves
 * includes every previous backup — each new snapshot swallows all earlier
 * ones and the backup tree grows exponentially (1, 3, 7, 15, … files). The
 * reverse (a "save folder" inside backup storage) is the same trap from the
 * other side. Neither layout can ever be backed up or restored safely.
 */
function assertNoBackupOverlap(savePath: string, backupsRoot: string): void {
  if (isPathWithin(savePath, backupsRoot) || isPathWithin(backupsRoot, savePath)) {
    throw new BackupError(
      BackupErrorCodes.BACKUP_DESTINATION_OVERLAPS_SAVE_DIR,
      `Save folder and backup storage overlap: the save folder (${savePath}) and the ` +
        `backup storage folder (${backupsRoot}) must not contain one another — backing up ` +
        `would copy previous backups into every new backup and grow without bound. ` +
        `Re-register the game with its actual save folder (not a parent of the backup ` +
        `storage, and not a folder inside it).`,
    );
  }
}

function errnoCode(err: unknown): string | undefined {
  return (err as NodeJS.ErrnoException | undefined)?.code;
}

/**
 * True when a save path that stat() reported as ENOENT is GENUINELY absent:
 * some ancestor exists as a readable directory, so the path is simply a
 * deleted folder below a real location and can be recreated. False when no
 * existing directory ancestor can be found (e.g. a disconnected drive whose
 * root itself is gone) or an ancestor is unreadable / not a directory — in
 * those cases absence cannot be distinguished from a lost destination, and
 * recreating directories at a guessed location would be wrong.
 */
async function isGenuinelyAbsent(savePath: string): Promise<boolean> {
  let current = path.resolve(savePath);
  for (;;) {
    const parent = path.dirname(current);
    if (parent === current) return false; // Even the root is missing: disconnected.
    try {
      const st = await fs.promises.stat(withLongPathPrefix(parent));
      return st.isDirectory();
    } catch (err) {
      if (errnoCode(err) !== 'ENOENT') return false; // Unreadable ancestor: cannot prove absence.
      current = parent;
    }
  }
}

/**
 * Record an EMPTY pre-restore safety snapshot: used when the save folder is
 * genuinely absent at restore time. There is no current state to preserve,
 * but the restore contract ("a safety backup is always taken first") still
 * holds — the snapshot is recorded with zero files and a note explaining
 * why, so `safetyBackupId` always points at a real, verifiable backup.
 */
function recordEmptySafetyBackup(deps: EngineDeps, game: Game): CreateBackupResult {
  const createdAt = new Date().toISOString();
  const backupDir = uniqueBackupDir(deps.backupsRoot, game.id, createdAt);
  fs.mkdirSync(withLongPathPrefix(backupDir), { recursive: true });
  const note =
    `Save folder was missing at restore time (${game.savePath}); this safety snapshot ` +
    `is intentionally empty — there was no current state to preserve. The restore ` +
    `recreates the folder.`;
  const manifest: StoredManifest = {
    version: 1,
    gameId: game.id,
    label: 'pre-restore safety',
    createdAt,
    notes: [note],
    skippedFiles: [],
    files: [],
  };
  fs.writeFileSync(
    withLongPathPrefix(siblingManifestPath(backupDir)),
    JSON.stringify(manifest, null, 2),
    'utf8',
  );
  const backup = insertBackup(deps.db, {
    gameId: game.id,
    label: 'pre-restore safety',
    fileCount: 0,
    totalBytes: 0,
    backupDir,
    notes: note,
    files: [],
  });
  return { skipped: false, backup, skippedFiles: [], notes: [note] };
}

/**
 * Take the pre-restore safety backup of the CURRENT save-dir state.
 *
 * Missing-destination handling: if the save folder was deleted after the
 * backup being restored was taken, `createBackup` would throw
 * SAVE_DIR_MISSING and the intact backup could never be restored — the
 * restore's own directory recreation would never be reached. A genuinely
 * absent folder (see isGenuinelyAbsent) instead gets an empty safety
 * snapshot and the restore proceeds to recreate it. An unreadable or
 * disconnected destination (stat fails for any other reason, the nearest
 * existing ancestor is not a directory, or the path exists but is not a
 * folder) is still rejected with SAVE_DIR_MISSING before anything is
 * written — absence must never be guessed at.
 */
async function createSafetyBackup(
  deps: EngineDeps,
  game: Game,
  onProgress: ProgressCallback | undefined,
): Promise<CreateBackupResult> {
  let stat: fs.Stats | null = null;
  let statError: unknown = null;
  try {
    stat = await fs.promises.stat(withLongPathPrefix(game.savePath));
  } catch (err) {
    statError = err;
  }
  if (stat) {
    if (!stat.isDirectory()) {
      throw new BackupError(
        BackupErrorCodes.SAVE_DIR_MISSING,
        `Save path is not a folder: ${game.savePath}. Restore aborted — nothing was ` +
          `written. Re-register the save folder from the Games list.`,
      );
    }
    return createBackup(deps, game.id, {
      label: 'pre-restore safety',
      force: true,
      onProgress,
    });
  }
  if (errnoCode(statError) === 'ENOENT' && (await isGenuinelyAbsent(game.savePath))) {
    return recordEmptySafetyBackup(deps, game);
  }
  throw new BackupError(
    BackupErrorCodes.SAVE_DIR_MISSING,
    `Save folder cannot be reached: ${game.savePath}. The drive may be disconnected ` +
      `or the folder may be unreadable. Restore aborted — nothing was written. ` +
      `Reconnect the drive (or re-register the save folder) and try again.`,
  );
}

interface StoredManifest {
  version: 1;
  gameId: number;
  label: string | null;
  createdAt: string;
  notes: string[];
  skippedFiles: SkippedFile[];
  files: BackupFileEntry[];
}

/**
 * Create a new backup version of the game's save folder.
 * Change detection: if every file matches the latest backup's manifest
 * (same rel paths, same sizes, same SHA-256), no new version is written and
 * { skipped: true } is returned. Originals are never modified or deleted.
 */
export async function createBackup(
  deps: EngineDeps,
  gameId: number,
  options: CreateBackupOptions = {},
): Promise<CreateBackupResult> {
  const { db, backupsRoot } = deps;
  const game = getGame(db, gameId);
  if (!game) {
    throw new BackupError(
      BackupErrorCodes.GAME_NOT_FOUND,
      `Game #${gameId} is not tracked. It may have been removed.`,
    );
  }

  // Overlap check first: never walk a save folder that contains (or lives
  // inside) the backup storage — the walk would include previous backups.
  assertNoBackupOverlap(game.savePath, backupsRoot);

  let saveStat: fs.Stats;
  try {
    saveStat = await fs.promises.stat(withLongPathPrefix(game.savePath));
  } catch {
    throw new BackupError(
      BackupErrorCodes.SAVE_DIR_MISSING,
      `Save folder not found: ${game.savePath}. The game may have moved its saves, ` +
        `or the drive may be disconnected. Re-register the save folder from the Games list.`,
    );
  }
  if (!saveStat.isDirectory()) {
    throw new BackupError(
      BackupErrorCodes.SAVE_DIR_MISSING,
      `Save path is not a folder: ${game.savePath}. Re-register the save folder from the Games list.`,
    );
  }

  const { files, skipped } = await walkSaveDir(game.savePath);

  // Hash phase (streamed, one file at a time; per-file failures -> skip+warn).
  const entries: BackupFileEntry[] = [];
  const notes: string[] = [];
  let totalBytes = 0;
  for (let i = 0; i < files.length; i++) {
    const f = files[i] as WalkedFile;
    options.onProgress?.({ phase: 'hash', done: i, total: files.length, currentFile: f.relPath });
    try {
      // Size comes from the bytes actually hashed, not the walk-time stat:
      // the file may have been resized since walkSaveDir measured it.
      const { sha256, sizeBytes } = await hashFileWithSize(f.absPath);
      entries.push({ relPath: f.relPath, sha256, sizeBytes });
      totalBytes += sizeBytes;
      if (isConflictCopy(path.basename(f.relPath))) {
        notes.push(
          `Cloud-sync conflict copy backed up as-is (not resolved): ${f.relPath}`,
        );
      }
    } catch (err) {
      skipped.push({ relPath: f.relPath, reason: `unreadable while hashing: ${(err as Error).message}` });
    }
  }
  options.onProgress?.({ phase: 'hash', done: files.length, total: files.length });

  // Skipped files are warnings the user must be able to see later, not just
  // in the create result: persist them in the backup's notes (shown in the
  // backup detail view) as well as in the manifest/result skippedFiles.
  for (const s of skipped) {
    notes.push(`Skipped file (not backed up): ${s.relPath} — ${s.reason}`);
  }

  // Change detection against the latest manifest.
  if (!options.force) {
    const prev = getLatestManifestMap(db, gameId);
    if (prev.size === entries.length && entries.every((e) => {
      const p = prev.get(e.relPath);
      return p !== undefined && p.sha256 === e.sha256 && p.sizeBytes === e.sizeBytes;
    })) {
      const latest = getLatestBackup(db, gameId);
      // latest must exist: prev was non-empty... unless the save dir is empty.
      // An empty save dir with a previous empty backup is also "unchanged".
      if (latest) {
        return {
          skipped: true,
          reason: 'No changes since the last backup — no new version created.',
          backup: latest,
          skippedFiles: skipped,
          notes,
        };
      }
    }
  }

  // Copy phase.
  const createdAt = new Date().toISOString();
  const backupDir = uniqueBackupDir(backupsRoot, gameId, createdAt);
  fs.mkdirSync(withLongPathPrefix(backupDir), { recursive: true });

  for (let i = 0; i < entries.length; i++) {
    const e = entries[i] as BackupFileEntry;
    const src = (files.find((f) => f.relPath === e.relPath) as WalkedFile).absPath;
    const dest = path.join(backupDir, ...e.relPath.split('/'));
    options.onProgress?.({ phase: 'copy', done: i, total: entries.length, currentFile: e.relPath });
    fs.mkdirSync(withLongPathPrefix(path.dirname(dest)), { recursive: true });
    await fs.promises.copyFile(withLongPathPrefix(src), withLongPathPrefix(dest));
    // Hash-before-copy race: the game may have rewritten the save between our
    // hash phase and this copy. Re-hash the DESTINATION bytes (hash + size,
    // measured over the stored bytes) and fail loudly instead of recording a
    // checksum/size that doesn't match the stored bytes.
    const destHashed = await hashFileWithSize(dest);
    if (destHashed.sha256 !== e.sha256 || destHashed.sizeBytes !== e.sizeBytes) {
      // Discard the partial backup — a half-written version must never be
      // presented as a good one, and no DB row is recorded.
      fs.rmSync(withLongPathPrefix(backupDir), { recursive: true, force: true });
      throw new BackupError(
        BackupErrorCodes.BACKUP_COPY_MISMATCH,
        `File changed while being backed up: ${e.relPath}. The bytes written do not ` +
          `match the checksum recorded moments earlier — the game probably wrote to it ` +
          `mid-backup. No backup was recorded; close the game and try again.`,
      );
    }
  }
  options.onProgress?.({ phase: 'copy', done: entries.length, total: entries.length });

  const manifest: StoredManifest = {
    version: 1,
    gameId,
    label: options.label ?? null,
    createdAt,
    notes,
    skippedFiles: skipped,
    files: entries,
  };
  fs.writeFileSync(
    withLongPathPrefix(siblingManifestPath(backupDir)),
    JSON.stringify(manifest, null, 2),
    'utf8',
  );

  const backup = insertBackup(db, {
    gameId,
    label: options.label ?? null,
    fileCount: entries.length,
    totalBytes,
    backupDir,
    notes: notes.length > 0 ? notes.join('\n') : null,
    files: entries,
  });

  return { skipped: false, backup, skippedFiles: skipped, notes };
}

/**
 * Re-hash every stored file of a backup against its DB manifest.
 * Flags missing files, checksum mismatches and size mismatches.
 */
export async function verifyBackup(deps: EngineDeps, backupId: number): Promise<VerifyBackupResult> {
  const { db } = deps;
  const detail = getBackupDetail(db, backupId);
  if (!detail) {
    throw new BackupError(
      BackupErrorCodes.BACKUP_NOT_FOUND,
      `Backup #${backupId} does not exist.`,
    );
  }
  const stored = readStoredManifest(detail.backupDir);
  if (!stored) {
    throw new BackupError(
      BackupErrorCodes.BACKUP_DIR_MISSING,
      `Backup folder is missing or unreadable: ${detail.backupDir}. ` +
        `The backup files may have been moved or deleted outside the app.`,
    );
  }

  const corrupt: CorruptFile[] = [];
  for (const f of detail.files) {
    // Legacy backups stored their metadata at <backupDir>/manifest.json — if
    // the DB lists a user-owned 'manifest.json' entry for such a backup, the
    // old metadata write DESTROYED that file: the bytes at the path are the
    // metadata, not the user's save, and the original bytes are
    // unrecoverable. Report the entry as missing/corrupt rather than
    // silently skipping it and certifying the backup as intact. (Restore
    // keeps its separate protection: it never copies those metadata bytes
    // over the user's current file.) New backups keep metadata as a sibling
    // file, so a user's own manifest.json verifies normally there.
    if (stored.legacy && f.relPath === 'manifest.json') {
      corrupt.push({ relPath: f.relPath, issue: 'missing', expected: f.sha256 });
      continue;
    }
    const absPath = path.join(detail.backupDir, ...f.relPath.split('/'));
    let stat: fs.Stats | null = null;
    try {
      stat = await fs.promises.stat(withLongPathPrefix(absPath));
    } catch {
      stat = null;
    }
    if (!stat || !stat.isFile()) {
      corrupt.push({ relPath: f.relPath, issue: 'missing', expected: f.sha256 });
      continue;
    }
    if (stat.size !== f.sizeBytes) {
      corrupt.push({
        relPath: f.relPath,
        issue: 'size-mismatch',
        expected: String(f.sizeBytes),
        actual: String(stat.size),
      });
      continue;
    }
    const actual = await hashFile(absPath);
    if (actual !== f.sha256) {
      corrupt.push({ relPath: f.relPath, issue: 'checksum-mismatch', expected: f.sha256, actual });
    }
  }

  return { backupId, ok: corrupt.length === 0, checkedFiles: detail.files.length, corrupt };
}

/**
 * Restore a backup over the game's save folder.
 *
 * Requires { confirmed: true } — there is no other way to call this.
 * Safety order:
 *   1. Take a fresh safety backup of the CURRENT save-dir state
 *      (label "pre-restore safety", force: true so it always records).
 *   2. Copy the backup's files over the save dir (overwrite/add only —
 *      files that exist in the save dir but not in the backup are left alone;
 *      nothing is ever deleted).
 *   3. Re-hash the restored files and report mismatches.
 */
export async function restoreBackup(
  deps: EngineDeps,
  backupId: number,
  options: RestoreBackupOptions,
): Promise<RestoreBackupResult> {
  if (!options || options.confirmed !== true) {
    throw new BackupError(
      BackupErrorCodes.RESTORE_NOT_CONFIRMED,
      'Restore requires explicit confirmation (confirmed: true). Refusing to overwrite save data.',
    );
  }
  const { db } = deps;
  const detail = getBackupDetail(db, backupId);
  if (!detail) {
    throw new BackupError(
      BackupErrorCodes.BACKUP_NOT_FOUND,
      `Backup #${backupId} does not exist.`,
    );
  }
  const game = getGame(db, detail.gameId);
  if (!game) {
    throw new BackupError(
      BackupErrorCodes.GAME_NOT_FOUND,
      `Game #${detail.gameId} is not tracked. It may have been removed.`,
    );
  }

  // Overlapping roots are rejected for restore too: the safety backup (and,
  // for a missing save folder, its empty snapshot) must never be written
  // into storage that lives inside the folder being restored over.
  assertNoBackupOverlap(game.savePath, deps.backupsRoot);

  // 1. Safety backup of the current state (always a fresh version). When
  // the save folder itself is genuinely absent, this records an empty
  // safety snapshot instead of failing — step 2 recreates the folder.
  const safety = await createSafetyBackup(deps, game, options.onProgress);
  const safetyBackup = safety.backup;

  // The escape hatch must never be incomplete: if the safety backup had to
  // skip files (locked by the game, unreadable, …), abort BEFORE any writes.
  if (safety.skippedFiles.length > 0) {
    const names = safety.skippedFiles.map((s) => `${s.relPath} (${s.reason})`).join('; ');
    throw new BackupError(
      BackupErrorCodes.SAFETY_BACKUP_INCOMPLETE,
      `Pre-restore safety backup was incomplete — skipped ${safety.skippedFiles.length} ` +
        `file(s): ${names}. Restore aborted before touching your saves. ` +
        `Close the game (or free whatever is locking those files) and try again. ` +
        `The partial safety backup (#${safetyBackup.id}) is intact if you need it.`,
    );
  }

  // Legacy backups keep their metadata at <backupDir>/manifest.json (in-tree):
  // never copy those bytes as if they were the user's save file.
  const legacyInTreeManifest = readStoredManifest(detail.backupDir)?.legacy === true;

  // 2. Copy backup files over the save dir. The mkdir recreates the folder
  // when it was genuinely absent (the empty-safety-snapshot path above).
  fs.mkdirSync(withLongPathPrefix(game.savePath), { recursive: true });
  let restoredFiles = 0;
  for (let i = 0; i < detail.files.length; i++) {
    const f = detail.files[i] as BackupFileEntry;
    if (legacyInTreeManifest && f.relPath === 'manifest.json') continue;
    const src = path.join(detail.backupDir, ...f.relPath.split('/'));
    const dest = path.join(game.savePath, ...f.relPath.split('/'));
    options.onProgress?.({ phase: 'copy', done: i, total: detail.files.length, currentFile: f.relPath });
    try {
      await fs.promises.stat(withLongPathPrefix(src));
    } catch {
      throw new BackupError(
        BackupErrorCodes.BACKUP_DIR_MISSING,
        `Backup file went missing mid-restore: ${f.relPath}. The restore was NOT completed; ` +
          `your pre-restore safety backup (#${safetyBackup.id}) is intact.`,
      );
    }
    fs.mkdirSync(withLongPathPrefix(path.dirname(dest)), { recursive: true });
    await fs.promises.copyFile(withLongPathPrefix(src), withLongPathPrefix(dest));
    restoredFiles++;
  }
  options.onProgress?.({ phase: 'copy', done: detail.files.length, total: detail.files.length });

  // 3. Post-restore verification.
  const mismatches: CorruptFile[] = [];
  for (const f of detail.files) {
    // Same legacy carve-out as the copy loop: the in-tree manifest.json is
    // old metadata, not user data — it was deliberately not restored.
    if (legacyInTreeManifest && f.relPath === 'manifest.json') continue;
    const dest = path.join(game.savePath, ...f.relPath.split('/'));
    try {
      const stat = await fs.promises.stat(withLongPathPrefix(dest));
      if (stat.size !== f.sizeBytes) {
        mismatches.push({
          relPath: f.relPath,
          issue: 'size-mismatch',
          expected: String(f.sizeBytes),
          actual: String(stat.size),
        });
        continue;
      }
      const actual = await hashFile(dest);
      if (actual !== f.sha256) {
        mismatches.push({ relPath: f.relPath, issue: 'checksum-mismatch', expected: f.sha256, actual });
      }
    } catch {
      mismatches.push({ relPath: f.relPath, issue: 'missing', expected: f.sha256 });
    }
  }

  return {
    backupId,
    safetyBackupId: safetyBackup.id,
    restoredFiles,
    mismatches,
  };
}
