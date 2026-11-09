import { describe, expect, it } from "vitest";
import {
  advance,
  clean,
  feed,
  giveMedicine,
  hatch,
  play,
  putToSleep,
  wake,
} from "../src/index.js";
import { egg, hatched, H, MIN } from "./helpers.js";

describe("feed", () => {
  it("meal restores hunger and pays a care bonus when hungry", () => {
    let pet = hatched("feed-meal");
    pet.needs.hunger = 50;
    const r = feed(pet, pet.lastTickAt, "meal");
    expect(r.state.needs.hunger).toBeCloseTo(85, 5);
    expect(r.state.needs.happiness).toBeCloseTo(82, 5);
    expect(r.state.needs.cleanliness).toBeCloseTo(98, 5);
    expect(r.state.careScore).toBeCloseTo(71.5, 5);
    expect(r.events.some((e) => e.kind === "fed")).toBe(true);
  });

  it("meal clamps hunger at 100", () => {
    const pet = hatched("feed-clamp");
    const r = feed(pet, pet.lastTickAt, "meal");
    expect(r.state.needs.hunger).toBe(100);
  });

  it("overfeeding a full pet costs health and care score", () => {
    let pet = hatched("feed-over");
    pet.needs.hunger = 95;
    const r = feed(pet, pet.lastTickAt, "meal");
    expect(r.state.health).toBeCloseTo(97, 5);
    expect(r.state.careScore).toBeCloseTo(69, 5);
    expect(r.events.some((e) => e.kind === "overfed")).toBe(true);
  });

  it("snack is small, cheering, and a bad habit on a full belly", () => {
    let pet = hatched("feed-snack");
    pet.needs.hunger = 50;
    const r = feed(pet, pet.lastTickAt, "snack");
    expect(r.state.needs.hunger).toBeCloseTo(58, 5);
    expect(r.state.needs.happiness).toBeCloseTo(85, 5);
    expect(r.state.careScore).toBeCloseTo(70.5, 5);

    let full = hatched("feed-snack-full");
    full.needs.hunger = 95;
    const r2 = feed(full, full.lastTickAt, "snack");
    expect(r2.state.careScore).toBeCloseTo(69, 5);
  });

  it("cannot feed an egg or a sleeping pet", () => {
    expect(() => feed(egg("feed-egg"), MIN * 10, "meal")).toThrowError(
      expect.objectContaining({ code: "is_egg" }),
    );
    const awake = hatched("feed-sleep");
    const pet = putToSleep(awake, awake.lastTickAt).state;
    expect(() => feed(pet, pet.lastTickAt, "meal")).toThrowError(
      expect.objectContaining({ code: "asleep" }),
    );
  });
});

describe("play", () => {
  it("raises happiness at the cost of energy, hunger, cleanliness", () => {
    let pet = hatched("play-1");
    pet.needs.happiness = 50;
    const r = play(pet, pet.lastTickAt);
    expect(r.state.needs.happiness).toBeCloseTo(68, 5);
    expect(r.state.needs.energy).toBeCloseTo(93, 5);
    expect(r.state.needs.hunger).toBeCloseTo(77, 5);
    expect(r.state.needs.cleanliness).toBeCloseTo(98, 5);
    expect(r.state.careScore).toBeCloseTo(71.5, 5);
  });

  it("refuses when too tired", () => {
    let pet = hatched("play-tired");
    pet.needs.energy = 5;
    expect(() => play(pet, pet.lastTickAt)).toThrowError(
      expect.objectContaining({ code: "too_tired" }),
    );
  });
});

describe("clean", () => {
  it("clears messes, restores cleanliness, rewards the cleaner", () => {
    let pet = hatched("clean-1");
    pet.messes = 2;
    pet.needs.cleanliness = 30;
    const r = clean(pet, pet.lastTickAt);
    expect(r.state.messes).toBe(0);
    expect(r.state.needs.cleanliness).toBe(100);
    expect(r.state.careScore).toBeCloseTo(72, 5);
    expect(r.events.some((e) => e.kind === "cleaned")).toBe(true);
  });
});

describe("sleep and wake actions", () => {
  it("putting a tired pet to sleep earns care credit", () => {
    let pet = hatched("sleep-credit");
    pet.needs.energy = 20;
    const r = putToSleep(pet, pet.lastTickAt);
    expect(r.state.asleep).toBe(true);
    expect(r.state.careScore).toBeCloseTo(71, 5);
    const w = wake(r.state, r.state.lastTickAt);
    expect(w.state.asleep).toBe(false);
  });

  it("rejects redundant sleep/wake", () => {
    const pet = hatched("sleep-redundant");
    expect(() => wake(pet, pet.lastTickAt)).toThrowError(
      expect.objectContaining({ code: "not_asleep" }),
    );
    const asleep = putToSleep(pet, pet.lastTickAt).state;
    expect(() => putToSleep(asleep, asleep.lastTickAt)).toThrowError(
      expect.objectContaining({ code: "already_asleep" }),
    );
  });
});

describe("sickness", () => {
  it("breaks out under at-risk conditions (deterministic for this pet id)", () => {
    // Probed behaviour: pet-sick-a with hunger pinned at 0 falls sick at 57 min.
    let pet = hatched("pet-sick-a");
    pet.needs.hunger = 0;
    const r = advance(pet, pet.lastTickAt + 2 * H);
    expect(r.state.sick).toBe(true);
    expect(r.events.some((e) => e.kind === "sick")).toBe(true);
  });

  it("drains health and happiness faster while sick", () => {
    let pet = hatched("sick-drain");
    pet.sick = true;
    pet.sickSince = pet.lastTickAt;
    const before = pet.health;
    const r = advance(pet, pet.lastTickAt + H);
    // Sick: -0.08/min health, no recovery; happiness: normal decay + 0.10/min extra.
    expect(r.state.health).toBeCloseTo(before - 0.08 * 60, 5);
    expect(r.state.needs.happiness).toBeCloseTo(80 - (0.22 + 0.1) * 60, 5);
  });

  it("medicine cures, at a small happiness price", () => {
    let pet = hatched("sick-cure");
    pet.sick = true;
    pet.sickSince = pet.lastTickAt;
    pet.health = 50;
    const r = giveMedicine(pet, pet.lastTickAt);
    expect(r.state.sick).toBe(false);
    expect(r.state.health).toBeCloseTo(56, 5);
    expect(r.state.needs.happiness).toBeCloseTo(78, 5);
    expect(r.state.careScore).toBeCloseTo(73, 5);
    expect(r.events.some((e) => e.kind === "cured")).toBe(true);
  });

  it("medicine on a healthy pet is refused", () => {
    const pet = hatched("sick-healthy");
    expect(() => giveMedicine(pet, pet.lastTickAt)).toThrowError(
      expect.objectContaining({ code: "not_sick" }),
    );
  });
});

describe("messes", () => {
  it("happen over time while awake (deterministic for this pet id)", () => {
    // Probed behaviour: pet-mess-a makes its first mess 20 minutes after hatch.
    const pet = hatched("pet-mess-a");
    const r = advance(pet, pet.lastTickAt + H);
    expect(r.events.some((e) => e.kind === "mess")).toBe(true);
    expect(r.state.messes).toBeGreaterThanOrEqual(1);
  });

  it("hatching twice is refused", () => {
    const pet = hatched("hatch-twice");
    expect(() => hatch(pet, pet.lastTickAt)).toThrowError(
      expect.objectContaining({ code: "already_hatched" }),
    );
  });
});
