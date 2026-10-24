/**
 * SQLite database lifecycle for the main process: per-user location,
 * pragmas, and migrations. Uses node:sqlite (DatabaseSync) — zero native
 * builds, provided by Node 22+ and the Electron runtime.
 *
 * DB file:      <userData>/inventory.db
 * Attachments:  <userData>/attachments/
 *
 * NOTE: this module imports 'electron', so backend tests must NOT import it.
 * Tests construct DatabaseSync directly and call runMigrations themselves.
 */
import { DatabaseSync } from 'node:sqlite';
import { app } from 'electron';
import fs from 'node:fs';
import path from 'node:path';
import { runMigrations } from './migrations';
import { ATTACHMENTS_DIR_NAME, DB_FILE_NAME } from './paths';

export { ATTACHMENTS_DIR_NAME, DB_FILE_NAME };

export function getUserDataDir(): string {
  return app.getPath('userData');
}

export function getDatabasePath(userDataDir?: string): string {
  return path.join(userDataDir ?? getUserDataDir(), DB_FILE_NAME);
}

/** App-owned directory for attachment file bytes. Created on demand. */
export function getAttachmentsDir(userDataDir?: string): string {
  const dir = path.join(userDataDir ?? getUserDataDir(), ATTACHMENTS_DIR_NAME);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

/**
 * Open (or create) the database and apply pending migrations.
 * Pass an explicit userDataDir for an isolated location.
 * The database file is never committed (see .gitignore: *.db*).
 */
export function openDatabase(userDataDir?: string): DatabaseSync {
  const target = getDatabasePath(userDataDir);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const db = new DatabaseSync(target);
  db.exec('PRAGMA journal_mode = WAL;');
  db.exec('PRAGMA foreign_keys = ON;');
  db.exec('PRAGMA busy_timeout = 5000;');
  runMigrations(db);
  return db;
}

/** Close a database opened with openDatabase. Reopen with openDatabase(). */
export function closeDatabase(db: DatabaseSync): void {
  db.close();
}
