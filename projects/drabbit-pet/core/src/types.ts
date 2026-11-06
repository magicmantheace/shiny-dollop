// Plain-JSON types for the drabbit pet brain. No behaviour lives here.

export const SCHEMA_VERSION = 1;

export type Stage = "egg" | "baby" | "child" | "teen" | "adult" | "dead";

export type AdultForm = "radiant" | "content" | "scruffy";

export type FurVariant = "ember" | "meadow" | "royal" | "sky" | "sunset" | "rainbow";

export type Mood =
  | "waiting"
  | "joyful"
  | "content"
  | "okay"
  | "unhappy"
  | "miserable"
  | "frail"
  | "sick"
  | "asleep"
  | "gone";

export interface Needs {
  hunger: number;
  happiness: number;
  energy: number;
  cleanliness: number;
}

export interface PetEvent {
  /** Simulated timestamp (ms) at which the event occurred. */
  t: number;
  kind: string;
  detail: string;
}

export interface PetState {
  schemaVersion: number;
  id: string;
  name: string;
  fur: FurVariant;
  stage: Stage;
  /** Fixed at the teen→adult transition; null before that. */
  adultForm: AdultForm | null;
  /** When the egg was created. */
  bornAt: number;
  /** When the egg hatched; null while still an egg. */
  hatchedAt: number | null;
  /** Simulated ms since hatch (0 while an egg). */
  ageMs: number;
  /** The sim has advanced up to this timestamp, in whole steps. */
  lastTickAt: number;
  /** Total 1-minute steps advanced since creation; seeds the RNG. */
  stepCount: number;
  readyToHatch: boolean;
  needs: Needs;
  health: number;
  careScore: number;
  /** Derived after every advance/action; see mood.ts. */
  mood: Mood;
  asleep: boolean;
  sick: boolean;
  sickSince: number | null;
  messes: number;
  diedAt: number | null;
  deathCause: string | null;
  /** Append-only, capped at EVENT_CAP (oldest dropped). */
  events: PetEvent[];
}

export interface AncestorRecord {
  name: string;
  fur: FurVariant;
  adultForm: AdultForm | null;
  bornAt: number;
  diedAt: number | null;
  deathCause: string | null;
}

export interface Lineage {
  generation: number;
  ancestors: AncestorRecord[];
}

export interface SaveEnvelope {
  schemaVersion: number;
  pet: PetState;
  lineage: Lineage;
}

export interface CreatePetOptions {
  id: string;
  name: string;
  fur: FurVariant;
}

export interface AdvanceResult {
  state: PetState;
  /** Events produced by this call (also appended to state.events). */
  events: PetEvent[];
}

/** Typed error for invalid actions and bad saves. */
export class PetError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "PetError";
    this.code = code;
  }
}
