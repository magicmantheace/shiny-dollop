/** SQLite database lifecycle: per-user location, pragmas, migrations. */
import { DatabaseSync } from 'node:sqlite';
import { app } from 'electron';
import fs from 'node:fs';
import path from 'node:path';
import { runMigrations } from './migrations';

export function getDatabaseDir(): string {
  const dir = path.join(app.getPath('userData'), 'data');
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export function getDatabasePath(): string {
  return path.join(getDatabaseDir(), 'library.db');
}

/**
 * Open (or create) the library database and apply pending migrations.
 * Pass ':memory:' in tests for an isolated database.
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
