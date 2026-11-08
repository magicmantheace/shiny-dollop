import { ACTION } from "./constants.js";
import { deriveMood } from "./mood.js";
import { advance, clampNeed, createEgg, pushEvent } from "./sim.js";
import {
  PetError,
  type AdvanceResult,
  type CreatePetOptions,
  type PetState,
  type SaveEnvelope,
} from "./types.js";

export type FeedVariant = "meal" | "snack";

/**
 * Every action starts by advancing the pet to `nowMs`, so hosts never
 * need to remember to tick first. Returned events include both the
 * advance events and the action's own event.
 */

function requireHatched(s: PetState): void {
  if (s.stage === "egg") throw new PetError("is_egg", "Still an egg — hatch it first.");
  if (s.stage === "dead") throw new PetError("is_dead", "This drabbit has died.");
}

function requireAwake(s: PetState): void {
  if (s.asleep) throw new PetError("asleep", "The drabbit is asleep.");
}

function finish(s: PetState, events: AdvanceResult["events"]): AdvanceResult {
  s.mood = deriveMood(s);
  return { state: s, events };
}

export function hatch(input: PetState, nowMs: number): AdvanceResult {
  const { state: s, events } = advance(input, nowMs);
  if (s.stage === "dead") throw new PetError("is_dead", "This drabbit has died.");
  if (s.stage !== "egg") throw new PetError("already_hatched", "Already hatched.");
  if (!s.readyToHatch) throw new PetError("not_ready", "The egg is not ready to hatch yet.");
  s.stage = "baby";
  s.hatchedAt = s.lastTickAt;
  s.ageMs = 0;
  pushEvent(s, events, "hatched", `${s.name} hatches! A tiny drabbit blinks at the world.`);
  return finish(s, events);
}

export function feed(input: PetState, nowMs: number, variant: FeedVariant): AdvanceResult {
  const { state: s, events } = advance(input, nowMs);
  requireHatched(s);
  requireAwake(s);
  const n = s.needs;
  if (variant === "meal") {
    if (n.hunger > ACTION.overfedAboveHunger) {
      s.health = clampNeed(s.health + ACTION.overfedHealth);
      s.careScore = clampNeed(s.careScore + ACTION.overfedCare);
      pushEvent(s, events, "overfed", "Stuffed past full — overfed.");
    } else if (n.hunger < ACTION.careBonusBelowNeed) {
      s.careScore = clampNeed(s.careScore + ACTION.mealCareBonus);
    }
    n.hunger = clampNeed(n.hunger + ACTION.meal.hunger);
    n.happiness = clampNeed(n.happiness + ACTION.meal.happiness);
    n.cleanliness = clampNeed(n.cleanliness + ACTION.meal.cleanliness);
    pushEvent(s, events, "fed", "Ate a proper meal.");
  } else {
    if (n.hunger >= ACTION.snackFullAtHunger) {
      s.careScore = clampNeed(s.careScore + ACTION.snackFullCare);
    } else if (n.hunger < ACTION.careBonusBelowNeed) {
      s.careScore = clampNeed(s.careScore + ACTION.snackCareBonus);
    }
    n.hunger = clampNeed(n.hunger + ACTION.snack.hunger);
    n.happiness = clampNeed(n.happiness + ACTION.snack.happiness);
    pushEvent(s, events, "fed", "Had a snack.");
  }
  return finish(s, events);
}

export function play(input: PetState, nowMs: number): AdvanceResult {
  const { state: s, events } = advance(input, nowMs);
  requireHatched(s);
  requireAwake(s);
  const n = s.needs;
  if (n.energy < ACTION.playMinEnergy) {
    throw new PetError("too_tired", "Too tired to play — needs rest.");
  }
  if (n.happiness < ACTION.careBonusBelowNeed) {
    s.careScore = clampNeed(s.careScore + ACTION.playCareBonus);
  }
  n.happiness = clampNeed(n.happiness + ACTION.play.happiness);
  n.energy = clampNeed(n.energy + ACTION.play.energy);
  n.hunger = clampNeed(n.hunger + ACTION.play.hunger);
  n.cleanliness = clampNeed(n.cleanliness + ACTION.play.cleanliness);
  pushEvent(s, events, "played", "Played — wings flapping, tail everywhere.");
  return finish(s, events);
}

export function clean(input: PetState, nowMs: number): AdvanceResult {
  const { state: s, events } = advance(input, nowMs);
  requireHatched(s);
  if (s.messes > 0) {
    s.careScore = clampNeed(s.careScore + ACTION.cleanCareWithMesses);
  } else if (s.needs.cleanliness < ACTION.cleanCareDirtyBelow) {
    s.careScore = clampNeed(s.careScore + ACTION.cleanCareDirty);
  }
  s.messes = 0;
  s.needs.cleanliness = 100;
  s.needs.happiness = clampNeed(s.needs.happiness + ACTION.cleanHappiness);
  pushEvent(s, events, "cleaned", "Cleaned up — sparkling fur, mild outrage.");
  return finish(s, events);
}

export function putToSleep(input: PetState, nowMs: number): AdvanceResult {
  const { state: s, events } = advance(input, nowMs);
  requireHatched(s);
  if (s.asleep) throw new PetError("already_asleep", "Already asleep.");
  if (s.needs.energy < ACTION.sleepCareBonusBelowEnergy) {
    s.careScore = clampNeed(s.careScore + ACTION.sleepCareBonus);
  }
  s.asleep = true;
  pushEvent(s, events, "fell_asleep", "Put to bed — curls up, tail over nose.");
  return finish(s, events);
}

export function wake(input: PetState, nowMs: number): AdvanceResult {
  const { state: s, events } = advance(input, nowMs);
  requireHatched(s);
  if (!s.asleep) throw new PetError("not_asleep", "Not asleep.");
  s.asleep = false;
  pushEvent(s, events, "woke", "Woken up.");
  return finish(s, events);
}

export function giveMedicine(input: PetState, nowMs: number): AdvanceResult {
  const { state: s, events } = advance(input, nowMs);
  requireHatched(s);
  if (!s.sick) throw new PetError("not_sick", "Not sick — medicine would just be mean.");
  s.sick = false;
  s.sickSince = null;
  s.health = clampNeed(s.health + ACTION.medicineHealth);
  s.needs.happiness = clampNeed(s.needs.happiness + ACTION.medicineHappiness);
  s.careScore = clampNeed(s.careScore + ACTION.medicineCareBonus);
  pushEvent(s, events, "cured", "Medicine given — cured (and offended).");
  return finish(s, events);
}

/**
 * Begin the next generation. The current pet must be dead; its record is
 * archived into the lineage and a fresh egg envelope is returned.
 */
export function startNewEgg(
  envelope: SaveEnvelope,
  options: Partial<CreatePetOptions>,
  nowMs: number,
): SaveEnvelope {
  const old = envelope.pet;
  if (old.stage !== "dead") {
    throw new PetError("not_dead", "The current drabbit is still alive.");
  }
  const generation = envelope.lineage.generation + 1;
  const pet = createEgg(
    {
      id: options.id ?? `${old.id}-g${generation}`,
      name: options.name ?? old.name,
      fur: options.fur ?? old.fur,
    },
    nowMs,
  );
  return {
    schemaVersion: envelope.schemaVersion,
    pet,
    lineage: {
      generation,
      ancestors: [
        ...envelope.lineage.ancestors,
        {
          name: old.name,
          fur: old.fur,
          adultForm: old.adultForm,
          bornAt: old.bornAt,
          diedAt: old.diedAt,
          deathCause: old.deathCause,
        },
      ],
    },
  };
}
