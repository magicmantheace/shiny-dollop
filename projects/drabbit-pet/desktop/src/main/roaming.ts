import type { Stage } from 'drabbit-core';

/**
 * Roaming planner: decides where the pet window goes next along the
 * bottom of the work area. Pure and clock-free — the main process
 * calls `step()` on its own timer and applies the result. Randomness
 * is injected so behaviour is testable.
 *
 * Pattern: long idle sits, occasional short hops. The pet never roams
 * while it is an egg or dead, while asleep, while the care panel is
 * open, or while roaming is paused from the tray.
 */

export interface RoamBounds {
  minX: number;
  maxX: number;
}

export interface RoamContext {
  stage: Stage;
  asleep: boolean;
  panelOpen: boolean;
  paused: boolean;
}

export interface RoamStep {
  /** Absolute x to place the window at (always within bounds). */
  x: number;
  /** True while a hop is in progress (renderer plays the hop anim). */
  hopping: boolean;
}

/** Horizontal px per planner step while hopping. */
export const HOP_STEP_PX = 7;
/** Chance per decision point to keep sitting instead of hopping. */
const SIT_CHANCE = 0.55;

function clamp(v: number, bounds: RoamBounds): number {
  return Math.max(bounds.minX, Math.min(bounds.maxX, v));
}

export class RoamPlanner {
  private targetX: number | null = null;
  private sitTicksLeft = 0;

  constructor(private readonly rand: () => number = Math.random) {}

  step(currentX: number, bounds: RoamBounds, ctx: RoamContext): RoamStep {
    const x = clamp(Math.round(currentX), bounds);

    if (ctx.paused || ctx.panelOpen || ctx.asleep || ctx.stage === 'egg' || ctx.stage === 'dead') {
      this.targetX = null;
      return { x, hopping: false };
    }

    if (this.sitTicksLeft > 0) {
      this.sitTicksLeft -= 1;
      return { x, hopping: false };
    }

    if (this.targetX === null) {
      if (this.rand() < SIT_CHANCE) {
        // Sit for ~6–24 s at the main loop's 200 ms cadence.
        this.sitTicksLeft = 30 + Math.floor(this.rand() * 90);
        return { x, hopping: false };
      }
      const dir = this.rand() < 0.5 ? -1 : 1;
      const dist = 40 + this.rand() * 220;
      const target = clamp(Math.round(x + dir * dist), bounds);
      if (target === x) {
        // Pinned against an edge — sit instead of hopping in place.
        this.sitTicksLeft = 20;
        return { x, hopping: false };
      }
      this.targetX = target;
    }

    const dx = this.targetX - x;
    const next = x + Math.sign(dx) * Math.min(Math.abs(dx), HOP_STEP_PX);
    if (next === this.targetX) {
      this.targetX = null;
      // Settle after a hop for ~8–32 s.
      this.sitTicksLeft = 40 + Math.floor(this.rand() * 120);
    }
    return { x: next, hopping: true };
  }
}
