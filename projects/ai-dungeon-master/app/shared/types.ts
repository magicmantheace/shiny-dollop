// Shared domain contract for the AI Dungeon Master.
// The renderer only ever sees these types via the flat `window.aidm` API
// (AidmApi below); the main process validates every input with zod before
// it reaches the store or the rules engine.
//
// Foundational rule: the deterministic engine (shared/dice.ts +
// shared/ruleset.ts) is authoritative. Narration is flavor attached to a
// log entry and has no path to rules state.

import type { RollOutcome } from './dice.js';
import type { Attribute, DifficultyKey, Stats } from './ruleset.js';

export type { Attribute, DifficultyKey, Stats };
export type { RollOutcome };

export interface Campaign {
  id: string;
  name: string;
  /** Free-text setting/premise notes. */
  setting: string;
  /** Seed text for this campaign's dice stream. */
  seed: string;
  /** Current PRNG state of the campaign dice stream (auditable). */
  diceState: number;
  createdAt: string;
  updatedAt: string;
}

export interface CampaignInput {
  name: string;
  setting?: string;
  /** Optional explicit seed; a random-looking one is derived when omitted. */
  seed?: string;
}

export interface Session {
  id: string;
  campaignId: string;
  title: string;
  notes: string;
  startedAt: string;
  endedAt: string | null;
}

export type CharacterKind = 'pc' | 'npc';

export interface Character {
  id: string;
  campaignId: string;
  kind: CharacterKind;
  name: string;
  archetype: string;
  stats: Stats;
  hpCurrent: number;
  hpMax: number;
  inventory: string[];
  notes: string;
  createdAt: string;
  updatedAt: string;
}

export interface CharacterInput {
  kind: CharacterKind;
  name: string;
  archetype?: string;
  stats?: Partial<Stats>;
  hpMax?: number;
  hpCurrent?: number;
  inventory?: string[];
  notes?: string;
}

export type CharacterPatch = Partial<CharacterInput>;

export type LogKind =
  | 'roll'
  | 'check'
  | 'damage'
  | 'heal'
  | 'note'
  | 'encounter'
  | 'narration'
  | 'import'
  | 'system';

/**
 * One append-only session-log entry. Entries are never edited or deleted;
 * corrections are new entries. `detail` carries the machine-readable
 * evidence (e.g. a full RollOutcome for kind 'roll'/'check').
 */
export interface LogEntry {
  id: string;
  campaignId: string;
  sessionId: string | null;
  /** Monotonic per-campaign sequence number, starting at 1. */
  seq: number;
  kind: LogKind;
  text: string;
  detail: Record<string, unknown> | null;
  /** Optional narration flavor attached after the fact; never rules data. */
  narration: string | null;
  /** Where the attached narration came from: 'mock' | 'local' | 'mock-fallback'. */
  narrationSource: string | null;
  createdAt: string;
}

export interface RollRequest {
  notation: string;
  label?: string;
  sessionId?: string | null;
}

export interface RollResponse {
  outcome: RollOutcome;
  entry: LogEntry;
}

export interface CheckRequest {
  characterId: string;
  attribute: Attribute;
  difficulty: DifficultyKey;
  sessionId?: string | null;
}

export interface CheckResponse {
  outcome: RollOutcome;
  target: number;
  succeeded: boolean;
  entry: LogEntry;
}

export interface Combatant {
  characterId: string;
  name: string;
  /** Initiative roll breakdown (2d6 + Agility), replayable from the log. */
  initiative: RollOutcome;
  initiativeTotal: number;
}

export interface Encounter {
  id: string;
  campaignId: string;
  sessionId: string | null;
  name: string;
  status: 'active' | 'ended';
  /** Combatants in turn order (initiative total desc, Agility desc, name). */
  combatants: Combatant[];
  /** Index into combatants for whose turn it is. */
  turnIndex: number;
  round: number;
  createdAt: string;
  endedAt: string | null;
}

export interface EncounterStartRequest {
  name: string;
  characterIds: string[];
  sessionId?: string | null;
}

export interface HpChangeRequest {
  characterId: string;
  amount: number;
  note?: string;
}

export type MemoryKind = 'npc' | 'location' | 'fact';

export interface MemoryEntry {
  id: string;
  campaignId: string;
  kind: MemoryKind;
  title: string;
  body: string;
  tags: string[];
  source: 'manual' | 'worldbuilding-import' | 'dungeon-import';
  createdAt: string;
  updatedAt: string;
}

export interface MemoryInput {
  kind: MemoryKind;
  title: string;
  body?: string;
  tags?: string[];
}

export type MemoryPatch = Partial<MemoryInput>;

export interface NarrationSettings {
  /** 'mock' = built-in deterministic narrator (default). 'local' = configured endpoint. */
  narrator: 'mock' | 'local';
  /** Loopback-only base URL, e.g. http://127.0.0.1:11434 — used when narrator is 'local'. */
  endpoint: string;
  model: string;
}

export interface NarrationResponse {
  entry: LogEntry;
  /** 'mock' | 'local' | 'mock-fallback' (endpoint failed; mock text used). */
  source: string;
}

export interface ImportSummary {
  createdMemoryEntries: number;
  detail: string;
}

export interface CampaignBundle {
  format: string;
  formatVersion: string;
  campaign: Campaign;
  sessions: Session[];
  characters: Character[];
  encounters: Encounter[];
  memory: MemoryEntry[];
  log: LogEntry[];
}

export interface AidmApi {
  campaignsList: () => Promise<Campaign[]>;
  campaignsCreate: (input: CampaignInput) => Promise<Campaign>;
  campaignsGet: (id: string) => Promise<Campaign>;
  campaignsDelete: (id: string) => Promise<void>;
  sessionsList: (campaignId: string) => Promise<Session[]>;
  sessionsCreate: (campaignId: string, input: { title: string }) => Promise<Session>;
  sessionsUpdateNotes: (sessionId: string, notes: string) => Promise<Session>;
  sessionsEnd: (sessionId: string) => Promise<Session>;
  charactersList: (campaignId: string) => Promise<Character[]>;
  charactersCreate: (campaignId: string, input: CharacterInput) => Promise<Character>;
  charactersUpdate: (id: string, patch: CharacterPatch) => Promise<Character>;
  charactersDelete: (id: string) => Promise<void>;
  diceRoll: (campaignId: string, req: RollRequest) => Promise<RollResponse>;
  checkRoll: (campaignId: string, req: CheckRequest) => Promise<CheckResponse>;
  logList: (campaignId: string, sessionId?: string | null) => Promise<LogEntry[]>;
  logAddNote: (campaignId: string, text: string, sessionId?: string | null) => Promise<LogEntry>;
  encountersStart: (campaignId: string, req: EncounterStartRequest) => Promise<Encounter>;
  encountersGetActive: (campaignId: string) => Promise<Encounter | null>;
  encountersAdvanceTurn: (encounterId: string) => Promise<Encounter>;
  encountersApplyDamage: (encounterId: string, req: HpChangeRequest) => Promise<Encounter>;
  encountersApplyHeal: (encounterId: string, req: HpChangeRequest) => Promise<Encounter>;
  encountersEnd: (encounterId: string) => Promise<Encounter>;
  memoryList: (campaignId: string) => Promise<MemoryEntry[]>;
  memoryCreate: (campaignId: string, input: MemoryInput) => Promise<MemoryEntry>;
  memoryUpdate: (id: string, patch: MemoryPatch) => Promise<MemoryEntry>;
  memoryDelete: (id: string) => Promise<void>;
  memorySearch: (campaignId: string, query: string) => Promise<MemoryEntry[]>;
  narrate: (logEntryId: string) => Promise<NarrationResponse>;
  settingsGet: () => Promise<NarrationSettings>;
  settingsUpdate: (settings: NarrationSettings) => Promise<NarrationSettings>;
  exportCampaign: (campaignId: string) => Promise<string>;
  importCampaign: (text: string) => Promise<Campaign>;
  importWorldbuilding: (campaignId: string, text: string) => Promise<ImportSummary>;
  importDungeonManifest: (campaignId: string, text: string) => Promise<ImportSummary>;
}
