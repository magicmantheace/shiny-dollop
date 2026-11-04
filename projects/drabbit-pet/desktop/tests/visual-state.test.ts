import { describe, expect, it } from 'vitest';
import type { PetEvent } from 'drabbit-core';
import type { PetSummary } from '../src/shared/api-types.js';
import {
  baseAnimState,
  resolveAnimState,
  transientFromEvents,
} from '../src/renderer/pet/visual-state.js';

function summary(over: Partial<PetSummary> = {}): PetSummary {
  return {
    id: 'x',
    name: 'Pip',
    fur: 'royal',
    stage: 'adult',
    adultForm: 'content',
    mood: 'content',
    needs: { hunger: 80, happiness: 80, energy: 90, cleanliness: 90 },
    health: 100,
    careScore: 70,
    ageMs: 20 * 60 * 60 * 1000,
    asleep: false,
    sick: false,
    messes: 0,
    readyToHatch: false,
    generation: 1,
    deathCause: null,
    ...over,
  };
}

const ev = (kind: string): PetEvent => ({ t: 0, kind, detail: '' });

describe('baseAnimState', () => {
  it('maps stages and conditions', () => {
    expect(baseAnimState(summary({ stage: 'egg' }))).toBe('egg');
    expect(baseAnimState(summary({ stage: 'egg', readyToHatch: true }))).toBe('egg-ready');
    expect(baseAnimState(summary({ stage: 'dead' }))).toBe('dead');
    expect(baseAnimState(summary({ asleep: true }))).toBe('sleeping');
    expect(baseAnimState(summary({ sick: true }))).toBe('sick');
    expect(baseAnimState(summary())).toBe('idle');
  });

  it('prioritises sleep over sickness (a sleeping sick pet breathes, not droops)', () => {
    expect(baseAnimState(summary({ asleep: true, sick: true }))).toBe('sleeping');
  });
});

describe('transientFromEvents', () => {
  it('maps fed/played events to brief animations', () => {
    expect(transientFromEvents([ev('fed')])).toBe('eating');
    expect(transientFromEvents([ev('played')])).toBe('playing');
    expect(transientFromEvents([ev('mess'), ev('stage')])).toBeNull();
    expect(transientFromEvents([])).toBeNull();
  });
});

describe('resolveAnimState', () => {
  it('base state beats transient and hopping', () => {
    expect(resolveAnimState(summary({ sick: true }), true, 'eating')).toBe('sick');
    expect(resolveAnimState(summary({ asleep: true }), true, 'playing')).toBe('sleeping');
    expect(resolveAnimState(summary({ stage: 'egg' }), true, null)).toBe('egg');
  });

  it('transient beats hopping, hopping beats idle', () => {
    expect(resolveAnimState(summary(), true, 'eating')).toBe('eating');
    expect(resolveAnimState(summary(), true, null)).toBe('hopping');
    expect(resolveAnimState(summary(), false, null)).toBe('idle');
  });
});
