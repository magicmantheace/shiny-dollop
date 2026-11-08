/**
 * User-data paths. The database lives under Electron's userData dir
 * (per-user, per-OS location) — never in the repo.
 */
import { app } from 'electron';

export function getUserDataDir(): string {
  return app.getPath('userData');
}
