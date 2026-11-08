import { describe, expect, it } from 'vitest';
import {
  advance,
  createSave,
  hatch,
  putToSleep,
  type SaveEnvelope,
} from 'drabbit-core';
import { AutoCareConfigStore } from '../src/main/auto-care-config.js';
import { AutoCareService } from '../src/main/auto-care.js';
import { PetService } from '../src/main/pet-service.js';
import { SaveStore } from '../src/main/save-store.js';
import { FakeClock, tmpDir } from './helpers.js';

const T0 = 1_700_000_000_000;
const MIN = 60_000;

/** A hatched baby, asleep with hunger below auto-care's feed line. */
function sleepingHungryBaby(): SaveEnvelope {
  const env = createSave({ id: 'wake-feed', name: 'Pip', fur: 'royal' }, T0);
  let pet = advance(env.pet, T0 + 11 * MIN).state; // egg ready to hatch
  pet = hatch(pet, T0 + 11 * MIN).state;
  pet = { ...pet, needs: { ...pet.needs, hunger: 10 } };
  pet = putToSleep(pet, T0 + 11 * MIN).state;
  return { ...env, pet };
}

describe('PetService.doAction summary freshness', () => {
  it('returns the post-callback summary when a change callback acts synchronously', () => {
    // Mirror the production wiring (main.ts): onChanged broadcasts,
    // then auto-care evaluates — and with the switch on it acts
    // synchronously through this same service while the outer
    // doAction is still on the stack. The action outcome must
    // describe the pet AFTER that feeding, not before it.
    const clock = new FakeClock(T0 + 11 * MIN);
    const store = new SaveStore(tmpDir());
    let autoCare: AutoCareService | undefined;
    const service = new PetService({
      store,
      clock,
      initialEnvelope: sleepingHungryBaby(),
      onChanged: () => autoCare?.consider(),
    });
    const configStore = new AutoCareConfigStore(tmpDir());
    configStore.save({ enabled: true });
    autoCare = new AutoCareService({ store: configStore, service, now: () => T0 });
    // init() loads the enabled switch; its immediate consider() is a
    // no-op here because auto-care never acts on a sleeping pet.
    autoCare.init();
    expect(service.getSummary().asleep).toBe(true);
    expect(service.getSummary().needs.hunger).toBe(10);

    const outcome = service.doAction('wake');

    expect(outcome.summary.asleep).toBe(false);
    // Auto-care fed the pet during the wake's change notification
    // (hunger 10 is below its feed line), raising hunger.
    expect(outcome.summary.needs.hunger).toBeGreaterThan(10);
    // The returned summary is the service's current summary, not a
    // snapshot captured before the callback ran.
    expect(outcome.summary).toEqual(service.getSummary());
  });
});
