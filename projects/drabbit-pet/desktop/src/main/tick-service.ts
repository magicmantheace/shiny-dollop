import type { PetService } from './pet-service.js';

/**
 * Schedules the pet service's tick. The scheduler is injectable so
 * tests can drive ticks manually; production uses setInterval.
 *
 * The pet sim is minute-granular, so a 5 s tick mostly observes
 * "nothing changed yet" — it exists so that a step boundary is never
 * more than a few seconds late in the UI.
 */

export interface Scheduler {
  set(fn: () => void, ms: number): unknown;
  clear(handle: unknown): void;
}

const systemScheduler: Scheduler = {
  set: (fn, ms) => setInterval(fn, ms),
  clear: (handle) => clearInterval(handle as ReturnType<typeof setInterval>),
};

export const DEFAULT_TICK_INTERVAL_MS = 5000;

export class TickService {
  private handle: unknown = null;

  constructor(
    private readonly service: PetService,
    private readonly opts: { intervalMs?: number; scheduler?: Scheduler } = {},
  ) {}

  get running(): boolean {
    return this.handle !== null;
  }

  start(): void {
    if (this.handle !== null) return;
    const scheduler = this.opts.scheduler ?? systemScheduler;
    const ms = this.opts.intervalMs ?? DEFAULT_TICK_INTERVAL_MS;
    this.handle = scheduler.set(() => {
      this.service.tick();
    }, ms);
  }

  stop(): void {
    if (this.handle === null) return;
    const scheduler = this.opts.scheduler ?? systemScheduler;
    scheduler.clear(this.handle);
    this.handle = null;
  }
}
