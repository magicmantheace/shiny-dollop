import type { ActionKind, PetSummary } from './api-types.js';

/**
 * Auto-care decisions (owner-requested, 2026-11-05): while the
 * toggle is on, the desktop app itself keeps the pet out of trouble
 * — feeding, cleaning, playing, and medicating through the SAME
 * action dispatcher the panel and the phone use. This module is
 * only the pure decision: given a summary, which actions (if any)
 * are due. The main-process service performs them; the core sim
 * never knows auto-care exists, so determinism is untouched.
 *
 * Thresholds sit comfortably inside the sim's danger lines
 * (core constants): health only recovers while hunger > 25 and
 * cleanliness > 25, and sickness risk starts at cleanliness < 25
 * or 3+ messes — auto-care intervenes well before any of those.
 */
export const AUTO_CARE = {
  /** Feed a meal below this hunger. */
  hungerBelow: 40,
  /** Clean below this cleanliness, or at any mess. */
  cleanlinessBelow: 40,
  /** Play below this happiness… */
  happinessBelow: 35,
  /** …but never play a tired pet (play costs energy). */
  playMinEnergy: 25,
} as const;

export function autoCareActionsFor(s: PetSummary): ActionKind[] {
  // Eggs need nothing (and refuse care), the dead are beyond care,
  // and a sleeping pet is already recharging — it wakes on its own
  // at full energy, and core refuses most actions on it anyway.
  if (s.stage === 'egg' || s.stage === 'dead' || s.asleep) return [];
  const actions: ActionKind[] = [];
  if (s.sick) actions.push('medicine');
  if (s.needs.hunger < AUTO_CARE.hungerBelow) actions.push('feed-meal');
  if (s.messes >= 1 || s.needs.cleanliness < AUTO_CARE.cleanlinessBelow) {
    actions.push('clean');
  }
  if (
    s.needs.happiness < AUTO_CARE.happinessBelow &&
    s.needs.energy >= AUTO_CARE.playMinEnergy
  ) {
    actions.push('play');
  }
  return actions;
}
