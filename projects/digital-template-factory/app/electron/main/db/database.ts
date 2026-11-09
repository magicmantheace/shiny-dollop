/**
 * SQLite database lifecycle. Uses node:sqlite (DatabaseSync) — zero
 * native builds, provided by Node 22+ and the Electron runtime.
 * The database lives under the app's userData directory (gitignored).
 */
import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';
import { runMigrations } from './migrations';

/**
 * Open (or create) the template-factory database and apply pending
 * migrations. Callers pass an explicit path; tests use ':memory:'.
 */
export function openDatabase(dbPath: string): DatabaseSync {
  if (dbPath !== ':memory:') {
    fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  }
  const db = new DatabaseSync(dbPath);
  db.exec('PRAGMA journal_mode = WAL;');
  db.exec('PRAGMA foreign_keys = ON;');
  db.exec('PRAGMA busy_timeout = 5000;');
  runMigrations(db);
  return db;
}

/** Run `fn` inside an explicit transaction; rolls back on throw. */
export function withTransaction<T>(db: DatabaseSync, fn: () => T): T {
  db.exec('BEGIN IMMEDIATE');
  try {
    const result = fn();
    db.exec('COMMIT');
    return result;
  } catch (err) {
    try {
      db.exec('ROLLBACK');
    } catch {
      // rollback failure: surface the original error
    }
    throw err;
  }
}
