import {
  advance,
  clean,
  createSave,
  feed,
  giveMedicine,
  hatch,
  play,
  putToSleep,
  serialize,
  startNewEgg,
  wake,
  type AdvanceResult,
  type PetEvent,
  type SaveEnvelope,
} from 'drabbit-core';
import { toSummary } from '../shared/summary.js';
import type { ActionKind, ActionOutcome, PetSummary } from '../shared/api-types.js';
import type { LoadOutcome, SaveStore } from './save-store.js';

/**
 * The pet service: the single owner of the one pet state in the main
 * process. Electron-free (clock + store are injected) so vitest can
 * drive it headlessly.
 *
 * The core stays clock-free (project invariant): this shell is where
 * `Date.now()` lives, and every core call receives the time as input.
 */

export interface Clock {
  now(): number;
}

export const systemClock: Clock = { now: () => Date.now() };

export interface PetServiceDeps {
  store: SaveStore;
  clock: Clock;
  onChanged?: (summary: PetSummary, events: PetEvent[]) => void;
  log?: (msg: string) => void;
  /** Test seam: start from this envelope instead of loading the save. */
  initialEnvelope?: SaveEnvelope;
}

export const DEFAULT_PET_NAME = 'Pip';
export const DEFAULT_FUR = 'royal' as const;

export interface TickResult {
  changed: boolean;
  events: PetEvent[];
}

export class PetService {
  private envelope: SaveEnvelope;
  /** How the save was obtained at startup (for logs / recovery notes). */
  readonly loadOutcome: LoadOutcome | 'injected';
  /**
   * Total events produced in the current pet-line's log since this
   * process started counting (anchored at the loaded log's length at
   * startup). This is the companion protocol's event cursor: the
   * event at log index `i` has sequence `eventTotal - log.length + i`.
   * Every mutation flows through tick()/doAction() below, and the
   * core reports exactly the events each call produced, so the count
   * is exact. It is per-process by design — see getEventsSince.
   */
  private eventTotal: number;

  constructor(private readonly deps: PetServiceDeps) {
    if (deps.initialEnvelope) {
      this.envelope = deps.initialEnvelope;
      this.loadOutcome = 'injected';
      this.eventTotal = this.envelope.pet.events.length;
      return;
    }
    const now = deps.clock.now();
    const result = deps.store.loadOrCreate(now, (t) =>
      createSave({ id: `drabbit-${t.toString(36)}`, name: DEFAULT_PET_NAME, fur: DEFAULT_FUR }, t),
    );
    this.envelope = result.envelope;
    this.loadOutcome = result.outcome;
    this.eventTotal = this.envelope.pet.events.length;
    if (result.outcome !== 'loaded') {
      // Persist the fresh egg immediately so a crash before the first
      // tick doesn't lose the pet's birth time.
      deps.store.save(this.envelope);
    }
  }

  getSummary(): PetSummary {
    return toSummary(this.envelope);
  }

  /** The most recent `limit` events, oldest first. */
  getEvents(limit = 50): PetEvent[] {
    return this.envelope.pet.events.slice(-limit);
  }

  /**
   * Events after a companion-protocol cursor, plus the current cursor.
   *
   * The cursor is a count, not an index: it is the total number of
   * events produced in this pet-line's log (see `eventTotal` above).
   * `since` means "I have seen `since` events" — the response is the
   * retained events with sequence >= `since`, in order, and `cursor`
   * is the new total to poll with next time. Passing the returned
   * cursor back yields only events produced in between. `since = 0`
   * returns the whole retained window (the core caps the log at 500,
   * so events older than the window are gone; if `since` predates
   * the window the whole window is returned). A `since` at or beyond
   * the current total — e.g. a stale cursor from before a desktop
   * restart, which renumbers from the loaded log — returns no events
   * and the current cursor, so pollers resync instead of erroring.
   */
  /** The current event cursor (see getEventsSince). */
  getEventCursor(): number {
    return this.eventTotal;
  }

  getEventsSince(since: number): { events: PetEvent[]; cursor: number } {
    const log = this.envelope.pet.events;
    const cursor = this.eventTotal;
    if (!Number.isFinite(since) || since >= cursor) {
      return { events: [], cursor };
    }
    const windowStart = cursor - log.length;
    const fromIndex = Math.max(0, Math.floor(since) - windowStart);
    return { events: log.slice(fromIndex), cursor };
  }

  /**
   * Advance the pet to clock-now and persist if anything changed.
   * Change detection is by canonical serialization: a tick that
   * doesn't cross a 1-minute sim step changes nothing and writes
   * nothing. A dead pet's state can no longer change, so it is not
   * advanced at all.
   */
  tick(): TickResult {
    if (this.envelope.pet.stage === 'dead') {
      return { changed: false, events: [] };
    }
    const before = serialize(this.envelope);
    const { state, events } = advance(this.envelope.pet, this.deps.clock.now());
    this.envelope = { ...this.envelope, pet: state };
    this.eventTotal += events.length;
    const changed = serialize(this.envelope) !== before;
    if (changed) {
      this.deps.store.save(this.envelope);
      this.emit(events);
    }
    return { changed, events };
  }

  /**
   * Run a UI care action. Core `PetError`s (wrong stage, asleep, …)
   * propagate to the caller — the IPC layer turns them into error
   * results; nothing is persisted for a rejected action.
   */
  doAction(kind: ActionKind): ActionOutcome {
    const now = this.deps.clock.now();
    const pet = this.envelope.pet;
    let events: PetEvent[];

    if (kind === 'new-egg') {
      // startNewEgg keeps the pet's name and fur for the next
      // generation (renaming is a future UI decision).
      const next = startNewEgg(this.envelope, {}, now);
      this.envelope = next;
      events = [...next.pet.events];
    } else {
      const result: AdvanceResult = (() => {
        switch (kind) {
          case 'feed-meal':
            return feed(pet, now, 'meal');
          case 'feed-snack':
            return feed(pet, now, 'snack');
          case 'play':
            return play(pet, now);
          case 'clean':
            return clean(pet, now);
          case 'sleep':
            return putToSleep(pet, now);
          case 'wake':
            return wake(pet, now);
          case 'medicine':
            return giveMedicine(pet, now);
          case 'hatch':
            return hatch(pet, now);
        }
      })();
      this.envelope = { ...this.envelope, pet: result.state };
      events = result.events;
    }
    this.eventTotal += events.length;

    this.deps.store.save(this.envelope);
    const summary = this.getSummary();
    this.emit(events);
    return { summary, events };
  }

  /** Final advance + persist, called on quit. */
  shutdown(): void {
    this.tick();
  }

  private emit(events: PetEvent[]): void {
    this.deps.onChanged?.(this.getSummary(), events);
  }
}
