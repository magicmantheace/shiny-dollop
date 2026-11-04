import type { AdultForm, FurVariant, Mood, Needs, PetEvent, Stage } from 'drabbit-core';

export type { PetEvent };

/**
 * The presentation subset of the pet state, safe to send over IPC and
 * (from P3) over the companion wire protocol. The full PetState —
 * event internals, step counters — stays in the main process.
 */
export interface PetSummary {
  id: string;
  name: string;
  fur: FurVariant;
  stage: Stage;
  adultForm: AdultForm | null;
  mood: Mood;
  needs: Needs;
  health: number;
  careScore: number;
  /** Simulated ms since hatch (0 while an egg). */
  ageMs: number;
  asleep: boolean;
  sick: boolean;
  messes: number;
  readyToHatch: boolean;
  /** Lineage generation of this pet (1 = first of its line). */
  generation: number;
  deathCause: string | null;
}

/** Care actions as the UI names them; mapped to core actions in main. */
export type ActionKind =
  | 'feed-meal'
  | 'feed-snack'
  | 'play'
  | 'clean'
  | 'sleep'
  | 'wake'
  | 'medicine'
  | 'hatch'
  | 'new-egg';

export const ACTION_KINDS: readonly ActionKind[] = [
  'feed-meal',
  'feed-snack',
  'play',
  'clean',
  'sleep',
  'wake',
  'medicine',
  'hatch',
  'new-egg',
];

export interface ActionOutcome {
  summary: PetSummary;
  /** Events produced by the advance + the action itself. */
  events: PetEvent[];
}

/** Payload of the `pet:changed` push. */
export interface ChangedEvent {
  summary: PetSummary;
  /** New events produced by the tick/action that caused the change. */
  events: PetEvent[];
}

/** Payload of the `pet:roamState` push. */
export interface RoamState {
  hopping: boolean;
}

/** Every invoke handler returns this envelope (repo app pattern). */
export type IpcResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string } };

/** Live counters from the companion server (main-process memory only). */
export interface CompanionServerStats {
  /** ms epoch when the server started listening. */
  startedAt: number;
  /** All /v1/* requests seen, authenticated or not. */
  requestCount: number;
  authFailures: number;
  /** Remote address of the most recent /v1/* request, if any. */
  lastClient: string | null;
}

export type CompanionStatus = 'off' | 'on' | 'error';

/** Everything the care panel's Companion section renders. */
export interface CompanionState {
  /** The persisted master switch in companion.json. */
  enabled: boolean;
  status: CompanionStatus;
  host: string;
  port: number;
  /** `http://<host>:<port>` while running; null otherwise. */
  url: string | null;
  /** Bind/start failure detail while status is 'error'. */
  error: string | null;
  /** The pairing token ('' until first generated). The panel masks it. */
  token: string;
  stats: CompanionServerStats | null;
}

/** The typed API the preload exposes as `window.drabbit`. */
export interface DrabbitApi {
  getSummary(): Promise<PetSummary>;
  /** Most recent events (oldest first), capped by the main process. */
  getEvents(): Promise<PetEvent[]>;
  action(kind: ActionKind): Promise<ActionOutcome>;
  openPanel(): Promise<void>;
  /** Subscribe to state changes. Returns an unsubscribe function. */
  onChanged(cb: (e: ChangedEvent) => void): () => void;
  /** Subscribe to roaming (hop) state flips. Returns an unsubscribe fn. */
  onRoamState(cb: (s: RoamState) => void): () => void;
  // Companion server (P3)
  getCompanionState(): Promise<CompanionState>;
  setCompanionEnabled(enabled: boolean): Promise<CompanionState>;
  regenerateCompanionToken(): Promise<CompanionState>;
}
