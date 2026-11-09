import { describe, expect, it } from 'vitest';
import { computePose, dampPose } from '../src/renderer/pet/pose-driver.js';
import type { PetAnimState } from '../src/renderer/pet/visual-state.js';

const STATES: PetAnimState[] = [
  'idle',
  'hopping',
  'eating',
  'playing',
  'sick',
  'sleeping',
];

describe('computePose', () => {
  it('returns finite poses for every 3D state across time', () => {
    for (const anim of STATES) {
      for (let t = 0; t < 5; t += 0.137) {
        const p = computePose(anim, t);
        for (const v of Object.values(p)) {
          expect(Number.isFinite(v)).toBe(true);
        }
      }
    }
  });

  it('sick folds the ears and bows the head far past idle', () => {
    const sick = computePose('sick', 1.0);
    const idle = computePose('idle', 1.0);
    expect(sick.earPitch).toBeGreaterThan(0.7);
    expect(sick.headPitch).toBeGreaterThan(idle.headPitch + 0.1);
    expect(sick.wingPitch).toBeLessThan(idle.wingPitch);
  });

  it('sleeping bows deeper than idle but folds ears less than sick', () => {
    const sleeping = computePose('sleeping', 2.0);
    const sick = computePose('sick', 2.0);
    const idle = computePose('idle', 2.0);
    expect(sleeping.headPitch).toBeGreaterThan(idle.headPitch);
    expect(sleeping.earPitch).toBeLessThan(sick.earPitch);
    expect(sleeping.earPitch).toBeGreaterThan(idle.earPitch);
  });

  it('hopping lifts the body and sweeps the wings over the cycle', () => {
    let maxY = -Infinity;
    let minY = Infinity;
    let maxWing = -Infinity;
    for (let t = 0; t < 0.62; t += 0.01) {
      const p = computePose('hopping', t);
      maxY = Math.max(maxY, p.rootY);
      minY = Math.min(minY, p.rootY);
      maxWing = Math.max(maxWing, p.wingPitch);
    }
    expect(maxY - minY).toBeGreaterThan(0.12);
    expect(maxWing).toBeGreaterThan(0.4);
  });

  it('playing flaps harder than idle moves', () => {
    let playingMax = 0;
    let idleMax = 0;
    for (let t = 0; t < 2; t += 0.01) {
      playingMax = Math.max(playingMax, Math.abs(computePose('playing', t).wingPitch));
      idleMax = Math.max(idleMax, Math.abs(computePose('idle', t).wingPitch));
    }
    expect(playingMax).toBeGreaterThan(idleMax + 0.3);
  });

  it('eating dips the head repeatedly', () => {
    let dips = 0;
    let prev = computePose('eating', 0).headPitch;
    for (let t = 0.05; t < 2.5; t += 0.05) {
      const h = computePose('eating', t).headPitch;
      if (prev < 0.05 && h >= 0.05) dips += 1;
      prev = h;
    }
    expect(dips).toBeGreaterThanOrEqual(2);
  });
});

describe('dampPose', () => {
  it('converges toward the target', () => {
    const target = computePose('sick', 0);
    let cur = computePose('idle', 0);
    for (let i = 0; i < 120; i += 1) {
      cur = dampPose(cur, target, 1 / 60);
    }
    expect(Math.abs(cur.earPitch - target.earPitch)).toBeLessThan(0.01);
  });

  it('does not overshoot in one frame', () => {
    const target = computePose('sick', 0);
    const cur = dampPose(computePose('idle', 0), target, 1 / 60);
    expect(cur.earPitch).toBeGreaterThanOrEqual(0);
    expect(cur.earPitch).toBeLessThanOrEqual(target.earPitch);
  });
});
