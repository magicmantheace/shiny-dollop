/**
 * First-run seeding: one low-risk built-in profile, "Balanced Gaming".
 *
 * - game-mode on (reversible registry DWORD, low risk).
 * - power-plan with an EMPTY guid placeholder. The user must pick a real
 *   power plan in the UI; preview marks the change unsupported until then and
 *   activation refuses to apply it.
 */

import type { ChangeSpec } from '../../shared/gpp-types.js';
import { GppDatabase } from './store/database.js';

export const SEED_PROFILE_NAME = 'Balanced Gaming';

export function seedProfile(db: GppDatabase): boolean {
  if (db.listProfiles().length > 0) return false;
  const changes: ChangeSpec[] = [
    { kind: 'game-mode', params: { enabled: 'true' } },
    { kind: 'power-plan', params: { guid: '' } },
  ];
  db.createProfile(SEED_PROFILE_NAME, changes);
  return true;
}
