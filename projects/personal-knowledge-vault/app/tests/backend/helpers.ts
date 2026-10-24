/**
 * Test helper: fresh in-memory SQLite database with migrations applied.
 * Synthetic fixtures only — no owner data.
 */
import { DatabaseSync } from 'node:sqlite';
import { runMigrations } from '../../db/migrations';

export function makeDb(): DatabaseSync {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA foreign_keys = ON;');
  runMigrations(db);
  return db;
}
