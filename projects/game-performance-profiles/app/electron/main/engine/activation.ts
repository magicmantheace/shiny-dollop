/**
 * activateProfile — apply a profile's changes in order with automatic
 * rollback on failure.
 *
 * Protocol:
 * 1. Recompute the preview (fresh capability probe + current values).
 * 2. Skip unsupported/invalid changes — they are recorded as skipped and
 *    NEVER attempted against the OS.
 * 3. For each supported change: read `from`, apply, journal the entry with
 *    exact before/after, emit progress.
 * 4. On ANY failure: roll back every change applied in this activation in
 *    reverse order (journal `before` values), mark journal entries rolled
 *    back, and return { ok: false, applied, rolledBack, error }.
 */

import type {
  ActivationResult,
  Profile,
  SkippedChange,
} from '../../../shared/gpp-types.js';
import type { ProgressCallback as EngineProgress } from '../os-layer/types.js';
import { GppDatabase } from '../store/database.js';
import { OsLayer, describeDesired, describeTarget } from '../os-layer/types.js';
import { previewProfile, validateParams } from './preview.js';
import { CHANGE_KINDS } from '../../../shared/gpp-types.js';

export type ProgressFn = EngineProgress;

export interface ActivationDeps {
  db: GppDatabase;
  onProgress?: ProgressFn;
}

export async function activateProfile(
  profile: Profile,
  os: OsLayer,
  deps: ActivationDeps,
): Promise<ActivationResult> {
  const planned = await previewProfile(profile, os);
  const applied: string[] = [];
  const rolledBack: string[] = [];
  const skipped: SkippedChange[] = [];

  const total = planned.length;
  for (let i = 0; i < planned.length; i++) {
    const p = planned[i]!;
    if (!p.supported || !CHANGE_KINDS.includes(p.kind)) {
      skipped.push({
        changeId: p.changeId,
        kind: p.kind,
        target: p.target,
        reason: p.unsupportedReason ?? 'Unsupported change.',
      });
      continue;
    }
    // Re-validate params at activation time even though preview checked them.
    const params = profile.changes[i]!.params;
    const problem = validateParams(p.kind, params);
    if (problem) {
      skipped.push({ changeId: p.changeId, kind: p.kind, target: p.target, reason: problem });
      continue;
    }

    deps.onProgress?.({ changeId: p.changeId, kind: p.kind, target: p.target, index: i, total, phase: 'applying' });
    try {
      const before = await os.readCurrent(p.kind, params);
      await os.apply(p.kind, params);
      const after = describeDesired(p.kind, params);
      const entry = deps.db.addJournalEntry({
        profileId: profile.id,
        profileName: profile.name,
        changeKind: p.kind,
        target: describeTarget(p.kind, params),
        before,
        after,
      });
      applied.push(entry.id);
      deps.onProgress?.({ changeId: p.changeId, kind: p.kind, target: p.target, index: i, total, phase: 'applied' });
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      deps.onProgress?.({ changeId: p.changeId, kind: p.kind, target: p.target, index: i, total, phase: 'failed' });
      // Automatic rollback of everything applied in this activation, reverse order.
      const rollbackErrors: string[] = [];
      for (let j = applied.length - 1; j >= 0; j--) {
        const entryId = applied[j]!;
        const entry = deps.db.listJournal().find((x) => x.id === entryId)!;
        const changeParams = findParams(profile, entry);
        deps.onProgress?.({
          changeId: p.changeId, kind: entry.changeKind, target: entry.target,
          index: j, total, phase: 'rolling-back',
        });
        try {
          await os.restore(entry.changeKind, changeParams, entry.before);
          deps.db.markRolledBack(entryId);
          rolledBack.push(entryId);
          deps.onProgress?.({
            changeId: p.changeId, kind: entry.changeKind, target: entry.target,
            index: j, total, phase: 'rolled-back',
          });
        } catch (re) {
          rollbackErrors.push(`rollback of ${entry.target} failed: ${re instanceof Error ? re.message : String(re)}`);
        }
      }
      return {
        ok: false,
        applied,
        rolledBack,
        skipped,
        error:
          `Activation failed at change ${i + 1}/${total} (${p.kind} → ${p.target}): ${message}. ` +
          `Rolled back ${rolledBack.length}/${applied.length} applied change(s).` +
          (rollbackErrors.length ? ` Rollback errors: ${rollbackErrors.join('; ')}` : ''),
      };
    }
  }

  return { ok: true, applied, rolledBack, skipped };
}

/** Recover the original params for a journaled entry from the profile definition. */
function findParams(profile: Profile, entry: { changeKind: string; target: string }): Record<string, string> {
  const match = profile.changes.find(
    (c) => c.kind === entry.changeKind && describeTarget(c.kind, c.params) === entry.target,
  );
  return match?.params ?? {};
}
