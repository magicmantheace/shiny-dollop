import { describe, expect, it } from 'vitest';
import {
  formatSpec,
  parseDiceNotation,
  replayRoll,
  rollFromState,
  rollNotation,
} from '../../shared/dice.js';
import { isAidmError } from '../../shared/errors.js';
import { hashSeed, streamFromSeed } from '../../shared/prng.js';

describe('dice notation parsing', () => {
  it('parses NdM, NdM+K, NdM-K and bare dM', () => {
    expect(parseDiceNotation('2d6')).toEqual({ count: 2, sides: 6, modifier: 0 });
    expect(parseDiceNotation('2d6+3')).toEqual({ count: 2, sides: 6, modifier: 3 });
    expect(parseDiceNotation('3d8-1')).toEqual({ count: 3, sides: 8, modifier: -1 });
    expect(parseDiceNotation('d20')).toEqual({ count: 1, sides: 20, modifier: 0 });
    expect(formatSpec(parseDiceNotation(' 2D6 + 3 '))).toBe('2d6+3');
  });

  it('rejects bad notation with DICE_NOTATION_INVALID', () => {
    for (const bad of ['', 'hello', '2x6', 'd1', '0d6', '101d6', '2d1001', '2d6+1001', '2d', '-2d6']) {
      try {
        parseDiceNotation(bad);
        expect.unreachable(`expected ${bad} to be rejected`);
      } catch (err) {
        expect(isAidmError(err) && err.code === 'DICE_NOTATION_INVALID').toBe(true);
      }
    }
  });
});

describe('deterministic dice stream', () => {
  it('produces identical sequences from the same seed state', () => {
    const start = hashSeed('audit-seed');
    const run = (): number[] => {
      let state = start;
      const totals: number[] = [];
      for (let i = 0; i < 10; i++) {
        const outcome = rollNotation('2d6+1', state);
        totals.push(outcome.total);
        state = outcome.stateAfter;
      }
      return totals;
    };
    expect(run()).toEqual(run());
  });

  it('every recorded roll replays exactly from its stateBefore', () => {
    let state = hashSeed('replay-seed');
    for (const notation of ['1d20', '2d6', '3d8-2', '1d4+4', '5d10']) {
      const outcome = rollNotation(notation, state);
      expect(replayRoll(outcome)).toBe(true);
      state = outcome.stateAfter;
    }
  });

  it('keeps dice within bounds over many draws', () => {
    const stream = streamFromSeed('bounds-seed');
    for (let i = 0; i < 500; i++) {
      const outcome = rollFromState({ count: 3, sides: 6, modifier: 0 }, 0);
      void outcome;
      const v = stream.next();
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
    let state = hashSeed('bounds-2');
    for (let i = 0; i < 200; i++) {
      const outcome = rollNotation('3d6', state);
      for (const die of outcome.dice) {
        expect(die).toBeGreaterThanOrEqual(1);
        expect(die).toBeLessThanOrEqual(6);
      }
      expect(outcome.total).toBeGreaterThanOrEqual(3);
      expect(outcome.total).toBeLessThanOrEqual(18);
      state = outcome.stateAfter;
    }
  });

  it('different seeds give different streams (sanity, fixed seeds)', () => {
    const a = rollNotation('2d6', hashSeed('seed-a'));
    const b = rollNotation('2d6', hashSeed('seed-b'));
    expect(a.stateAfter).not.toBe(b.stateAfter);
  });
});
