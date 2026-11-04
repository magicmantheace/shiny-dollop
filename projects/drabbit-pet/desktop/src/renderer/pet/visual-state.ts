import type { PetEvent } from 'drabbit-core';
import type { PetSummary } from '../../shared/api-types.js';

/**
 * Maps pet state → the pet window's animation state. Pure functions,
 * unit-tested headlessly (the GUI itself is owner-PC verification).
 */

export type PetAnimState =
  | 'egg'
  | 'egg-ready'
  | 'idle'
  | 'hopping'
  | 'sleeping'
  | 'eating'
  | 'playing'
  | 'sick'
  | 'dead';

/** The state implied by the pet summary alone. */
export function baseAnimState(s: PetSummary): PetAnimState {
  if (s.stage === 'egg') return s.readyToHatch ? 'egg-ready' : 'egg';
  if (s.stage === 'dead') return 'dead';
  if (s.asleep) return 'sleeping';
  if (s.sick) return 'sick';
  return 'idle';
}

export type TransientAnim = 'eating' | 'playing';

/** A just-happened care action briefly overrides the idle animation. */
export function transientFromEvents(events: readonly PetEvent[]): TransientAnim | null {
  for (const e of events) {
    if (e.kind === 'fed') return 'eating';
    if (e.kind === 'played') return 'playing';
  }
  return null;
}

/** Priority: base state (egg/dead/sleep/sick) > transient > hopping > idle. */
export function resolveAnimState(
  s: PetSummary,
  hopping: boolean,
  transient: TransientAnim | null,
): PetAnimState {
  const base = baseAnimState(s);
  if (base !== 'idle') return base;
  if (transient) return transient;
  if (hopping) return 'hopping';
  return 'idle';
}
