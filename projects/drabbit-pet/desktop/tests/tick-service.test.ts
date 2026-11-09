import { describe, expect, it } from 'vitest';
import { createSave, type SaveEnvelope } from 'drabbit-core';
import { PetService } from '../src/main/pet-service.js';
import { SaveStore } from '../src/main/save-store.js';
import { TickService, type Scheduler } from '../src/main/tick-service.js';
import { FakeClock, tmpDir } from './helpers.js';

const T0 = 1_700_000_000_000;
const MIN = 60_000;

class CountingStore extends SaveStore {
  saves = 0;
  override save(envelope: SaveEnvelope): void {
    this.saves += 1;
    super.save(envelope);
  }
}

class ManualScheduler implements Scheduler {
  fn: (() => void) | null = null;
  ms: number | null = null;
  set(fn: () => void, ms: number): unknown {
    this.fn = fn;
    this.ms = ms;
    return 1;
  }
  clear(): void {
    this.fn = null;
  }
  fire(): void {
    this.fn?.();
  }
}

function makeService(dir: string, clock: FakeClock): { service: PetService; store: CountingStore } {
  const store = new CountingStore(dir);
  const service = new PetService({ store, clock });
  return { service, store };
}

describe('TickService + PetService.tick', () => {
  it('schedules at the default 5 s interval and stops cleanly', () => {
    const clock = new FakeClock(T0);
    const { service } = makeService(tmpDir(), clock);
    const scheduler = new ManualScheduler();
    const ticks = new TickService(service, { scheduler });
    expect(ticks.running).toBe(false);
    ticks.start();
    expect(ticks.running).toBe(true);
    expect(scheduler.ms).toBe(5000);
    ticks.start(); // no double-schedule
    ticks.stop();
    expect(ticks.running).toBe(false);
    expect(scheduler.fn).toBeNull();
  });

  it('persists the fresh egg once at startup, then only when a tick changes state', () => {
    const clock = new FakeClock(T0);
    const { service, store } = makeService(tmpDir(), clock);
    expect(store.saves).toBe(1); // the fresh egg, persisted by the constructor

    // No time passed → advance is a no-op → no write.
    expect(service.tick().changed).toBe(false);
    expect(store.saves).toBe(1);

    // Cross the 10-minute incubation boundary → egg becomes ready → write.
    clock.set(T0 + 11 * MIN);
    const res = service.tick();
    expect(res.changed).toBe(true);
    expect(res.events.map((e) => e.kind)).toContain('egg_ready');
    expect(store.saves).toBe(2);
    expect(service.getSummary().readyToHatch).toBe(true);

    // Same instant again → nothing new → no write.
    expect(service.tick().changed).toBe(false);
    expect(store.saves).toBe(2);
  });

  it('drives ticks through the injected scheduler with the injected clock', () => {
    const clock = new FakeClock(T0);
    const { service, store } = makeService(tmpDir(), clock);
    const scheduler = new ManualScheduler();
    new TickService(service, { scheduler }).start();

    scheduler.fire();
    expect(store.saves).toBe(1);
    clock.set(T0 + 30 * MIN);
    scheduler.fire();
    expect(store.saves).toBe(2);
    expect(service.getSummary().readyToHatch).toBe(true);
  });

  it('never persists for a dead pet', () => {
    const clock = new FakeClock(T0);
    const dir = tmpDir();
    const store = new CountingStore(dir);
    const env = createSave({ id: 'gone', name: 'Pip', fur: 'sky' }, T0);
    env.pet.stage = 'dead';
    env.pet.diedAt = T0;
    env.pet.deathCause = 'neglect';
    const service = new PetService({ store, clock, initialEnvelope: env });

    clock.set(T0 + 24 * 60 * MIN);
    expect(service.tick().changed).toBe(false);
    expect(store.saves).toBe(0);
  });

  it('emits onChanged only when a tick changed state', () => {
    const clock = new FakeClock(T0);
    const dir = tmpDir();
    const store = new CountingStore(dir);
    const seen: string[] = [];
    const service = new PetService({
      store,
      clock,
      onChanged: (_summary, events) => seen.push(...events.map((e) => e.kind)),
    });
    service.tick();
    expect(seen).toEqual([]);
    clock.set(T0 + 11 * MIN);
    service.tick();
    expect(seen).toContain('egg_ready');
  });
});
