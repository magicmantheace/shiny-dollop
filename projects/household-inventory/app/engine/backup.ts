/**
 * Portable backup format: a zip archive containing
 *   - manifest.json            (format marker + per-file sha256 inventory)
 *   - inventory.db             (consistent snapshot via VACUUM INTO)
 *   - attachments/<storedName> (raw attachment bytes)
 *
 * No 'electron' import — backend tests exercise export/import round-trips
 * directly. The Electron dialogs, rollback and DB close/reopen live in
 * electron/ipc.ts, which calls into this module.
 */
import type { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { strFromU8, strToU8, unzipSync, zipSync } from 'fflate';
import { countAttachments, countItems } from '../db/records';
import { DB_FILE_NAME } from '../db/paths';

export const BACKUP_FORMAT = 'household-inventory-backup';
export const BACKUP_FORMAT_VERSION = 1;

export interface BackupManifestFile {
  path: string;
  sha256: string;
  sizeBytes: number;
}

export interface BackupManifest {
  format: string;
  formatVersion: number;
  exportedAt: string;
  appVersion: string;
  itemCount: number;
  attachmentCount: number;
  files: BackupManifestFile[];
}

export interface CreateBackupOptions {
  db: DatabaseSync;
  attachmentsDir: string;
  appVersion: string;
  exportedAt?: string;
}

export interface BackupArchiveResult {
  /** Raw zip bytes, ready to write to disk. */
  data: Uint8Array;
  manifest: BackupManifest;
  itemCount: number;
  attachmentCount: number;
}

export interface ExtractedBackup {
  manifest: BackupManifest;
  /** path (as in the manifest) -> raw file bytes. */
  files: Map<string, Uint8Array>;
}

function sha256Hex(bytes: Uint8Array): string {
  return createHash('sha256').update(bytes).digest('hex');
}

function escapeSqlString(s: string): string {
  return s.replace(/'/g, "''");
}

/**
 * Consistent point-in-time snapshot of the open DB into `destPath`.
 * VACUUM INTO works on a live connection (even in WAL mode) and fails
 * loudly instead of copying a torn file. Must not run inside a transaction.
 */
export function snapshotDatabaseToFile(db: DatabaseSync, destPath: string): void {
  fs.mkdirSync(path.dirname(destPath), { recursive: true });
  db.exec(`VACUUM INTO '${escapeSqlString(destPath)}'`);
}

/**
 * Build the backup zip from the live database + attachment files.
 * Throws when an attachment row references a file missing on disk —
 * a backup must never silently drop bytes.
 */
export function createBackupArchive(opts: CreateBackupOptions): BackupArchiveResult {
  const { db, attachmentsDir, appVersion } = opts;
  const itemCount = countItems(db);
  const attachmentCount = countAttachments(db);

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'hi-backup-'));
  try {
    const dbSnapshotPath = path.join(tmpDir, DB_FILE_NAME);
    snapshotDatabaseToFile(db, dbSnapshotPath);
    const dbBytes = fs.readFileSync(dbSnapshotPath);

    const zipEntries: Record<string, Uint8Array> = {};
    const manifestFiles: BackupManifestFile[] = [];

    const addFile = (zipPath: string, bytes: Uint8Array): void => {
      zipEntries[zipPath] = bytes;
      manifestFiles.push({ path: zipPath, sha256: sha256Hex(bytes), sizeBytes: bytes.byteLength });
    };

    addFile(DB_FILE_NAME, dbBytes);

    // Walk the DB rows (source of truth), not the directory listing, so the
    // manifest always agrees with the attachment table.
    const rows = listAttachmentsForAllItems(db);
    for (const row of rows) {
      const filePath = path.join(attachmentsDir, row.storedName);
      let bytes: Buffer;
      try {
        bytes = fs.readFileSync(filePath);
      } catch (err) {
        if ((err as NodeJS.ErrnoException).code === 'ENOENT') {
          throw new Error(
            `Backup aborted: attachment file missing on disk (attachment ${row.id}, stored as ${row.storedName}).`,
          );
        }
        throw err;
      }
      const actual = sha256Hex(bytes);
      if (actual !== row.sha256) {
        throw new Error(
          `Backup aborted: attachment ${row.id} failed integrity check (expected ${row.sha256}, got ${actual}).`,
        );
      }
      addFile(`attachments/${row.storedName}`, bytes);
    }

    const manifest: BackupManifest = {
      format: BACKUP_FORMAT,
      formatVersion: BACKUP_FORMAT_VERSION,
      exportedAt: opts.exportedAt ?? new Date().toISOString(),
      appVersion,
      itemCount,
      attachmentCount,
      files: manifestFiles,
    };
    const manifestBytes = strToU8(JSON.stringify(manifest, null, 2));
    zipEntries['manifest.json'] = manifestBytes;

    const data = zipSync(zipEntries, { level: 6 });
    return { data, manifest, itemCount, attachmentCount };
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

/** Every attachment row in the DB, regardless of item. */
function listAttachmentsForAllItems(db: DatabaseSync): { id: string; storedName: string; sha256: string }[] {
  const rows = db
    .prepare('SELECT id, stored_name, sha256 FROM attachments ORDER BY id ASC')
    .all() as { id: string; stored_name: string; sha256: string }[];
  return rows.map((r) => ({ id: r.id, storedName: r.stored_name, sha256: r.sha256 }));
}

function isManifest(value: unknown): value is BackupManifest {
  if (typeof value !== 'object' || value === null) return false;
  const m = value as Record<string, unknown>;
  return (
    m['format'] === BACKUP_FORMAT &&
    m['formatVersion'] === BACKUP_FORMAT_VERSION &&
    typeof m['exportedAt'] === 'string' &&
    typeof m['appVersion'] === 'string' &&
    typeof m['itemCount'] === 'number' &&
    typeof m['attachmentCount'] === 'number' &&
    Array.isArray(m['files'])
  );
}

/**
 * Parse + fully verify a backup zip: manifest format/version, every listed
 * file present, every sha256 matching. Returns the manifest and file bytes.
 * Throws on any integrity problem.
 */
export function extractBackupArchive(data: Uint8Array): ExtractedBackup {
  let entries: Record<string, Uint8Array>;
  try {
    entries = unzipSync(data);
  } catch (err) {
    throw new Error(`Backup is not a readable zip archive: ${(err as Error).message}`);
  }
  const manifestBytes = entries['manifest.json'];
  if (!manifestBytes) throw new Error('Backup is missing manifest.json.');
  let manifest: unknown;
  try {
    manifest = JSON.parse(strFromU8(manifestBytes));
  } catch {
    throw new Error('Backup manifest.json is not valid JSON.');
  }
  if (!isManifest(manifest)) {
    throw new Error(
      'Backup manifest has an unrecognized format or version (expected household-inventory-backup v1).',
    );
  }
  const files = new Map<string, Uint8Array>();
  for (const f of manifest.files) {
    const bytes = entries[f.path];
    if (!bytes) throw new Error(`Backup is missing listed file: ${f.path}`);
    const actual = sha256Hex(bytes);
    if (actual !== f.sha256) {
      throw new Error(`Backup file failed integrity check: ${f.path}`);
    }
    if (bytes.byteLength !== f.sizeBytes) {
      throw new Error(`Backup file size mismatch: ${f.path}`);
    }
    files.set(f.path, bytes);
  }
  if (!files.has(DB_FILE_NAME)) {
    throw new Error('Backup manifest does not list inventory.db.');
  }
  return { manifest, files };
}

const SAFE_RESTORE_RE = /^(?:inventory\.db|attachments\/[A-Za-z0-9._-]+)$/;

/**
 * Write an extracted backup into `targetDir` (inventory.db at the root,
 * attachments/* under attachments/). Paths are allow-listed — anything else
 * in the archive is refused rather than written.
 */
export function restoreBackupToDir(extracted: ExtractedBackup, targetDir: string): void {
  for (const [zipPath, bytes] of extracted.files) {
    if (!SAFE_RESTORE_RE.test(zipPath)) {
      throw new Error(`Refusing to restore unexpected backup path: ${zipPath}`);
    }
    const dest = path.join(targetDir, zipPath);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, bytes);
  }
}
