import type { PetAnimState } from './visual-state.js';

/**
 * Procedural poses for the rigged 3D Pip (PetArt3D). Pure functions of
 * (anim state, time) so they unit-test headlessly; PetArt3D damps the
 * live pose toward these targets every frame, which is what makes
 * state changes glide instead of snapping.
 *
 * Angles are radians of LOCAL X rotation composed onto each bone's
 * rest orientation (the same convention as the Blender pose tests that
 * proved this rig: +earPitch folds the ears forward, +wingPitch sweeps
 * the wings up, +headPitch bows the head). rootY is a world-up offset
 * in metres for the root bone.
 */
export interface PetPose {
  rootY: number;
  sway: number;
  headPitch: number;
  earPitch: number;
  wingPitch: number;
  wing2Pitch: number;
  tailYaw: number;
}

const REST: PetPose = {
  rootY: 0,
  sway: 0,
  headPitch: 0,
  earPitch: 0,
  wingPitch: 0,
  wing2Pitch: 0,
  tailYaw: 0,
};

const TAU = Math.PI * 2;

/** One arch of a hop: 0 at the ground, 1 at the apex. */
function hopArch(t: number, period: number): number {
  const p = ((t % period) + period) % period / period;
  return Math.sin(Math.PI * p);
}

export function computePose(anim: PetAnimState, t: number): PetPose {
  switch (anim) {
    case 'hopping': {
      const arch = hopArch(t, 0.62);
      return {
        ...REST,
        rootY: 0.19 * Math.pow(arch, 1.3),
        headPitch: -0.05 * arch,
        earPitch: -0.1 + 0.22 * hopArch(t - 0.08, 0.62),
        wingPitch: 0.65 * arch,
        wing2Pitch: 0.35 * hopArch(t - 0.05, 0.62),
        tailYaw: 0.15 * Math.sin(TAU * (t / 0.62)),
      };
    }
    case 'playing': {
      const arch = hopArch(t, 0.5);
      return {
        ...REST,
        rootY: 0.16 * Math.pow(arch, 1.3),
        earPitch: 0.1 * Math.sin(TAU * (t / 0.5)),
        wingPitch: 0.3 + 0.45 * Math.sin(TAU * (t / 0.5)),
        wing2Pitch: 0.2 + 0.3 * Math.sin(TAU * (t / 0.5) - 0.5),
        tailYaw: 0.25 * Math.sin(TAU * (t / 0.5)),
      };
    }
    case 'eating': {
      const dip = Math.pow(Math.max(0, Math.sin(t * 5.2)), 1.5);
      return {
        ...REST,
        rootY: 0.02 * dip,
        headPitch: 0.38 * dip,
        earPitch: 0.05 + 0.04 * dip,
        wingPitch: 0.05,
      };
    }
    case 'sick':
      return {
        ...REST,
        rootY: -0.01,
        sway: 0.03 * Math.sin(t * 0.9),
        headPitch: 0.2,
        earPitch: 0.88,
        wingPitch: -0.22,
        wing2Pitch: -0.12,
        tailYaw: 0.03 * Math.sin(t * 0.7),
      };
    case 'sleeping':
      return {
        ...REST,
        rootY: -0.02 + 0.008 * Math.sin(TAU * (t / 4.5)),
        headPitch: 0.3,
        earPitch: 0.45,
        wingPitch: -0.12,
        wing2Pitch: -0.06,
        tailYaw: 0.02 * Math.sin(TAU * (t / 4.5)),
      };
    case 'idle':
    default:
      return {
        ...REST,
        rootY: 0.012 * Math.sin(TAU * (t / 2.4)),
        headPitch: 0.02 * Math.sin(TAU * (t / 2.4) + 0.3),
        earPitch: 0.04 * Math.sin(TAU * (t / 2.4) + 0.6),
        wingPitch: 0.03 * Math.sin(TAU * (t / 2.4)),
        wing2Pitch: 0.015 * Math.sin(TAU * (t / 2.4) + 0.4),
        tailYaw: 0.08 * Math.sin(TAU * (t / 3.8)),
      };
  }
}

/** Exponential approach of `current` toward `target` (frame-rate independent). */
export function dampPose(current: PetPose, target: PetPose, dt: number, tau = 0.06): PetPose {
  const k = 1 - Math.exp(-dt / tau);
  const mix = (a: number, b: number) => a + (b - a) * k;
  return {
    rootY: mix(current.rootY, target.rootY),
    sway: mix(current.sway, target.sway),
    headPitch: mix(current.headPitch, target.headPitch),
    earPitch: mix(current.earPitch, target.earPitch),
    wingPitch: mix(current.wingPitch, target.wingPitch),
    wing2Pitch: mix(current.wing2Pitch, target.wing2Pitch),
    tailYaw: mix(current.tailYaw, target.tailYaw),
  };
}
