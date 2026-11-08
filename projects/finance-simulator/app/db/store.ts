/**
 * SQLite database lifecycle for the main process: per-user location,
 * pragmas, and migrations. Uses node:sqlite (DatabaseSync) — zero native
 * builds, provided by Node 22+ and the Electron runtime.
 *
 * NOTE: this module imports 'electron', so backend tests must NOT import it.
 * Tests construct DatabaseSync directly and call runMigrations themselves.
 */
import { DatabaseSync } from 'node:sqlite';
import { app } from 'electron';
import fs from 'node:fs';
import path from 'node:path';
import { runMigrations } from './migrations';

export function getDatabaseDir(): string {
  const dir = path.join(app.getPath('userData'), 'FinanceSimulator', 'data');
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export function getDatabasePath(): string {
  return path.join(getDatabaseDir(), 'finance-simulator.db');
}

/**
 * Open (or create) the database and apply pending migrations.
 * Pass an explicit path for an isolated database (':memory:' works).
 * The database file is never committed (see .gitignore: *.db*).
 */
export function openDatabase(dbPath?: string): DatabaseSync {
  const target = dbPath ?? getDatabasePath();
  if (target !== ':memory:') {
    fs.mkdirSync(path.dirname(target), { recursive: true });
  }
  const db = new DatabaseSync(target);
  db.exec('PRAGMA journal_mode = WAL;');
  db.exec('PRAGMA foreign_keys = ON;');
  db.exec('PRAGMA busy_timeout = 5000;');
  runMigrations(db);
  return db;
}
