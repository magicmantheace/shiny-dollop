/** CRUD for backups and their file manifests. Pure SQL over DatabaseSync. */
import type { DatabaseSync } from 'node:sqlite';
import type { Backup, BackupDetail, BackupFileEntry } from '../../../shared/types';
import { allRows, oneRow } from './rows';

interface BackupRow {
  id: number;
  game_id: number;
  created_at: string;
  label: string | null;
  file_count: number;
  total_bytes: number;
  backup_dir: string;
  notes: string | null;
}

interface BackupFileRow {
  rel_path: string;
  sha256: string;
  size_bytes: number;
}

function toBackup(row: BackupRow): Backup {
  return {
    id: row.id,
    gameId: row.game_id,
    createdAt: row.created_at,
    label: row.label,
    fileCount: row.file_count,
    totalBytes: row.total_bytes,
    backupDir: row.backup_dir,
    notes: row.notes,
  };
}

export function listBackups(db: DatabaseSync, gameId: number): Backup[] {
  const rows = allRows<BackupRow>(
    db.prepare('SELECT * FROM backups WHERE game_id = ? ORDER BY id DESC').all(gameId),
  );
  return rows.map(toBackup);
}

export function getBackup(db: DatabaseSync, backupId: number): Backup | null {
  const row = oneRow<BackupRow>(db.prepare('SELECT * FROM backups WHERE id = ?').get(backupId));
  return row ? toBackup(row) : null;
}

export function getLatestBackup(db: DatabaseSync, gameId: number): Backup | null {
  const row = oneRow<BackupRow>(
    db.prepare('SELECT * FROM backups WHERE game_id = ? ORDER BY id DESC LIMIT 1').get(gameId),
  );
  return row ? toBackup(row) : null;
}

export function getBackupDetail(db: DatabaseSync, backupId: number): BackupDetail | null {
  const backup = getBackup(db, backupId);
  if (!backup) return null;
  const fileRows = allRows<BackupFileRow>(
    db
      .prepare('SELECT rel_path, sha256, size_bytes FROM backup_files WHERE backup_id = ? ORDER BY rel_path')
      .all(backupId),
  );
  const files: BackupFileEntry[] = fileRows.map((r) => ({
    relPath: r.rel_path,
    sha256: r.sha256,
    sizeBytes: r.size_bytes,
  }));
  return { ...backup, files };
}

/** Maps relPath -> {sha256, sizeBytes} for the latest backup of a game. */
export function getLatestManifestMap(
  db: DatabaseSync,
  gameId: number,
): Map<string, { sha256: string; sizeBytes: number }> {
  const latest = getLatestBackup(db, gameId);
  const map = new Map<string, { sha256: string; sizeBytes: number }>();
  if (!latest) return map;
  const rows = allRows<BackupFileRow>(
    db.prepare('SELECT rel_path, sha256, size_bytes FROM backup_files WHERE backup_id = ?').all(latest.id),
  );
  for (const r of rows) map.set(r.rel_path, { sha256: r.sha256, sizeBytes: r.size_bytes });
  return map;
}

export function insertBackup(
  db: DatabaseSync,
  input: {
    gameId: number;
    label: string | null;
    fileCount: number;
    totalBytes: number;
    backupDir: string;
    notes: string | null;
    files: BackupFileEntry[];
  },
): Backup {
  const createdAt = new Date().toISOString();
  const insertBackupStmt = db.prepare(
    'INSERT INTO backups (game_id, created_at, label, file_count, total_bytes, backup_dir, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
  );
  const insertFileStmt = db.prepare(
    'INSERT INTO backup_files (backup_id, rel_path, sha256, size_bytes) VALUES (?, ?, ?, ?)',
  );
  // One transaction: the backup row and its manifest are atomic.
  // (node:sqlite has no transaction() helper — use explicit statements.)
  db.exec('BEGIN');
  try {
    const result = insertBackupStmt.run(
      input.gameId,
      createdAt,
      input.label,
      input.fileCount,
      input.totalBytes,
      input.backupDir,
      input.notes,
    );
    const backupId = Number(result.lastInsertRowid);
    for (const f of input.files) {
      insertFileStmt.run(backupId, f.relPath, f.sha256, f.sizeBytes);
    }
    db.exec('COMMIT');
    const backup = getBackup(db, backupId);
    if (!backup) throw new Error('Failed to read back inserted backup');
    return backup;
  } catch (err) {
    try {
      db.exec('ROLLBACK');
    } catch {
      // ignore secondary failure
    }
    throw err;
  }
}

export function countBackups(db: DatabaseSync, gameId: number): number {
  const row = db
    .prepare('SELECT COUNT(*) AS n FROM backups WHERE game_id = ?')
    .get(gameId) as { n: number };
  return row.n;
}
