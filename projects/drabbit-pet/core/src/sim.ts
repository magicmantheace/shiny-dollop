import {
  ADULT_FORM_CONTENT_AT,
  ADULT_FORM_RADIANT_AT,
  ASLEEP_DECAY_FACTOR,
  ASLEEP_ENERGY_REGEN_PER_MIN,
  AUTO_SLEEP_ENERGY,
  AUTO_WAKE_ENERGY,
  CARE_ALL_GOOD_AT_LEAST,
  CARE_ALL_GOOD_PER_MIN,
  CARE_LOW_NEED_BELOW,
  CARE_LOW_NEED_PER_MIN,
  CARE_ZERO_NEED_PER_MIN,
  DECAY_PER_MIN,
  EGG_INCUBATION_MS,
  EVENT_CAP,
  HATCH_NEEDS,
  HEALTH_FILTHY_PER_MIN,
  HEALTH_RECOVERY_PER_MIN,
  HEALTH_SICK_PER_MIN,
  HEALTH_STARVING_PER_MIN,
  MESS_CHANCE_PER_MIN,
  MESS_CLEANLINESS_HIT,
  MESS_FULL_BELLY_HUNGER,
  MESS_FULL_BELLY_MULTIPLIER,
  RECOVERY_MIN_CLEANLINESS,
  RECOVERY_MIN_HUNGER,
  SICK_CHANCE_PER_MIN,
  SICK_CLEANLINESS_BELOW,
  SICK_HAPPINESS_DECAY_PER_MIN,
  SICK_MESSES_AT_LEAST,
  STAGE_START_AGE_MS,
  START_CARE_SCORE,
  START_HEALTH,
  STEP_MS,
} from "./constants.js";
import { deriveMood } from "./mood.js";
import { ROLL_MESS, ROLL_SICK, stepRoll } from "./rng.js";
import {
  SCHEMA_VERSION,
  type AdvanceResult,
  type AdultForm,
  type CreatePetOptions,
  type PetEvent,
  type PetState,
  type Stage,
} from "./types.js";

export function clampNeed(v: number): number {
  return v < 0 ? 0 : v > 100 ? 100 : v;
}

/** PetState is pure JSON data; a JSON round-trip is a complete clone. */
export function cloneState(state: PetState): PetState {
  return JSON.parse(JSON.stringify(state)) as PetState;
}

export function pushEvent(state: PetState, sink: PetEvent[], kind: string, detail: string): void {
  const event: PetEvent = { t: state.lastTickAt, kind, detail };
  state.events.push(event);
  if (state.events.length > EVENT_CAP) {
    state.events.splice(0, state.events.length - EVENT_CAP);
  }
  sink.push(event);
}

export function createEgg(options: CreatePetOptions, nowMs: number): PetState {
  const state: PetState = {
    schemaVersion: SCHEMA_VERSION,
    id: options.id,
    name: options.name,
    fur: options.fur,
    stage: "egg",
    adultForm: null,
    bornAt: nowMs,
    hatchedAt: null,
    ageMs: 0,
    lastTickAt: nowMs,
    stepCount: 0,
    readyToHatch: false,
    needs: { ...HATCH_NEEDS },
    health: START_HEALTH,
    careScore: START_CARE_SCORE,
    mood: "waiting",
    asleep: false,
    sick: false,
    sickSince: null,
    messes: 0,
    diedAt: null,
    deathCause: null,
    events: [],
  };
  pushEvent(state, [], "created", `A ${options.fur} drabbit egg appears.`);
  return state;
}

function stageForAge(ageMs: number): Stage {
  if (ageMs >= STAGE_START_AGE_MS.adult) return "adult";
  if (ageMs >= STAGE_START_AGE_MS.teen) return "teen";
  if (ageMs >= STAGE_START_AGE_MS.child) return "child";
  return "baby";
}

export function adultFormForCare(careScore: number): AdultForm {
  if (careScore >= ADULT_FORM_RADIANT_AT) return "radiant";
  if (careScore >= ADULT_FORM_CONTENT_AT) return "content";
  return "scruffy";
}

type LivingStage = "baby" | "child" | "teen" | "adult";

/** Advance one fixed step. Mutates the (already cloned) state. */
function stepOnce(s: PetState, sink: PetEvent[]): void {
  s.stepCount += 1;
  s.lastTickAt += STEP_MS;
  const t = s.lastTickAt;

  if (s.stage === "egg") {
    if (!s.readyToHatch && t - s.bornAt >= EGG_INCUBATION_MS) {
      s.readyToHatch = true;
      pushEvent(s, sink, "egg_ready", "The egg is wiggling — ready to hatch!");
    }
    return;
  }

  // Post-hatch stages only from here (dead is handled by advance()).
  s.ageMs = t - (s.hatchedAt ?? t);
  const rates = DECAY_PER_MIN[s.stage as LivingStage];
  const n = s.needs;

  if (s.asleep) {
    n.energy = clampNeed(n.energy + ASLEEP_ENERGY_REGEN_PER_MIN);
    n.hunger = clampNeed(n.hunger - rates.hunger * ASLEEP_DECAY_FACTOR);
    n.happiness = clampNeed(n.happiness - rates.happiness * ASLEEP_DECAY_FACTOR);
    n.cleanliness = clampNeed(n.cleanliness - rates.cleanliness * ASLEEP_DECAY_FACTOR);
    if (n.energy >= AUTO_WAKE_ENERGY) {
      s.asleep = false;
      pushEvent(s, sink, "woke", "Wakes up fully rested.");
    }
  } else {
    n.hunger = clampNeed(n.hunger - rates.hunger);
    n.happiness = clampNeed(n.happiness - rates.happiness);
    n.energy = clampNeed(n.energy - rates.energy);
    n.cleanliness = clampNeed(n.cleanliness - rates.cleanliness);
    if (n.energy <= AUTO_SLEEP_ENERGY) {
      s.asleep = true;
      pushEvent(s, sink, "fell_asleep", "Collapses into sleep, exhausted.");
    }
  }

  if (s.sick) {
    n.happiness = clampNeed(n.happiness - SICK_HAPPINESS_DECAY_PER_MIN);
  }

  // Mess roll — awake pets only.
  if (!s.asleep) {
    const chance =
      MESS_CHANCE_PER_MIN *
      (n.hunger >= MESS_FULL_BELLY_HUNGER ? MESS_FULL_BELLY_MULTIPLIER : 1);
    if (stepRoll(s.id, s.stepCount, ROLL_MESS) < chance) {
      s.messes += 1;
      n.cleanliness = clampNeed(n.cleanliness - MESS_CLEANLINESS_HIT);
      pushEvent(s, sink, "mess", "Made a mess.");
    }
  }

  // Sickness roll.
  const atRisk =
    n.hunger <= 0 || n.cleanliness < SICK_CLEANLINESS_BELOW || s.messes >= SICK_MESSES_AT_LEAST;
  if (!s.sick && atRisk && stepRoll(s.id, s.stepCount, ROLL_SICK) < SICK_CHANCE_PER_MIN) {
    s.sick = true;
    s.sickSince = t;
    pushEvent(s, sink, "sick", "Has fallen sick.");
  }

  // Health integration.
  let dh = 0;
  if (n.hunger <= 0) dh += HEALTH_STARVING_PER_MIN;
  if (n.cleanliness <= 0) dh += HEALTH_FILTHY_PER_MIN;
  if (s.sick) dh += HEALTH_SICK_PER_MIN;
  if (!s.sick && n.hunger > RECOVERY_MIN_HUNGER && n.cleanliness > RECOVERY_MIN_CLEANLINESS) {
    dh += HEALTH_RECOVERY_PER_MIN;
  }
  s.health = clampNeed(s.health + dh);

  // Care-score drift.
  const values = [n.hunger, n.happiness, n.energy, n.cleanliness];
  if (values.some((v) => v <= 0)) {
    s.careScore = clampNeed(s.careScore + CARE_ZERO_NEED_PER_MIN);
  } else if (values.some((v) => v < CARE_LOW_NEED_BELOW)) {
    s.careScore = clampNeed(s.careScore + CARE_LOW_NEED_PER_MIN);
  } else if (values.every((v) => v >= CARE_ALL_GOOD_AT_LEAST)) {
    s.careScore = clampNeed(s.careScore + CARE_ALL_GOOD_PER_MIN);
  }

  // Death.
  if (s.health <= 0) {
    s.stage = "dead";
    s.diedAt = t;
    s.deathCause = s.sick ? "sickness" : values.some((v) => v <= 0) ? "neglect" : "failing health";
    pushEvent(s, sink, "died", `Died of ${s.deathCause}.`);
    return;
  }

  // Stage transitions by age.
  const next = stageForAge(s.ageMs);
  if (next !== s.stage) {
    s.stage = next;
    pushEvent(s, sink, "stage", `Reached the ${next} stage.`);
    if (next === "adult") {
      s.adultForm = adultFormForCare(s.careScore);
      pushEvent(s, sink, "adult_form", `Adult form: ${s.adultForm}.`);
    }
  }
}

/**
 * Advance the simulation to `nowMs` in fixed 1-minute steps.
 * Pure: the input state is not mutated. Sub-step remainders are kept —
 * `lastTickAt` only moves in whole steps, so chunked and single advances
 * through the same timestamps agree exactly, events included.
 * A `nowMs` at or before `lastTickAt` is a no-op.
 */
export function advance(input: PetState, nowMs: number): AdvanceResult {
  const s = cloneState(input);
  const events: PetEvent[] = [];
  if (s.stage === "dead") {
    if (nowMs > s.lastTickAt) s.lastTickAt = nowMs;
    return { state: s, events };
  }
  while (s.lastTickAt + STEP_MS <= nowMs) {
    stepOnce(s, events);
    if ((s.stage as Stage) === "dead") {
      // stepOnce may have killed the pet; nothing more can happen.
      s.lastTickAt = nowMs; // park the clock
      break;
    }
  }
  s.mood = deriveMood(s);
  return { state: s, events };
}
