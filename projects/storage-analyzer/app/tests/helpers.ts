/**
 * Test fixtures. Everything lives in :memory: SQLite databases or under
 * os.tmpdir() and is cleaned up after each test — synthetic data only.
 * Never the owner's real data.
 */
import { DatabaseSync } from 'node:sqlite';
import type { DatabaseSync as DatabaseSyncType } from 'node:sqlite';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { runMigrations } from '../electron/main/db/migrations';

export function makeTestDb(): DatabaseSyncType {
  const db = new DatabaseSync(':memory:');
  runMigrations(db);
  return db;
}

export function makeFixtureDir(prefix = 'sa-test-'): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

export function rmDir(dir: string): void {
  fs.rmSync(dir, { recursive: true, force: true });
}

export function writeFixture(filePath: string, content: string | Buffer): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
}

/** sha256 of a file's current contents (for the zero-writes test). */
export function fileDigest(filePath: string): string {
  return createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

export interface TreeSnapshot {
  files: string[];
  digests: Map<string, string>;
  mtimes: Map<string, number>;
}

/** Snapshot every regular file under root: digest + mtime. */
export function snapshotTree(root: string): TreeSnapshot {
  const files: string[] = [];
  const digests = new Map<string, string>();
  const mtimes = new Map<string, number>();
  const stack = [root];
  while (stack.length > 0) {
    const dir = stack.pop() as string;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) {
        stack.push(full);
      } else if (entry.isFile()) {
        files.push(full);
        digests.set(full, fileDigest(full));
        mtimes.set(full, fs.statSync(full).mtimeMs);
      }
    }
  }
  return { files, digests, mtimes };
}
