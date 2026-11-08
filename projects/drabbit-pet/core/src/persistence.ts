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

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
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
  if (typeof pet.id !== "string" || typeof pet.name !== "string" || !STAGES.includes(String(pet.stage))) {
    throw new PetError("bad_save", "Save pet record is malformed.");
  }
  if (!isRecord(pet.needs) || typeof pet.needs.hunger !== "number") {
    throw new PetError("bad_save", "Save pet needs are malformed.");
  }
  if (typeof raw.lineage.generation !== "number" || !Array.isArray(raw.lineage.ancestors)) {
    throw new PetError("bad_save", "Save lineage is malformed.");
  }
  return migrate(raw as unknown as SaveEnvelope);
}
