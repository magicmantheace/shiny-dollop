import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import type { PetSummary } from '../src/shared/api-types.js';
import { autoCareActionsFor } from '../src/shared/auto-care.js';
import {
  AutoCareConfigStore,
  AUTO_CARE_FILENAME,
} from '../src/main/auto-care-config.js';
import { AutoCareService } from '../src/main/auto-care.js';
import type { PetService } from '../src/main/pet-service.js';

function summary(over: Partial<PetSummary> = {}): PetSummary {
  return {
    id: 'x',
    name: 'Pip',
    fur: 'royal',
    stage: 'baby',
    adultForm: null,
    mood: 'content',
    needs: { hunger: 80, happiness: 80, energy: 90, cleanliness: 90 },
    health: 100,
    careScore: 70,
    ageMs: 60_000,
    asleep: false,
    sick: false,
    messes: 0,
    readyToHatch: false,
    generation: 1,
    deathCause: null,
    ...over,
  };
}

describe('autoCareActionsFor', () => {
  it('does nothing for a content pet', () => {
    expect(autoCareActionsFor(summary())).toEqual([]);
  });

  it('feeds below the hunger threshold, not at it', () => {
    const hungry = summary({ needs: { hunger: 39, happiness: 80, energy: 90, cleanliness: 90 } });
    expect(autoCareActionsFor(hungry)).toEqual(['feed-meal']);
    const atLine = summary({ needs: { hunger: 40, happiness: 80, energy: 90, cleanliness: 90 } });
    expect(autoCareActionsFor(atLine)).toEqual([]);
  });

  it('cleans for a mess or low cleanliness', () => {
    expect(autoCareActionsFor(summary({ messes: 1 }))).toEqual(['clean']);
    const grubby = summary({ needs: { hunger: 80, happiness: 80, energy: 90, cleanliness: 39 } });
    expect(autoCareActionsFor(grubby)).toEqual(['clean']);
  });

  it('plays when unhappy, but never with a tired pet', () => {
    const bored = summary({ needs: { hunger: 80, happiness: 34, energy: 90, cleanliness: 90 } });
    expect(autoCareActionsFor(bored)).toEqual(['play']);
    const tired = summary({ needs: { hunger: 80, happiness: 34, energy: 24, cleanliness: 90 } });
    expect(autoCareActionsFor(tired)).toEqual([]);
  });

  it('medicates first when sick, and still covers other needs', () => {
    const poorly = summary({
      sick: true,
      needs: { hunger: 10, happiness: 80, energy: 90, cleanliness: 90 },
    });
    expect(autoCareActionsFor(poorly)).toEqual(['medicine', 'feed-meal']);
  });

  it('never acts on an egg, a dead pet, or a sleeper', () => {
    const needy = { hunger: 0, happiness: 0, energy: 90, cleanliness: 0 };
    expect(autoCareActionsFor(summary({ stage: 'egg', needs: needy, messes: 3 }))).toEqual([]);
    expect(autoCareActionsFor(summary({ stage: 'dead', needs: needy }))).toEqual([]);
    expect(autoCareActionsFor(summary({ asleep: true, needs: needy, sick: true }))).toEqual([]);
  });
});

describe('AutoCareConfigStore', () => {
  function tmpStore() {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'drabbit-autocare-'));
    return { dir, store: new AutoCareConfigStore(dir) };
  }

  it('defaults to off when no file exists, and writes nothing', () => {
    const { dir, store } = tmpStore();
    const { config, outcome } = store.load(1000);
    expect(config.enabled).toBe(false);
    expect(outcome).toBe('fresh-missing');
    expect(fs.existsSync(path.join(dir, AUTO_CARE_FILENAME))).toBe(false);
  });

  it('round-trips the switch with no .tmp left behind', () => {
    const { dir, store } = tmpStore();
    store.save({ enabled: true });
    expect(store.load(1000).config.enabled).toBe(true);
    expect(fs.existsSync(path.join(dir, `${AUTO_CARE_FILENAME}.tmp`))).toBe(false);
  });

  it('a corrupt file is preserved aside and defaults are used', () => {
    const { dir, store } = tmpStore();
    fs.writeFileSync(path.join(dir, AUTO_CARE_FILENAME), '{oops');
    const { config, outcome, backupPath } = store.load(4242);
    expect(config.enabled).toBe(false);
    expect(outcome).toBe('fresh-corrupt');
    expect(backupPath).toBeTruthy();
    expect(fs.readFileSync(backupPath!, 'utf8')).toBe('{oops');
  });
});

/** A PetService stand-in: doAction applies simplified need deltas. */
class FakePet {
  performed: string[] = [];
  constructor(public current: PetSummary) {}
  getSummary(): PetSummary {
    return this.current;
  }
  doAction(kind: string): unknown {
    this.performed.push(kind);
    const n = { ...this.current.needs };
    if (kind === 'feed-meal') n.hunger = 90;
    if (kind === 'clean') n.cleanliness = 95;
    if (kind === 'play') n.happiness = 90;
    this.current = {
      ...this.current,
      needs: n,
      messes: kind === 'clean' ? 0 : this.current.messes,
      sick: kind === 'medicine' ? false : this.current.sick,
    };
    return { summary: this.current, events: [] };
  }
}

describe('AutoCareService', () => {
  function harness(pet: FakePet, enabled = false) {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'drabbit-autocare-'));
    const store = new AutoCareConfigStore(dir);
    if (enabled) store.save({ enabled: true });
    const svc = new AutoCareService({
      store,
      service: pet as unknown as PetService,
      now: () => 1000,
    });
    svc.init();
    return { svc, store };
  }

  it('does nothing while off, even for a needy pet', () => {
    const pet = new FakePet(summary({
      needs: { hunger: 5, happiness: 80, energy: 90, cleanliness: 90 },
    }));
    harness(pet).svc.consider();
    expect(pet.performed).toEqual([]);
  });

  it('acts on init when the persisted switch is on', () => {
    const pet = new FakePet(summary({
      sick: true,
      needs: { hunger: 5, happiness: 80, energy: 90, cleanliness: 90 },
    }));
    harness(pet, true);
    expect(pet.performed).toEqual(['medicine', 'feed-meal']);
  });

  it('setEnabled persists, and enabling mid-run acts immediately', () => {
    const pet = new FakePet(summary({ messes: 2 }));
    const { svc, store } = harness(pet);
    expect(svc.setEnabled(true).enabled).toBe(true);
    expect(pet.performed).toEqual(['clean']);
    expect(store.load(2000).config.enabled).toBe(true);
    svc.setEnabled(false);
    pet.current = summary({
      needs: { hunger: 0, happiness: 80, energy: 90, cleanliness: 90 },
    });
    svc.consider();
    expect(pet.performed).toEqual(['clean']);
  });
});
