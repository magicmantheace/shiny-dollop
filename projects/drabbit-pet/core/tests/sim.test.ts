import { describe, expect, it } from "vitest";
import {
  advance,
  deriveMood,
  hatch,
  putToSleep,
  serialize,
  type PetState,
  type SaveEnvelope,
} from "../src/index.js";
import { H, MIN, T0, egg, hatched } from "./helpers.js";

describe("egg stage", () => {
  it("does not decay needs while incubating", () => {
    const r = advance(egg("egg-calm"), T0 + 9 * MIN);
    expect(r.state.needs).toEqual({ hunger: 80, happiness: 80, energy: 100, cleanliness: 100 });
    expect(r.state.readyToHatch).toBe(false);
    expect(r.state.stepCount).toBe(9);
  });

  it("becomes ready to hatch at exactly 10 minutes", () => {
    const r = advance(egg("egg-ready"), T0 + 10 * MIN);
    expect(r.state.readyToHatch).toBe(true);
    expect(r.events.some((e) => e.kind === "egg_ready")).toBe(true);
  });

  it("refuses to hatch before it is ready", () => {
    expect(() => hatch(egg("egg-early"), T0 + 5 * MIN)).toThrowError(
      expect.objectContaining({ code: "not_ready" }),
    );
  });

  it("hatches into a baby with hatch values", () => {
    const r = hatch(egg("egg-hatch"), T0 + 10 * MIN);
    expect(r.state.stage).toBe("baby");
    expect(r.state.hatchedAt).toBe(T0 + 10 * MIN);
    expect(r.state.ageMs).toBe(0);
    expect(r.state.health).toBe(100);
    expect(r.state.careScore).toBe(70);
    expect(r.events.some((e) => e.kind === "hatched")).toBe(true);
  });
});

describe("decay math", () => {
  it("applies baby decay rates for one awake hour", () => {
    const pet = hatched("decay-baby");
    const r = advance(pet, pet.lastTickAt + H);
    const messes = r.events.filter((e) => e.kind === "mess").length;
    expect(r.state.needs.hunger).toBeCloseTo(80 - 0.3 * 60, 5);
    expect(r.state.needs.happiness).toBeCloseTo(80 - 0.22 * 60, 5);
    expect(r.state.needs.energy).toBeCloseTo(100 - 0.25 * 60, 5);
    expect(r.state.needs.cleanliness).toBeCloseTo(100 - 0.1 * 60 - 8 * messes, 5);
    expect(r.state.sick).toBe(false);
  });

  it("applies adult decay rates for one awake hour", () => {
    let pet = hatched("decay-adult");
    // Fast-forward the paperwork: make the next step cross into adulthood,
    // then set known need values and measure one clean hour.
    pet.hatchedAt = pet.lastTickAt - (19 * H - MIN);
    pet.ageMs = 19 * H - MIN;
    pet = advance(pet, pet.lastTickAt + MIN).state;
    expect(pet.stage).toBe("adult");
    pet.needs = { hunger: 90, happiness: 90, energy: 90, cleanliness: 90 };
    pet.health = 100;
    const r = advance(pet, pet.lastTickAt + H);
    const messes = r.events.filter((e) => e.kind === "mess").length;
    expect(r.state.needs.hunger).toBeCloseTo(90 - 0.16 * 60, 5);
    expect(r.state.needs.happiness).toBeCloseTo(90 - 0.11 * 60, 5);
    expect(r.state.needs.energy).toBeCloseTo(90 - 0.13 * 60, 5);
    expect(r.state.needs.cleanliness).toBeCloseTo(90 - 0.06 * 60 - 8 * messes, 5);
  });

  it("clamps needs at 0 and 100", () => {
    let pet = hatched("decay-clamp");
    pet.needs.hunger = 1;
    const r = advance(pet, pet.lastTickAt + H);
    expect(r.state.needs.hunger).toBe(0);
    expect(r.state.needs.energy).toBeLessThanOrEqual(100);
  });

  it("advancing to a past or equal time is a no-op", () => {
    const pet = hatched("decay-noop");
    const r = advance(pet, pet.lastTickAt - H);
    expect(r.events).toHaveLength(0);
    expect(r.state.lastTickAt).toBe(pet.lastTickAt);
    expect(r.state.needs).toEqual(pet.needs);
  });
});

describe("sleep", () => {
  it("regenerates energy and slows other decay while asleep", () => {
    let pet = hatched("sleep-rates");
    pet.needs.energy = 40;
    pet = putToSleep(pet, pet.lastTickAt).state;
    const r = advance(pet, pet.lastTickAt + 20 * MIN);
    expect(r.state.asleep).toBe(true);
    expect(r.state.needs.energy).toBeCloseTo(40 + 1.5 * 20, 5);
    expect(r.state.needs.hunger).toBeCloseTo(80 - 0.3 * 0.3 * 20, 5);
  });

  it("falls asleep from exhaustion at low energy", () => {
    let pet = hatched("sleep-exhausted");
    pet.needs.energy = 2;
    const r = advance(pet, pet.lastTickAt + MIN);
    expect(r.state.asleep).toBe(true);
    expect(r.events.some((e) => e.kind === "fell_asleep")).toBe(true);
  });

  it("wakes on its own when fully rested", () => {
    let pet = hatched("sleep-wake");
    pet.needs.energy = 99;
    pet = putToSleep(pet, pet.lastTickAt).state;
    const r = advance(pet, pet.lastTickAt + MIN);
    expect(r.state.asleep).toBe(false);
    expect(r.events.some((e) => e.kind === "woke")).toBe(true);
  });
});

describe("stage transitions", () => {
  function agedTo(id: string, ageMs: number): PetState {
    let pet = hatched(id);
    pet.hatchedAt = pet.lastTickAt - (ageMs - MIN);
    pet.ageMs = ageMs - MIN;
    pet.needs = { hunger: 90, happiness: 90, energy: 90, cleanliness: 90 };
    pet.health = 100;
    return pet;
  }

  it("baby becomes child at 1 hour of age", () => {
    const pet = agedTo("stage-child", H);
    const r = advance(pet, pet.lastTickAt + MIN);
    expect(r.state.stage).toBe("child");
    expect(r.events.some((e) => e.kind === "stage" && e.detail.includes("child"))).toBe(true);
  });

  it("child becomes teen at 7 hours of age", () => {
    const pet = agedTo("stage-teen", 7 * H);
    pet.stage = "child";
    const r = advance(pet, pet.lastTickAt + MIN);
    expect(r.state.stage).toBe("teen");
  });

  it("teen becomes adult at 19 hours of age and fixes an adult form", () => {
    const pet = agedTo("stage-adult", 19 * H);
    pet.stage = "teen";
    const r = advance(pet, pet.lastTickAt + MIN);
    expect(r.state.stage).toBe("adult");
    expect(r.state.adultForm).not.toBeNull();
    expect(r.events.some((e) => e.kind === "adult_form")).toBe(true);
  });
});

describe("determinism and offline catch-up", () => {
  it("one 24h jump equals hourly chunks and minute ticks, byte for byte", () => {
    const start = hatched("catchup-1");
    const end = start.lastTickAt + 24 * H;
    const wrap = (pet: PetState): string =>
      serialize({ schemaVersion: 1, pet, lineage: { generation: 1, ancestors: [] } } satisfies SaveEnvelope);

    const single = advance(start, end).state;

    let hourly = start;
    for (let i = 0; i < 24; i++) hourly = advance(hourly, hourly.lastTickAt + H).state;

    let minutely = start;
    for (let i = 0; i < 24 * 60; i++) minutely = advance(minutely, minutely.lastTickAt + MIN).state;

    expect(wrap(single)).toBe(wrap(hourly));
    expect(wrap(single)).toBe(wrap(minutely));
    expect(single.events.length).toBe(hourly.events.length);
  });

  it("keeps sub-step remainders: advancing 90 seconds twice equals 3 minutes once", () => {
    const pet = hatched("catchup-remainder");
    const a = advance(pet, pet.lastTickAt + 90_000);
    const b = advance(a.state, pet.lastTickAt + 180_000);
    const c = advance(pet, pet.lastTickAt + 180_000);
    expect(b.state.stepCount).toBe(c.state.stepCount);
    expect(b.state.needs).toEqual(c.state.needs);
  });
});

describe("mood derivation", () => {
  it("prioritises sickness over low needs, and sleep over frailty", () => {
    const pet = hatched("mood-1");
    pet.needs.hunger = 5;
    expect(deriveMood(pet)).toBe("miserable");
    pet.sick = true;
    expect(deriveMood(pet)).toBe("sick");
    pet.sick = false;
    pet.asleep = true;
    expect(deriveMood(pet)).toBe("asleep");
  });

  it("is joyful when needs are high", () => {
    const pet = hatched("mood-2");
    expect(deriveMood(pet)).toBe("joyful");
  });
});
