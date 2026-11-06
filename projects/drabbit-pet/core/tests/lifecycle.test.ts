import { describe, expect, it } from "vitest";
import {
  advance,
  adultFormForCare,
  clean,
  feed,
  giveMedicine,
  play,
  putToSleep,
  startNewEgg,
  wake,
  type SaveEnvelope,
} from "../src/index.js";
import { hatched, H, MIN } from "./helpers.js";
const WEEK = 7 * 24 * H;

describe("adult form by care band", () => {
  it("maps scores to forms at the band edges", () => {
    expect(adultFormForCare(100)).toBe("radiant");
    expect(adultFormForCare(70)).toBe("radiant");
    expect(adultFormForCare(69.9)).toBe("content");
    expect(adultFormForCare(40)).toBe("content");
    expect(adultFormForCare(39.9)).toBe("scruffy");
    expect(adultFormForCare(0)).toBe("scruffy");
  });

  it.each([
    [85, "radiant"],
    [55, "content"],
    [20, "scruffy"],
  ])("careScore %i at the adult transition yields %s", (score, form) => {
    const pet = hatched(`form-${score}`);
    pet.stage = "teen";
    pet.hatchedAt = pet.lastTickAt - (19 * H - MIN);
    pet.ageMs = 19 * H - MIN;
    pet.needs = { hunger: 90, happiness: 90, energy: 90, cleanliness: 90 };
    pet.health = 100;
    pet.careScore = score;
    const r = advance(pet, pet.lastTickAt + MIN);
    expect(r.state.stage).toBe("adult");
    expect(r.state.adultForm).toBe(form);
  });
});

describe("a cared-for life", () => {
  it("grows baby → child → teen → adult under regular care", () => {
    let pet = hatched("life-1");
    const stageDetails: string[] = [];
    let now = pet.lastTickAt;
    let guard = 0;
    while (pet.stage !== "adult" && pet.stage !== "dead" && guard++ < 400) {
      now += 15 * MIN;
      const before = pet.events.length;
      pet = advance(pet, now).state;
      for (const e of pet.events.slice(before)) {
        if (e.kind === "stage") stageDetails.push(e.detail);
      }
      if (pet.stage === "dead") break;
      if (pet.sick) pet = giveMedicine(pet, now).state;
      else if (pet.asleep && pet.needs.energy > 92) pet = wake(pet, now).state;
      else if (!pet.asleep && pet.needs.energy < 18) pet = putToSleep(pet, now).state;
      else if (!pet.asleep && pet.messes > 0) pet = clean(pet, now).state;
      else if (!pet.asleep && pet.needs.hunger < 45) pet = feed(pet, now, "meal").state;
      else if (!pet.asleep && pet.needs.happiness < 45) pet = play(pet, now).state;
    }
    expect(pet.stage).toBe("adult");
    expect(pet.adultForm).not.toBeNull();
    expect(stageDetails.some((d) => d.includes("child"))).toBe(true);
    expect(stageDetails.some((d) => d.includes("teen"))).toBe(true);
    expect(stageDetails.some((d) => d.includes("adult"))).toBe(true);
  });
});

describe("death and rebirth", () => {
  it("total neglect kills, records the cause, and refuses further care", () => {
    // Probed behaviour: pet-neglect dies of sickness ~14.8 h after hatch.
    const pet = hatched("pet-neglect");
    const r = advance(pet, pet.lastTickAt + WEEK);
    expect(r.state.stage).toBe("dead");
    expect(r.state.deathCause).toBe("sickness");
    expect(r.state.diedAt).not.toBeNull();
    expect(r.state.diedAt! - r.state.hatchedAt!).toBeLessThan(24 * H);
    expect(r.events.some((e) => e.kind === "died")).toBe(true);
    expect(() => feed(r.state, r.state.lastTickAt, "meal")).toThrowError(
      expect.objectContaining({ code: "is_dead" }),
    );
  });

  it("startNewEgg archives the ancestor and begins generation 2", () => {
    const pet = hatched("pet-neglect");
    const dead = advance(pet, pet.lastTickAt + WEEK).state;
    const env: SaveEnvelope = {
      schemaVersion: 1,
      pet: dead,
      lineage: { generation: 1, ancestors: [] },
    };
    const next = startNewEgg(env, {}, dead.lastTickAt + H);
    expect(next.lineage.generation).toBe(2);
    expect(next.lineage.ancestors).toHaveLength(1);
    expect(next.lineage.ancestors[0]?.name).toBe("pet-neglect");
    expect(next.lineage.ancestors[0]?.deathCause).toBe("sickness");
    expect(next.pet.stage).toBe("egg");
    expect(next.pet.id).toBe("pet-neglect-g2");
    expect(next.pet.events.some((e) => e.kind === "created")).toBe(true);
  });

  it("startNewEgg refuses while the current pet lives", () => {
    const pet = hatched("still-alive");
    const env: SaveEnvelope = {
      schemaVersion: 1,
      pet,
      lineage: { generation: 1, ancestors: [] },
    };
    expect(() => startNewEgg(env, {}, pet.lastTickAt)).toThrowError(
      expect.objectContaining({ code: "not_dead" }),
    );
  });
});
