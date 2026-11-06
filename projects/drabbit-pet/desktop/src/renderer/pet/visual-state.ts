import type { PetEvent } from 'drabbit-core';
import type { PetSummary } from '../../shared/api-types.js';
import type { BridgeReactionKind } from '../../shared/bridge-reaction.js';

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
  | 'cleaning'
  | 'healing'
  | 'hatching'
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

export type TransientAnim =
  | 'eating'
  | 'playing'
  | 'cleaning'
  | 'healing'
  | 'hatching';

/**
 * A just-happened care action briefly overrides the idle animation.
 * Priority is by kind, not event order — a hatch outranks everything
 * in its batch, a cure outranks a feeding, and so on.
 */
export function transientFromEvents(events: readonly PetEvent[]): TransientAnim | null {
  const kinds = new Set(events.map((e) => e.kind));
  if (kinds.has('hatched')) return 'hatching';
  if (kinds.has('cured')) return 'healing';
  if (kinds.has('cleaned')) return 'cleaning';
  if (kinds.has('fed') || kinds.has('overfed')) return 'eating';
  if (kinds.has('played')) return 'playing';
  return null;
}

/**
 * Bridge reactions are mostly a bubble line, not a body animation —
 * only a successful bridge update earns the happy bounce.
 */
export function bridgeTransientFor(kind: BridgeReactionKind): TransientAnim | null {
  return kind === 'celebrate' ? 'playing' : null;
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
