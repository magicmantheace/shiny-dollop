// Transparent dice engine.
//
// Notation: NdM, NdM+K, NdM-K, dM (= 1dM). Examples: "2d6+3", "1d20",
// "3d8-1". Every roll is a pure function of (notation, stream state):
// the result records each individual die, the modifier, the total, and
// the stream states before/after, so any roll stored in a session log
// can be replayed exactly by re-running the stream from stateBefore.

import { AIDM_ERROR_CODES, aidmError } from './errors.js';
import { prngStep } from './prng.js';

export interface DiceSpec {
  count: number;
  sides: number;
  modifier: number;
}

export interface RollOutcome {
  notation: string;
  spec: DiceSpec;
  /** Individual die results, in draw order. */
  dice: number[];
  modifier: number;
  total: number;
  /** PRNG state before the first draw. */
  stateBefore: number;
  /** PRNG state after the last draw; the next roll continues from here. */
  stateAfter: number;
}

const NOTATION_RE = /^\s*(\d*)\s*d\s*(\d+)\s*(?:([+-])\s*(\d+))?\s*$/i;

export const MAX_DICE = 100;
export const MAX_SIDES = 1000;
export const MAX_MODIFIER = 1000;

export function parseDiceNotation(input: string): DiceSpec {
  if (typeof input !== 'string' || input.trim().length === 0) {
    throw aidmError(
      AIDM_ERROR_CODES.DICE_NOTATION_INVALID,
      'Dice notation is empty. Use forms like "2d6+3" or "1d20".',
    );
  }
  const match = NOTATION_RE.exec(input);
  if (!match) {
    throw aidmError(
      AIDM_ERROR_CODES.DICE_NOTATION_INVALID,
      `"${input}" is not valid dice notation. Use forms like "2d6+3" or "1d20".`,
    );
  }
  const count = match[1] === '' || match[1] === undefined ? 1 : Number(match[1]);
  const sides = Number(match[2]);
  const sign = match[3] === '-' ? -1 : 1;
  const modifier = match[4] === undefined ? 0 : sign * Number(match[4]);
  if (!Number.isInteger(count) || count < 1 || count > MAX_DICE) {
    throw aidmError(
      AIDM_ERROR_CODES.DICE_NOTATION_INVALID,
      `Dice count must be between 1 and ${MAX_DICE}.`,
    );
  }
  if (!Number.isInteger(sides) || sides < 2 || sides > MAX_SIDES) {
    throw aidmError(
      AIDM_ERROR_CODES.DICE_NOTATION_INVALID,
      `Die size must be between 2 and ${MAX_SIDES}.`,
    );
  }
  if (!Number.isInteger(modifier) || Math.abs(modifier) > MAX_MODIFIER) {
    throw aidmError(
      AIDM_ERROR_CODES.DICE_NOTATION_INVALID,
      `Modifier must be between -${MAX_MODIFIER} and +${MAX_MODIFIER}.`,
    );
  }
  return { count, sides, modifier };
}

export function formatSpec(spec: DiceSpec): string {
  const base = `${spec.count}d${spec.sides}`;
  if (spec.modifier > 0) return `${base}+${spec.modifier}`;
  if (spec.modifier < 0) return `${base}${spec.modifier}`;
  return base;
}

/** Roll a spec against an explicit stream state. Pure and replayable. */
export function rollFromState(spec: DiceSpec, stateBefore: number): RollOutcome {
  let state = stateBefore >>> 0;
  const dice: number[] = [];
  for (let i = 0; i < spec.count; i++) {
    const step = prngStep(state);
    state = step.state;
    dice.push(1 + Math.floor(step.value * spec.sides));
  }
  const total = dice.reduce((sum, d) => sum + d, 0) + spec.modifier;
  return {
    notation: formatSpec(spec),
    spec,
    dice,
    modifier: spec.modifier,
    total,
    stateBefore: stateBefore >>> 0,
    stateAfter: state,
  };
}

export function rollNotation(notation: string, stateBefore: number): RollOutcome {
  return rollFromState(parseDiceNotation(notation), stateBefore);
}

/**
 * Replay a recorded roll: re-running the stream from its recorded
 * stateBefore must reproduce the same dice and total. Used by tests and
 * by anyone auditing the session log.
 */
export function replayRoll(outcome: RollOutcome): boolean {
  const again = rollFromState(outcome.spec, outcome.stateBefore);
  return (
    again.total === outcome.total &&
    again.stateAfter === outcome.stateAfter &&
    again.dice.length === outcome.dice.length &&
    again.dice.every((d, i) => d === outcome.dice[i])
  );
}
