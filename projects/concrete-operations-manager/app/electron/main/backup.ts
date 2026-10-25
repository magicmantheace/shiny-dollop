/**
 * Backup (export whole DB to a file) and restore (validated replace).
 *
 * Backup: checkpoint WAL, then copy the database file.
 * Restore: validate the candidate (real SQLite file, expected tables,
 * schema_migrations at a compatible version), keep a rollback copy of the
 * current DB, then replace it. The caller must reopen the database after
 * a successful restore.
 */
import type { DatabaseSync } from 'node:sqlite';
import { DatabaseSync as DB } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';
import { OpsError, OpsErrorCodes } from './errors';
import { latestMigrationVersion } from './db/migrations';

const REQUIRED_TABLES = [
  'customers',
  'jobs',
  'pours',
  'quotes',
  'invoices',
  'tax_rates',
  'inventory_materials',
  'inventory_receipts',
  'inventory_consumption',
  'audit_trail',
  'app_settings',
  'calibration_profiles',
  'schema_migrations',
];

/** Copy the live database file to destPath (WAL checkpoint first). */
export function backupDatabase(db: DatabaseSync, sourcePath: string, destPath: string): string {
  try {
    db.exec('PRAGMA wal_checkpoint(TRUNCATE);');
  } catch {
    // Non-fatal: a plain file copy still works, just may lag by the WAL.
  }
  try {
    fs.mkdirSync(path.dirname(destPath), { recursive: true });
    fs.copyFileSync(sourcePath, destPath);
  } catch (err) {
    throw new OpsError(
      OpsErrorCodes.IO_ERROR,
      `Backup failed: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
  return destPath;
}

/** Validate that candidatePath is a restorable ConcreteOps database. */
export function validateRestoreCandidate(candidatePath: string): { version: number } {
  let stat: fs.Stats;
  try {
    stat = fs.statSync(candidatePath);
  } catch {
    throw new OpsError(OpsErrorCodes.RESTORE_INVALID, 'Restore file does not exist or is unreadable.');
  }
  if (!stat.isFile() || stat.size === 0) {
    throw new OpsError(OpsErrorCodes.RESTORE_INVALID, 'Restore file is empty or not a file.');
  }
  if (stat.size > 512 * 1024 * 1024) {
    throw new OpsError(OpsErrorCodes.RESTORE_INVALID, 'Restore file is implausibly large (>512 MB).');
  }
  let probe: DB | null = null;
  try {
    probe = new DB(candidatePath, { readOnly: true });
    const tables = (
      probe.prepare("SELECT name FROM sqlite_master WHERE type = 'table'").all() as { name: string }[]
    ).map((t) => t.name);
    const missing = REQUIRED_TABLES.filter((t) => !tables.includes(t));
    if (missing.length > 0) {
      throw new OpsError(
        OpsErrorCodes.RESTORE_INVALID,
        `Not a Concrete Operations database: missing tables ${missing.join(', ')}.`,
      );
    }
    const versions = probe.prepare('SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1').all() as {
      version: number;
    }[];
    const version = versions[0]?.version ?? 0;
    if (version > latestMigrationVersion()) {
      throw new OpsError(
        OpsErrorCodes.RESTORE_INVALID,
        `Backup uses schema version ${version}, newer than this app supports (${latestMigrationVersion()}).`,
      );
    }
    return { version };
  } catch (err) {
    if (err instanceof OpsError) throw err;
    throw new OpsError(
      OpsErrorCodes.RESTORE_INVALID,
      `Not a valid SQLite database: ${err instanceof Error ? err.message : String(err)}`,
    );
  } finally {
    try {
      probe?.close();
    } catch {
      // ignore
    }
  }
}

export interface RestoreResult {
  /** Rollback copy of the pre-restore database. */
  rollbackPath: string;
}

/**
 * Replace the live database file with a validated candidate. The caller
 * must close the current connection first and reopen afterwards.
 */
export function restoreDatabase(
  livePath: string,
  candidatePath: string,
  rollbackDir: string,
): RestoreResult {
  validateRestoreCandidate(candidatePath);
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const rollbackPath = path.join(rollbackDir, `concrete-ops.pre-restore-${stamp}.db`);
  try {
    fs.mkdirSync(rollbackDir, { recursive: true });
    if (fs.existsSync(livePath)) {
      fs.copyFileSync(livePath, rollbackPath);
    }
    fs.copyFileSync(candidatePath, livePath);
  } catch (err) {
    throw new OpsError(
      OpsErrorCodes.IO_ERROR,
      `Restore failed: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
  return { rollbackPath };
}
