/**
 * rollbackProfile — restore a profile's un-rolled-back journal entries,
 * newest first. restoreAll — roll back every un-rolled-back entry,
 * newest first. Both are best-effort: each entry is attempted, failures are
 * collected in `errors`, and only successful restores are marked rolled back.
 */

import type { RollbackResult, RestoreAllResult } from '../../../shared/gpp-types.js';
import { GppDatabase } from '../store/database.js';
import { OsLayer } from '../os-layer/types.js';
import { describeTarget } from '../os-layer/types.js';
import type { Profile } from '../../../shared/gpp-types.js';

export async function rollbackProfile(
  profileId: string,
  os: OsLayer,
  db: GppDatabase,
  /** Optional profile lookup so restore() gets the original params. */
  getProfile?: (id: string) => Profile | undefined,
): Promise<RollbackResult> {
  const entries = db.listUnrolledBack(profileId);
  const profile = getProfile?.(profileId);
  const rolledBack: string[] = [];
  const errors: string[] = [];

  for (const entry of entries) {
    try {
      const params = profile ? findParams(profile, entry) : {};
      await os.restore(entry.changeKind, params, entry.before);
      db.markRolledBack(entry.id);
      rolledBack.push(entry.id);
    } catch (e) {
      errors.push(`Could not roll back ${entry.target}: ${e instanceof Error ? e.message : String(e)}`);
    }
  }
  return { ok: errors.length === 0, rolledBack, errors };
}

export async function restoreAll(
  os: OsLayer,
  db: GppDatabase,
  getProfile?: (id: string) => Profile | undefined,
): Promise<RestoreAllResult> {
  const entries = db.listUnrolledBack();
  const rolledBack: string[] = [];
  const errors: string[] = [];

  for (const entry of entries) {
    try {
      const profile = getProfile?.(entry.profileId);
      const params = profile ? findParams(profile, entry) : {};
      await os.restore(entry.changeKind, params, entry.before);
      db.markRolledBack(entry.id);
      rolledBack.push(entry.id);
    } catch (e) {
      errors.push(`Could not restore ${entry.target}: ${e instanceof Error ? e.message : String(e)}`);
    }
  }
  return { ok: errors.length === 0, rolledBack, errors };
}

function findParams(profile: Profile, entry: { changeKind: string; target: string }): Record<string, string> {
  const match = profile.changes.find(
    (c) => c.kind === entry.changeKind && describeTarget(c.kind, c.params) === entry.target,
  );
  return match?.params ?? {};
}
