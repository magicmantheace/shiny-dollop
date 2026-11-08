/**
 * Test fixtures. Everything lives in :memory: SQLite databases or under
 * os.tmpdir() and is cleaned up after each test — synthetic data only.
 */
import type { DatabaseSync } from 'node:sqlite';
import { DatabaseSync as DB } from 'node:sqlite';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { runMigrations } from '../electron/main/db/migrations';
import { addCustomer } from '../electron/main/db/customers';
import { addJob } from '../electron/main/db/jobs';
import { addPour } from '../electron/main/db/pours';
import type { Customer, Job, Pour } from '../shared/types';

export function makeTestDb(): DatabaseSync {
  const db = new DB(':memory:');
  db.exec('PRAGMA foreign_keys = ON;');
  runMigrations(db);
  return db;
}

/** A real on-disk database (for persistence / backup tests). */
export function makeFileDb(): { db: DatabaseSync; dbPath: string; dir: string } {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'com-test-'));
  const dbPath = path.join(dir, 'test.db');
  const db = new DB(dbPath);
  db.exec('PRAGMA journal_mode = WAL;');
  db.exec('PRAGMA foreign_keys = ON;');
  runMigrations(db);
  return { db, dbPath, dir };
}

export function cleanupDir(dir: string): void {
  fs.rmSync(dir, { recursive: true, force: true });
}

export function addTestCustomer(db: DatabaseSync, name = 'Synthetic Test Customer'): Customer {
  return addCustomer(db, { name });
}

export function addTestJob(db: DatabaseSync, customerId: number): Job {
  return addJob(db, {
    customerId,
    jobDate: '2026-10-23',
    deliveryLocation: '1234 Test Road, Lethbridge AB',
    poNumber: 'PO-TEST-001',
  });
}

export function addTestPour(db: DatabaseSync, jobId: number, quotedLiters = 2500): Pour {
  return addPour(db, { jobId, mixDesignId: 'C25/30', quotedLiters });
}
