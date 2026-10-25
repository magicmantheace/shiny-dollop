/**
 * User-data paths. The database and every backup live under Electron's
 * userData dir (per-user, per-OS location) — never in the repo.
 */
import { app } from 'electron';
import fs from 'node:fs';
import path from 'node:path';

export function getUserDataDir(): string {
  return app.getPath('userData');
}

/** <userData>/SaveManager/backups — created on demand. */
export function getBackupsRoot(userDataDir?: string): string {
  const root = path.join(userDataDir ?? getUserDataDir(), 'SaveManager', 'backups');
  fs.mkdirSync(root, { recursive: true });
  return root;
}
