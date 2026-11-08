import { createEgg } from "./sim.js";
import {
  PetError,
  SCHEMA_VERSION,
  type CreatePetOptions,
  type SaveEnvelope,
} from "./types.js";

export function createSave(options: CreatePetOptions, nowMs: number): SaveEnvelope {
  return {
    schemaVersion: SCHEMA_VERSION,
    pet: createEgg(options, nowMs),
    lineage: { generation: 1, ancestors: [] },
  };
}

/** Canonical JSON: recursively key-sorted, so equal states serialize byte-identically. */
function canonical(value: unknown): string {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value) ?? "null";
  }
  if (Array.isArray(value)) {
    return `[${value.map(canonical).join(",")}]`;
  }
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonical(record[k])}`).join(",")}}`;
}

export function serialize(envelope: SaveEnvelope): string {
  return canonical(envelope);
}

const STAGES = ["egg", "baby", "child", "teen", "adult", "dead"];
const FURS = ["ember", "meadow", "royal", "sky", "sunset", "rainbow"];
const ADULT_FORMS = ["radiant", "content", "scruffy"];
const MOODS = [
  "waiting",
  "joyful",
  "content",
  "okay",
  "unhappy",
  "miserable",
  "frail",
  "sick",
  "asleep",
  "gone",
];

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function isNumOrNull(v: unknown): v is number | null {
  return v === null || isNum(v);
}

function isStrOrNull(v: unknown): v is string | null {
  return v === null || typeof v === "string";
}

/**
 * Migration stub. Version 1 is the only schema that exists; future
 * versions add an entry here keyed by the version they migrate FROM.
 * Unknown newer versions are rejected rather than guessed at.
 */
const MIGRATIONS: Record<number, (env: SaveEnvelope) => SaveEnvelope> = {};

export function migrate(envelope: SaveEnvelope): SaveEnvelope {
  let env = envelope;
  while (env.schemaVersion < SCHEMA_VERSION) {
    const step = MIGRATIONS[env.schemaVersion];
    if (!step) {
      throw new PetError(
        "bad_save",
        `No migration path from schema version ${env.schemaVersion}.`,
      );
    }
    env = step(env);
  }
  return env;
}

export function parse(text: string): SaveEnvelope {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new PetError("bad_save", "Save is not valid JSON.");
  }
  if (!isRecord(raw) || typeof raw.schemaVersion !== "number") {
    throw new PetError("bad_save", "Save is missing a numeric schemaVersion.");
  }
  if (raw.schemaVersion > SCHEMA_VERSION) {
    throw new PetError(
      "bad_save",
      `Save schema version ${raw.schemaVersion} is newer than this build understands (${SCHEMA_VERSION}).`,
    );
  }
  if (!isRecord(raw.pet) || !isRecord(raw.lineage)) {
    throw new PetError("bad_save", "Save is missing pet or lineage.");
  }
  const pet = raw.pet;
  if (
    !isNum(pet.schemaVersion) ||
    typeof pet.id !== "string" ||
    typeof pet.name !== "string" ||
    !FURS.includes(String(pet.fur)) ||
    !STAGES.includes(String(pet.stage)) ||
    !(pet.adultForm === null || ADULT_FORMS.includes(String(pet.adultForm))) ||
    !MOODS.includes(String(pet.mood))
  ) {
    throw new PetError("bad_save", "Save pet record is malformed.");
  }
  if (
    !isNum(pet.bornAt) ||
    !isNumOrNull(pet.hatchedAt) ||
    !isNum(pet.ageMs) ||
    !isNum(pet.lastTickAt) ||
    !isNum(pet.stepCount) ||
    typeof pet.readyToHatch !== "boolean" ||
    !isNum(pet.health) ||
    !isNum(pet.careScore) ||
    typeof pet.asleep !== "boolean" ||
    typeof pet.sick !== "boolean" ||
    !isNumOrNull(pet.sickSince) ||
    !isNum(pet.messes) ||
    !isNumOrNull(pet.diedAt) ||
    !isStrOrNull(pet.deathCause)
  ) {
    throw new PetError("bad_save", "Save pet record is malformed.");
  }
  if (
    !isRecord(pet.needs) ||
    !isNum(pet.needs.hunger) ||
    !isNum(pet.needs.happiness) ||
    !isNum(pet.needs.energy) ||
    !isNum(pet.needs.cleanliness)
  ) {
    throw new PetError("bad_save", "Save pet needs are malformed.");
  }
  // The service reads pet.events unconditionally (its length anchors
  // the event cursor), and the sim appends to it — a save that lost
  // the array, or an entry's fields, must fail here and reach the
  // corrupt-save recovery path instead of crashing the service.
  if (
    !Array.isArray(pet.events) ||
    !pet.events.every(
      (e) =>
        isRecord(e) &&
        isNum(e.t) &&
        typeof e.kind === "string" &&
        typeof e.detail === "string",
    )
  ) {
    throw new PetError("bad_save", "Save pet events are malformed.");
  }
  if (typeof raw.lineage.generation !== "number" || !Array.isArray(raw.lineage.ancestors)) {
    throw new PetError("bad_save", "Save lineage is malformed.");
  }
  if (
    !raw.lineage.ancestors.every(
      (a) =>
        isRecord(a) &&
        typeof a.name === "string" &&
        FURS.includes(String(a.fur)) &&
        (a.adultForm === null || ADULT_FORMS.includes(String(a.adultForm))) &&
        isNum(a.bornAt) &&
        isNumOrNull(a.diedAt) &&
        isStrOrNull(a.deathCause),
    )
  ) {
    throw new PetError("bad_save", "Save lineage is malformed.");
  }
  return migrate(raw as unknown as SaveEnvelope);
}
