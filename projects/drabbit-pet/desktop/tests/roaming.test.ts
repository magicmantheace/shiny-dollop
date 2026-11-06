import { describe, expect, it } from 'vitest';
import { RoamPlanner, type RoamBounds, type RoamContext } from '../src/main/roaming.js';
import { scriptedRand } from './helpers.js';

const BOUNDS: RoamBounds = { minX: 0, maxX: 1000 };
const FREE: RoamContext = { stage: 'adult', asleep: false, panelOpen: false, paused: false };

describe('RoamPlanner', () => {
  it('never moves while asleep, panel-open, paused, an egg, or dead', () => {
    const blocked: RoamContext[] = [
      { ...FREE, asleep: true },
      { ...FREE, panelOpen: true },
      { ...FREE, paused: true },
      { ...FREE, stage: 'egg' },
      { ...FREE, stage: 'dead' },
    ];
    for (const ctx of blocked) {
      // rand 0.99 would choose to hop if it were allowed to decide.
      const planner = new RoamPlanner(() => 0.99);
      for (let i = 0; i < 50; i++) {
        const step = planner.step(500, BOUNDS, ctx);
        expect(step).toEqual({ x: 500, hopping: false });
      }
    }
  });

  it('stays within bounds under adversarial randomness', () => {
    // Always hop right, as far as possible.
    const right = new RoamPlanner(() => 0.99);
    let x = 990;
    for (let i = 0; i < 100; i++) {
      x = right.step(x, BOUNDS, FREE).x;
      expect(x).toBeGreaterThanOrEqual(BOUNDS.minX);
      expect(x).toBeLessThanOrEqual(BOUNDS.maxX);
    }
    expect(x).toBe(BOUNDS.maxX);

    // Scripted: hop decision (≥0.55), direction left (<0.5), max distance.
    const left = new RoamPlanner(scriptedRand([0.9, 0.1, 0.99], 0.99));
    x = 10;
    for (let i = 0; i < 100; i++) {
      x = left.step(x, BOUNDS, FREE).x;
      expect(x).toBeGreaterThanOrEqual(BOUNDS.minX);
      expect(x).toBeLessThanOrEqual(BOUNDS.maxX);
    }
    expect(x).toBe(BOUNDS.minX);
  });

  it('clamps an out-of-bounds start position', () => {
    const planner = new RoamPlanner(() => 0.99);
    expect(planner.step(-50, BOUNDS, { ...FREE, asleep: true }).x).toBe(0);
    expect(planner.step(5000, BOUNDS, { ...FREE, asleep: true }).x).toBe(1000);
  });

  it('hops toward a chosen target, arrives, then sits', () => {
    // decide hop (0.9), direction right (0.9 → +1), distance 150 (0.5)
    const planner = new RoamPlanner(scriptedRand([0.9, 0.9, 0.5], 0.5));
    const first = planner.step(500, BOUNDS, FREE);
    expect(first.hopping).toBe(true);
    expect(first.x).toBe(507);

    let x = first.x;
    let hopping = true;
    for (let i = 0; i < 60 && hopping; i++) {
      const step = planner.step(x, BOUNDS, FREE);
      x = step.x;
      hopping = step.hopping;
    }
    expect(x).toBe(650); // exactly the chosen target
    // After arrival it sits: further steps don't move.
    for (let i = 0; i < 10; i++) {
      expect(planner.step(x, BOUNDS, FREE)).toEqual({ x: 650, hopping: false });
    }
  });

  it('usually sits when given the choice (long idle sits)', () => {
    const planner = new RoamPlanner(() => 0.1); // < SIT_CHANCE → sit
    for (let i = 0; i < 20; i++) {
      expect(planner.step(500, BOUNDS, FREE)).toEqual({ x: 500, hopping: false });
    }
  });
});
