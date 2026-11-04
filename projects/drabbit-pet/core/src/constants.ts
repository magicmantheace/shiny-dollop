// Tuning constants — the implementation of docs/PET_DESIGN.md.
// Doc and code must agree; change both together.

export const STEP_MS = 60_000; // fixed 1-minute simulation step

export const EGG_INCUBATION_MS = 10 * 60_000; // 10 minutes

/** Cumulative age-since-hatch at which each post-baby stage begins. */
export const STAGE_START_AGE_MS = {
  child: 60 * 60_000, // 1 h
  teen: 7 * 60 * 60_000, // 7 h
  adult: 19 * 60 * 60_000, // 19 h
} as const;

export const HATCH_NEEDS = {
  hunger: 80,
  happiness: 80,
  energy: 100,
  cleanliness: 100,
} as const;

export const START_HEALTH = 100;
export const START_CARE_SCORE = 70;

/** Needs decay per minute while awake, by stage (egg/dead: no decay). */
export const DECAY_PER_MIN: Record<
  "baby" | "child" | "teen" | "adult",
  { hunger: number; happiness: number; energy: number; cleanliness: number }
> = {
  baby: { hunger: 0.3, happiness: 0.22, energy: 0.25, cleanliness: 0.1 },
  child: { hunger: 0.22, happiness: 0.16, energy: 0.18, cleanliness: 0.08 },
  teen: { hunger: 0.2, happiness: 0.14, energy: 0.16, cleanliness: 0.07 },
  adult: { hunger: 0.16, happiness: 0.11, energy: 0.13, cleanliness: 0.06 },
};

/** While asleep: energy regens; other needs decay at this fraction. */
export const ASLEEP_ENERGY_REGEN_PER_MIN = 1.5;
export const ASLEEP_DECAY_FACTOR = 0.3;
/** Awake pet at or below this energy falls asleep exhausted. */
export const AUTO_SLEEP_ENERGY = 2;
/** Sleeping pet wakes on its own at this energy. */
export const AUTO_WAKE_ENERGY = 100;

/** Mess rolls (awake, post-hatch). */
export const MESS_CHANCE_PER_MIN = 0.004;
export const MESS_FULL_BELLY_HUNGER = 95;
export const MESS_FULL_BELLY_MULTIPLIER = 3;
export const MESS_CLEANLINESS_HIT = 8;

/** Sickness rolls. At risk while any condition holds. */
export const SICK_CHANCE_PER_MIN = 0.002;
export const SICK_CLEANLINESS_BELOW = 25;
export const SICK_MESSES_AT_LEAST = 3;
export const SICK_HAPPINESS_DECAY_PER_MIN = 0.1;

/** Health integration per minute. */
export const HEALTH_STARVING_PER_MIN = -0.12; // hunger = 0
export const HEALTH_FILTHY_PER_MIN = -0.04; // cleanliness = 0
export const HEALTH_SICK_PER_MIN = -0.08; // sick
export const HEALTH_RECOVERY_PER_MIN = 0.06; // not sick, hunger > 25, cleanliness > 25
export const RECOVERY_MIN_HUNGER = 25;
export const RECOVERY_MIN_CLEANLINESS = 25;

/** Care-score drift per minute. */
export const CARE_ZERO_NEED_PER_MIN = -0.04; // any need at 0
export const CARE_LOW_NEED_PER_MIN = -0.015; // any need < 20 (and none at 0)
export const CARE_LOW_NEED_BELOW = 20;
export const CARE_ALL_GOOD_PER_MIN = 0.01; // all needs >= 50
export const CARE_ALL_GOOD_AT_LEAST = 50;

/** Adult form bands, applied to careScore at the teen→adult transition. */
export const ADULT_FORM_RADIANT_AT = 70;
export const ADULT_FORM_CONTENT_AT = 40;

/** Care actions (see PET_DESIGN §8). */
export const ACTION = {
  meal: { hunger: 35, happiness: 2, cleanliness: -2 },
  mealCareBonus: 1.5, // when hunger < 60 before eating
  snack: { hunger: 8, happiness: 5 },
  snackCareBonus: 0.5, // when hunger < 60 before eating
  careBonusBelowNeed: 60,
  overfedAboveHunger: 90, // meal with hunger > 90
  overfedHealth: -3,
  overfedCare: -1,
  snackFullAtHunger: 90, // snack with hunger >= 90
  snackFullCare: -1,
  play: { happiness: 18, energy: -7, hunger: -3, cleanliness: -2 },
  playMinEnergy: 10,
  playCareBonus: 1.5, // when happiness < 60 before playing
  cleanHappiness: 1,
  cleanCareWithMesses: 2,
  cleanCareDirty: 0.5, // cleanliness < 50, no messes
  cleanCareDirtyBelow: 50,
  medicineHealth: 6,
  medicineHappiness: -2,
  medicineCareBonus: 3,
  sleepCareBonus: 1, // putting to sleep with energy < 30
  sleepCareBonusBelowEnergy: 30,
} as const;

/** The pet's event log keeps at most this many entries. */
export const EVENT_CAP = 500;
