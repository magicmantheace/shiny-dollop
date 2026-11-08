/**
 * User-data paths. The database and every export live under Electron's
 * userData dir (per-user, per-OS location) — never in the repo.
 */
import { app } from 'electron';
import fs from 'node:fs';
import path from 'node:path';

export function getUserDataDir(): string {
  return app.getPath('userData');
}

/** <userData>/ConcreteOps/exports — created on demand. */
export function getExportsRoot(userDataDir?: string): string {
  const root = path.join(userDataDir ?? getUserDataDir(), 'ConcreteOps', 'exports');
  fs.mkdirSync(root, { recursive: true });
  return root;
}
