import { describe, expect, it } from 'vitest';
import { createSave, PetError, type SaveEnvelope } from 'drabbit-core';
import { PetService, type PetServiceDeps } from '../src/main/pet-service.js';
import { SaveStore } from '../src/main/save-store.js';
import { parseActionPayload } from '../src/shared/validation.js';
import { FakeClock, tmpDir } from './helpers.js';

const T0 = 1_700_000_000_000;
const MIN = 60_000;

function makeService(clock: FakeClock, extra: Partial<PetServiceDeps> = {}): PetService {
  return new PetService({ store: new SaveStore(tmpDir()), clock, ...extra });
}

function expectPetError(fn: () => unknown, code: string): void {
  try {
    fn();
  } catch (err) {
    expect(err).toBeInstanceOf(PetError);
    expect((err as PetError).code).toBe(code);
    return;
  }
  throw new Error(`expected PetError(${code}) but nothing was thrown`);
}

/** A service whose pet hatched at T0 (clock is still at T0). */
function hatchedService(): { service: PetService; clock: FakeClock } {
  const clock = new FakeClock(T0);
  const service = makeService(clock);
  clock.set(T0 + 10 * MIN);
  service.doAction('hatch');
  clock.set(T0); // actions advance first; rewinding the shell clock is a no-op for the sim
  return { service, clock };
}

describe('parseActionPayload', () => {
  it('accepts every UI action kind', () => {
    for (const kind of ['feed-meal', 'feed-snack', 'play', 'clean', 'sleep', 'wake', 'medicine', 'hatch', 'new-egg']) {
      const r = parseActionPayload({ kind });
      expect(r.ok).toBe(true);
      if (r.ok) expect(r.value.kind).toBe(kind);
    }
  });

  it('rejects malformed payloads with bad_payload', () => {
    for (const bad of [null, undefined, 'play', 42, {}, { kind: 'dance' }, { kind: 7 }, []]) {
      const r = parseActionPayload(bad);
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.error.code).toBe('bad_payload');
    }
  });
});

describe('IPC action mapping (PetService.doAction)', () => {
  it('hatch: rejected before incubation, works once ready', () => {
    const clock = new FakeClock(T0);
    const service = makeService(clock);
    expectPetError(() => service.doAction('hatch'), 'not_ready');

    clock.set(T0 + 10 * MIN);
    const outcome = service.doAction('hatch');
    expect(outcome.events.map((e) => e.kind)).toContain('hatched');
    expect(outcome.summary.stage).toBe('baby');
    expect(outcome.summary.needs.hunger).toBe(80);
    expect(outcome.summary.needs.happiness).toBe(80);
  });

  it('feed-snack and feed-meal map to the right core feed variants', () => {
    const { service } = hatchedService();
    const snack = service.doAction('feed-snack');
    expect(snack.events.map((e) => e.kind)).toContain('fed');
    expect(snack.summary.needs.hunger).toBe(88); // 80 + 8
    expect(snack.summary.needs.happiness).toBe(85); // 80 + 5

    const meal = service.doAction('feed-meal');
    expect(meal.summary.needs.hunger).toBe(100); // 88 + 35, clamped
    expect(meal.summary.needs.cleanliness).toBe(98); // 100 − 2
    expect(meal.events.map((e) => e.kind)).not.toContain('overfed');
  });

  it('play maps to core play with its costs', () => {
    const { service } = hatchedService();
    const outcome = service.doAction('play');
    expect(outcome.events.map((e) => e.kind)).toContain('played');
    expect(outcome.summary.needs.happiness).toBe(98); // 80 + 18
    expect(outcome.summary.needs.energy).toBe(93); // 100 − 7
  });

  it('sleep/wake gate feed and play; clean is allowed while asleep', () => {
    const { service } = hatchedService();
    const slept = service.doAction('sleep');
    expect(slept.summary.asleep).toBe(true);
    expect(slept.events.map((e) => e.kind)).toContain('fell_asleep');

    expectPetError(() => service.doAction('feed-meal'), 'asleep');
    expectPetError(() => service.doAction('play'), 'asleep');
    expectPetError(() => service.doAction('sleep'), 'already_asleep');

    const cleaned = service.doAction('clean');
    expect(cleaned.summary.needs.cleanliness).toBe(100);

    const woke = service.doAction('wake');
    expect(woke.summary.asleep).toBe(false);
    expect(woke.events.map((e) => e.kind)).toContain('woke');
  });

  it('medicine: rejected when healthy, cures a sick pet', () => {
    const { service } = hatchedService();
    expectPetError(() => service.doAction('medicine'), 'not_sick');

    const clock = new FakeClock(T0);
    const env: SaveEnvelope = createSave({ id: 'sick-1', name: 'Pip', fur: 'sky' }, T0);
    env.pet.stage = 'baby';
    env.pet.hatchedAt = T0;
    env.pet.sick = true;
    env.pet.sickSince = T0;
    env.pet.health = 50;
    const sickService = makeService(clock, { initialEnvelope: env });
    const cured = sickService.doAction('medicine');
    expect(cured.summary.sick).toBe(false);
    expect(cured.summary.health).toBe(56); // 50 + 6
    expect(cured.events.map((e) => e.kind)).toContain('cured');
  });

  it('new-egg: rejected while alive, starts generation 2 after death', () => {
    const { service } = hatchedService();
    expectPetError(() => service.doAction('new-egg'), 'not_dead');

    const clock = new FakeClock(T0);
    const env: SaveEnvelope = createSave({ id: 'gone-1', name: 'Pip', fur: 'ember' }, T0);
    env.pet.stage = 'dead';
    env.pet.diedAt = T0;
    env.pet.deathCause = 'neglect';
    const deadService = makeService(clock, { initialEnvelope: env });
    const outcome = deadService.doAction('new-egg');
    expect(outcome.summary.stage).toBe('egg');
    expect(outcome.summary.generation).toBe(2);
    expect(outcome.summary.name).toBe('Pip'); // kept for the next generation
  });

  it('actions on an egg (other than hatch) are rejected cleanly', () => {
    const clock = new FakeClock(T0);
    const service = makeService(clock);
    expectPetError(() => service.doAction('feed-meal'), 'is_egg');
    expectPetError(() => service.doAction('play'), 'is_egg');
    expectPetError(() => service.doAction('new-egg'), 'not_dead');
  });
});
