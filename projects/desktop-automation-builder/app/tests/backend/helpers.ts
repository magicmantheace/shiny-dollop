// Shared fixture helpers for backend tests: a per-test temp directory and a
// fresh SQLite database. Real filesystem + real engine — no mocks.
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { openDatabase } from '../../electron/main/store.js';

export interface Fixture {
  root: string;
  sandbox: string;
  dbPath: string;
  db: DatabaseSync;
  cleanup(): void;
}

export function makeFixture(): Fixture {
  const root = mkdtempSync(join(tmpdir(), 'dab-test-'));
  const sandbox = join(root, 'sandbox');
  const dbPath = join(root, 'dab.sqlite');
  const db = openDatabase(dbPath);
  return {
    root,
    sandbox,
    dbPath,
    db,
    cleanup() {
      db.close();
      rmSync(root, { recursive: true, force: true });
    },
  };
}

export function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
