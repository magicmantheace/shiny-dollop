/**
 * rollbackProfile — restore a profile's un-rolled-back journal entries,
 * newest first. restoreAll — roll back every un-rolled-back entry,
 * newest first. Both are best-effort: each entry is attempted, failures are
 * collected in `errors`, and only successful restores are marked rolled back.
 *
 * Out-of-order rollback over a shared setting: if a NEWER entry from
 * another profile is still live for the same OS setting, restoring this
 * entry's `before` would clobber the newer entry's live state — and the
 * newer entry's recorded baseline would then be wrong, so a later
 * restore-all could not recover the original value even though every
 * entry shows rolled back. Instead the entry is retired WITHOUT touching
 * the OS (the live state is exactly the newer chain's result either way:
 * applies set absolute values) and the immediate surviving successor's
 * `before` is rebased to this entry's `before`, splicing this entry out
 * of the history chain.
 *
 * Dependent history after a restore failure: entries are restored
 * newest first, so a chain for one setting is unwound step by step. If
 * restoring a newer entry FAILS, that entry stays live and its `before`
 * is still the value the chain must pass through. Restoring (or
 * splicing out) an OLDER entry for the same setting anyway would jump
 * straight to the older baseline and retire the older entry, leaving
 * the failed entry's `before` pointing at a state that no longer
 * exists in the remaining history — a second restore-all would then
 * "restore" the failed entry to that stale intermediate value and lose
 * the original state (e.g. Game Mode originally disabled ends up
 * enabled). So once a restore fails for a setting, every older entry
 * for the SAME setting in this run is skipped and left un-rolled-back
 * for a later retry, while entries for independent settings still
 * restore normally.
 */

import type { JournalEntry, RollbackResult, RestoreAllResult } from '../../../shared/gpp-types.js';
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
  const ownIds = new Set(entries.map((e) => e.id));
  const profile = getProfile?.(profileId);
  const rolledBack: string[] = [];
  const errors: string[] = [];
  /** Settings whose newer entry failed to restore in this run. */
  const failedKeys = new Set<string>();

  for (const entry of entries) {
    const entryKey = overlapKey(entry, getProfile);
    if (failedKeys.has(entryKey)) {
      errors.push(
        `Skipped rolling back ${entry.target}: a newer entry for the same setting could not be restored, so this entry was left in place to preserve the rollback history.`,
      );
      continue;
    }
    try {
      const params = profile ? findParams(profile, entry) : {};
      // Re-read the live journal each iteration: entries retired earlier in
      // this loop (including rebased successors) must be reflected here.
      const allUnrolled = db.listUnrolledBack(); // newest first
      const idx = allUnrolled.findIndex((e) => e.id === entry.id);
      const key = overlapKey(entry, getProfile);
      const newerOverlapping =
        idx >= 0
          ? allUnrolled
              .slice(0, idx)
              .filter((e) => !ownIds.has(e.id) && overlapKey(e, getProfile) === key)
          : [];
      if (newerOverlapping.length > 0) {
        // Splice this entry out of the chain: the immediate successor
        // (oldest of the newer overlapping entries) inherits its baseline.
        const successor = newerOverlapping[newerOverlapping.length - 1]!;
        db.updateJournalBefore(successor.id, entry.before);
        db.markRolledBack(entry.id);
        rolledBack.push(entry.id);
        continue;
      }
      await os.restore(entry.changeKind, params, entry.before);
      db.markRolledBack(entry.id);
      rolledBack.push(entry.id);
    } catch (e) {
      failedKeys.add(entryKey);
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
  /** Settings whose newer entry failed to restore in this run. */
  const failedKeys = new Set<string>();

  for (const entry of entries) {
    const key = overlapKey(entry, getProfile);
    if (failedKeys.has(key)) {
      errors.push(
        `Skipped restoring ${entry.target}: a newer entry for the same setting could not be restored, so this entry was left in place to preserve the rollback history.`,
      );
      continue;
    }
    try {
      const profile = getProfile?.(entry.profileId);
      const params = profile ? findParams(profile, entry) : {};
      await os.restore(entry.changeKind, params, entry.before);
      db.markRolledBack(entry.id);
      rolledBack.push(entry.id);
    } catch (e) {
      failedKeys.add(key);
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

/**
 * Identity of the underlying OS setting a journal entry changes. Game Mode
 * and the active power plan are machine-wide singletons; process priority
 * is per executable image; fullscreen optimizations are per game key.
 * Falls back to kind+target when the owning profile (and its params) is
 * gone.
 */
function overlapKey(
  entry: JournalEntry,
  getProfile?: (id: string) => Profile | undefined,
): string {
  const profile = getProfile?.(entry.profileId);
  const params = profile ? findParams(profile, entry) : {};
  switch (entry.changeKind) {
    case 'process-priority': {
      const image = (params['imageName'] ?? '').trim().toLowerCase();
      return image ? `process-priority|${image}` : `process-priority|${entry.target}`;
    }
    case 'fullscreen-optimizations': {
      const key = (params['childKey'] ?? '').trim();
      return key
        ? `fullscreen-optimizations|${key}`
        : `fullscreen-optimizations|${entry.target}`;
    }
    default:
      return entry.changeKind;
  }
}
