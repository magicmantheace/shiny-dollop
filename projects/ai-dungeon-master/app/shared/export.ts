// Versioned export/import for AI Dungeon Master, plus contract-level
// importers for the two sibling formats this app consumes:
//
//   * Campaign bundle:  { format: "ai-dungeon-master/campaign",
//                         formatVersion: "1.0.0", campaign, sessions,
//                         characters, encounters, memory, log }
//     Byte-deterministic: stableStringify sorts object keys recursively
//     and the envelope carries no export timestamp.
//
//   * Worldbuilding Manager project backup:
//                       { format: "worldbuilding-manager.project",
//                         formatVersion: "1.0.0", entities, links, revisions }
//     Entities of type character/location/faction/event/note become
//     NPC / location / fact memory entries.
//
//   * Procedural Dungeon Designer map manifest:
//                       { format: "procedural-dungeon-designer/map",
//                         formatVersion: "1.0.0", name, map }
//     Becomes a single location memory entry referencing the map.
//
// Unknown major versions are rejected with IMPORT_VERSION_UNSUPPORTED;
// wrong formats and malformed payloads with IMPORT_INVALID.

import { AIDM_ERROR_CODES, aidmError } from './errors.js';
import type { CampaignBundle } from './types.js';

export const CAMPAIGN_FORMAT = 'ai-dungeon-master/campaign';
export const WORLDBUILDING_FORMAT = 'worldbuilding-manager.project';
export const DUNGEON_FORMAT = 'procedural-dungeon-designer/map';
export const FORMAT_VERSION = '1.0.0';
export const MAX_IMPORT_CHARS = 2_000_000;

export function stableStringify(value: unknown): string {
  return JSON.stringify(sortValue(value), null, 2);
}

function sortValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortValue);
  if (value !== null && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const k of Object.keys(value as Record<string, unknown>).sort()) {
      out[k] = sortValue((value as Record<string, unknown>)[k]);
    }
    return out;
  }
  return value;
}

function parseJsonObject(text: string, what: string): Record<string, unknown> {
  if (typeof text !== 'string' || text.length === 0) {
    throw aidmError(AIDM_ERROR_CODES.IMPORT_INVALID, `${what} is empty.`);
  }
  if (text.length > MAX_IMPORT_CHARS) {
    throw aidmError(
      AIDM_ERROR_CODES.INPUT_TOO_LARGE,
      `${what} is ${text.length} characters; the limit is ${MAX_IMPORT_CHARS}.`,
    );
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw aidmError(AIDM_ERROR_CODES.IMPORT_INVALID, `${what} is not valid JSON.`);
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw aidmError(AIDM_ERROR_CODES.IMPORT_INVALID, `${what} must be a JSON object.`);
  }
  return parsed as Record<string, unknown>;
}

function checkFormat(
  env: Record<string, unknown>,
  expectedFormat: string,
  what: string,
): void {
  if (env.format !== expectedFormat) {
    throw aidmError(
      AIDM_ERROR_CODES.IMPORT_INVALID,
      `${what} format must be "${expectedFormat}".`,
    );
  }
  const version = env.formatVersion;
  if (typeof version !== 'string' || version.length === 0) {
    throw aidmError(
      AIDM_ERROR_CODES.IMPORT_INVALID,
      `${what} has no readable formatVersion.`,
    );
  }
  const major = Number(version.split('.')[0]);
  if (!Number.isInteger(major)) {
    throw aidmError(
      AIDM_ERROR_CODES.IMPORT_INVALID,
      `${what} has no readable formatVersion.`,
    );
  }
  if (major !== 1) {
    throw aidmError(
      AIDM_ERROR_CODES.IMPORT_VERSION_UNSUPPORTED,
      `${what} format ${version} is not supported by this version of the app (major version 1 only).`,
    );
  }
}

function requireArray(env: Record<string, unknown>, key: string, what: string): unknown[] {
  const value = env[key];
  if (!Array.isArray(value)) {
    throw aidmError(AIDM_ERROR_CODES.IMPORT_INVALID, `${what} is missing its "${key}" list.`);
  }
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function reqString(obj: Record<string, unknown>, key: string, what: string): string {
  const value = obj[key];
  if (typeof value !== 'string') {
    throw aidmError(AIDM_ERROR_CODES.IMPORT_INVALID, `${what} has a missing or non-string "${key}".`);
  }
  return value;
}

// ---------- campaign bundle ----------

export function buildCampaignBundle(bundle: CampaignBundle): string {
  return stableStringify({ ...bundle, format: CAMPAIGN_FORMAT, formatVersion: FORMAT_VERSION });
}

function invalid(message: string): never {
  throw aidmError(AIDM_ERROR_CODES.IMPORT_INVALID, message);
}

function reqRecord(value: unknown, what: string): Record<string, unknown> {
  if (!isRecord(value)) invalid(`${what} must be an object.`);
  return value as Record<string, unknown>;
}

function reqStr(obj: Record<string, unknown>, key: string, what: string): string {
  const value = obj[key];
  if (typeof value !== 'string') invalid(`${what} has a missing or non-string "${key}".`);
  return value as string;
}

function reqNullableStr(obj: Record<string, unknown>, key: string, what: string): string | null {
  const value = obj[key];
  if (value !== null && typeof value !== 'string') {
    invalid(`${what} has a non-string, non-null "${key}".`);
  }
  return value as string | null;
}

function reqFiniteNum(obj: Record<string, unknown>, key: string, what: string): number {
  const value = obj[key];
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    invalid(`${what} has a missing or non-numeric "${key}".`);
  }
  return value as number;
}

function reqInt(
  obj: Record<string, unknown>,
  key: string,
  what: string,
  min: number,
  max: number,
): number {
  const value = reqFiniteNum(obj, key, what);
  if (!Number.isInteger(value) || value < min || value > max) {
    invalid(`${what} has an out-of-range "${key}" (expected an integer ${min}..${max}).`);
  }
  return value;
}

function reqStrArray(obj: Record<string, unknown>, key: string, what: string): string[] {
  const value = obj[key];
  if (!Array.isArray(value) || value.some((v) => typeof v !== 'string')) {
    invalid(`${what} has a missing or malformed "${key}" list.`);
  }
  return value as string[];
}

function reqEnum<T extends string>(
  obj: Record<string, unknown>,
  key: string,
  what: string,
  allowed: readonly T[],
): T {
  const value = obj[key];
  if (typeof value !== 'string' || !allowed.includes(value as T)) {
    invalid(`${what} has an invalid "${key}".`);
  }
  return value as T;
}

function checkUniqueIds(records: Array<{ id: string }>, what: string): Set<string> {
  const ids = new Set<string>();
  for (const r of records) {
    if (ids.has(r.id)) invalid(`Campaign import has a duplicate ${what} id "${r.id}".`);
    ids.add(r.id);
  }
  return ids;
}

const ATTRIBUTE_KEYS = ['might', 'agility', 'wits', 'spirit'] as const;
const LOG_KINDS = [
  'roll', 'check', 'damage', 'heal', 'note', 'encounter', 'narration', 'import', 'system',
] as const;

function validateRollOutcome(value: unknown, what: string): void {
  const outcome = reqRecord(value, what);
  reqStr(outcome, 'notation', what);
  const spec = reqRecord(outcome.spec, `${what} spec`);
  reqInt(spec, 'count', `${what} spec`, 1, 100_000);
  reqInt(spec, 'sides', `${what} spec`, 2, 100_000);
  reqFiniteNum(spec, 'modifier', `${what} spec`);
  const dice = outcome.dice;
  if (!Array.isArray(dice) || dice.some((d) => typeof d !== 'number' || !Number.isFinite(d))) {
    invalid(`${what} has a malformed "dice" list.`);
  }
  reqFiniteNum(outcome, 'modifier', what);
  reqFiniteNum(outcome, 'total', what);
  reqFiniteNum(outcome, 'stateBefore', what);
  reqFiniteNum(outcome, 'stateAfter', what);
}

/**
 * Validate a campaign bundle completely — every record, field type, and
 * cross-reference — before anything is written to the database. A bundle
 * that merely has the right envelope and array-shaped collections is NOT
 * trusted: e.g. a character with `stats: null` must be rejected here, not
 * persisted and crashed on later by the renderer.
 */
export function parseCampaignBundle(text: string): CampaignBundle {
  const env = parseJsonObject(text, 'Campaign import');
  checkFormat(env, CAMPAIGN_FORMAT, 'Campaign import');

  const campaignRaw = reqRecord(env.campaign, 'Campaign import campaign');
  const campaignId = reqStr(campaignRaw, 'id', 'Campaign');
  if (campaignId.length === 0) invalid('Campaign has an empty "id".');
  reqStr(campaignRaw, 'name', 'Campaign');
  reqStr(campaignRaw, 'setting', 'Campaign');
  reqStr(campaignRaw, 'seed', 'Campaign');
  reqFiniteNum(campaignRaw, 'diceState', 'Campaign');
  reqStr(campaignRaw, 'createdAt', 'Campaign');
  reqStr(campaignRaw, 'updatedAt', 'Campaign');

  const sessionsRaw = requireArray(env, 'sessions', 'Campaign import');
  const charactersRaw = requireArray(env, 'characters', 'Campaign import');
  const encountersRaw = requireArray(env, 'encounters', 'Campaign import');
  const memoryRaw = requireArray(env, 'memory', 'Campaign import');
  const logRaw = requireArray(env, 'log', 'Campaign import');

  const sessions = sessionsRaw.map((item, i) => {
    const what = `Campaign import session #${i + 1}`;
    const s = reqRecord(item, what);
    const id = reqStr(s, 'id', what);
    if (reqStr(s, 'campaignId', what) !== campaignId) {
      invalid(`${what} does not belong to the imported campaign.`);
    }
    reqStr(s, 'title', what);
    reqStr(s, 'notes', what);
    reqStr(s, 'startedAt', what);
    reqNullableStr(s, 'endedAt', what);
    return { id };
  });
  const sessionIds = checkUniqueIds(sessions, 'session');

  const characters = charactersRaw.map((item, i) => {
    const what = `Campaign import character #${i + 1}`;
    const c = reqRecord(item, what);
    const id = reqStr(c, 'id', what);
    if (reqStr(c, 'campaignId', what) !== campaignId) {
      invalid(`${what} does not belong to the imported campaign.`);
    }
    reqEnum(c, 'kind', what, ['pc', 'npc'] as const);
    reqStr(c, 'name', what);
    reqStr(c, 'archetype', what);
    const stats = reqRecord(c.stats, `${what} stats`);
    for (const attr of ATTRIBUTE_KEYS) {
      reqInt(stats, attr, `${what} stats`, -2, 4);
    }
    const hpMax = reqInt(c, 'hpMax', what, 1, 10_000);
    reqInt(c, 'hpCurrent', what, 0, hpMax);
    reqStrArray(c, 'inventory', what);
    reqStr(c, 'notes', what);
    reqStr(c, 'createdAt', what);
    reqStr(c, 'updatedAt', what);
    return { id };
  });
  const characterIds = checkUniqueIds(characters, 'character');

  for (const [i, item] of encountersRaw.entries()) {
    const what = `Campaign import encounter #${i + 1}`;
    const e = reqRecord(item, what);
    reqStr(e, 'id', what);
    if (reqStr(e, 'campaignId', what) !== campaignId) {
      invalid(`${what} does not belong to the imported campaign.`);
    }
    const sessionId = reqNullableStr(e, 'sessionId', what);
    if (sessionId !== null && !sessionIds.has(sessionId)) {
      invalid(`${what} references an unknown session.`);
    }
    reqStr(e, 'name', what);
    const status = reqEnum(e, 'status', what, ['active', 'ended'] as const);
    const combatants = e.combatants;
    if (!Array.isArray(combatants)) invalid(`${what} has a missing "combatants" list.`);
    for (const [j, cb] of combatants.entries()) {
      const cbWhat = `${what} combatant #${j + 1}`;
      const combatant = reqRecord(cb, cbWhat);
      const characterId = reqStr(combatant, 'characterId', cbWhat);
      // An ACTIVE encounter's combatants must all have live character
      // sheets — damage/healing resolves through them. An ENDED encounter
      // is a historical record: charactersDelete legitimately permits
      // deleting a former combatant once the encounter ends, so a missing
      // sheet must not make the campaign's own backup unimportable. The
      // combatant's name/initiative snapshot in the bundle is the record.
      if (status === 'active' && !characterIds.has(characterId)) {
        invalid(`${cbWhat} references an unknown character.`);
      }
      reqStr(combatant, 'name', cbWhat);
      validateRollOutcome(combatant.initiative, `${cbWhat} initiative`);
      reqFiniteNum(combatant, 'initiativeTotal', cbWhat);
    }
    if (combatants.length > 0) {
      reqInt(e, 'turnIndex', what, 0, combatants.length - 1);
    } else {
      reqInt(e, 'turnIndex', what, 0, 0);
    }
    reqInt(e, 'round', what, 1, 1_000_000);
    reqStr(e, 'createdAt', what);
    reqNullableStr(e, 'endedAt', what);
  }
  checkUniqueIds(
    encountersRaw.map((item) => ({ id: (item as Record<string, unknown>).id as string })),
    'encounter',
  );

  for (const [i, item] of memoryRaw.entries()) {
    const what = `Campaign import memory entry #${i + 1}`;
    const m = reqRecord(item, what);
    reqStr(m, 'id', what);
    if (reqStr(m, 'campaignId', what) !== campaignId) {
      invalid(`${what} does not belong to the imported campaign.`);
    }
    reqEnum(m, 'kind', what, ['npc', 'location', 'fact'] as const);
    reqStr(m, 'title', what);
    reqStr(m, 'body', what);
    reqStrArray(m, 'tags', what);
    reqEnum(m, 'source', what, ['manual', 'worldbuilding-import', 'dungeon-import'] as const);
    reqStr(m, 'createdAt', what);
    reqStr(m, 'updatedAt', what);
  }
  checkUniqueIds(
    memoryRaw.map((item) => ({ id: (item as Record<string, unknown>).id as string })),
    'memory entry',
  );

  const seqs = new Set<number>();
  for (const [i, item] of logRaw.entries()) {
    const what = `Campaign import log entry #${i + 1}`;
    const l = reqRecord(item, what);
    reqStr(l, 'id', what);
    if (reqStr(l, 'campaignId', what) !== campaignId) {
      invalid(`${what} does not belong to the imported campaign.`);
    }
    const sessionId = reqNullableStr(l, 'sessionId', what);
    if (sessionId !== null && !sessionIds.has(sessionId)) {
      invalid(`${what} references an unknown session.`);
    }
    const seq = reqInt(l, 'seq', what, 1, Number.MAX_SAFE_INTEGER);
    if (seqs.has(seq)) invalid(`Campaign import has a duplicate log seq ${seq}.`);
    seqs.add(seq);
    reqEnum(l, 'kind', what, LOG_KINDS);
    reqStr(l, 'text', what);
    if (l.detail !== null) reqRecord(l.detail, `${what} detail`);
    reqNullableStr(l, 'narration', what);
    reqNullableStr(l, 'narrationSource', what);
    reqStr(l, 'createdAt', what);
  }
  checkUniqueIds(
    logRaw.map((item) => ({ id: (item as Record<string, unknown>).id as string })),
    'log entry',
  );

  return env as unknown as CampaignBundle;
}

// ---------- worldbuilding import ----------

export interface WorldbuildingEntity {
  id: string;
  type: string;
  name: string;
  role: string;
  description: string;
  body: string;
  tags: string[];
}

export function parseWorldbuildingBackup(text: string): WorldbuildingEntity[] {
  const env = parseJsonObject(text, 'Worldbuilding import');
  checkFormat(env, WORLDBUILDING_FORMAT, 'Worldbuilding import');
  const raw = requireArray(env, 'entities', 'Worldbuilding import');
  const entities: WorldbuildingEntity[] = [];
  for (const item of raw) {
    if (!isRecord(item)) {
      throw aidmError(AIDM_ERROR_CODES.IMPORT_INVALID, 'Worldbuilding import contains a malformed entity.');
    }
    entities.push({
      id: reqString(item, 'id', 'Worldbuilding entity'),
      type: reqString(item, 'type', 'Worldbuilding entity'),
      name: reqString(item, 'name', 'Worldbuilding entity'),
      role: typeof item.role === 'string' ? item.role : '',
      description: typeof item.description === 'string' ? item.description : '',
      body: typeof item.body === 'string' ? item.body : '',
      tags: Array.isArray(item.tags) ? item.tags.filter((t): t is string => typeof t === 'string') : [],
    });
  }
  return entities;
}

/** Map a worldbuilding entity type onto an AIDM memory kind. */
export function worldbuildingMemoryKind(entityType: string): 'npc' | 'location' | 'fact' {
  if (entityType === 'character') return 'npc';
  if (entityType === 'location') return 'location';
  return 'fact';
}

// ---------- dungeon manifest import ----------

export interface DungeonManifestSummary {
  name: string;
  seed: string;
  theme: string;
  roomCount: number;
  rooms: Array<{ name: string; placements: string[] }>;
  budgetUsed: number;
  budgetLimit: number;
}

export function parseDungeonManifest(text: string): DungeonManifestSummary {
  const env = parseJsonObject(text, 'Dungeon manifest import');
  checkFormat(env, DUNGEON_FORMAT, 'Dungeon manifest import');
  const name = reqString(env, 'name', 'Dungeon manifest');
  const map = env.map;
  if (!isRecord(map) || !Array.isArray(map.rooms)) {
    throw aidmError(AIDM_ERROR_CODES.IMPORT_INVALID, 'Dungeon manifest has no valid map.');
  }
  const params = isRecord(map.params) ? map.params : {};
  const rooms = (map.rooms as unknown[]).map((room) => {
    if (!isRecord(room)) {
      throw aidmError(AIDM_ERROR_CODES.IMPORT_INVALID, 'Dungeon manifest contains a malformed room.');
    }
    const placements = Array.isArray(room.placements)
      ? (room.placements as unknown[])
          .filter(isRecord)
          .map((p) => (typeof p.name === 'string' ? p.name : ''))
          .filter((n) => n.length > 0)
      : [];
    return { name: typeof room.name === 'string' ? room.name : 'Unnamed room', placements };
  });
  return {
    name,
    seed: typeof params.seed === 'string' ? params.seed : '',
    theme: typeof params.theme === 'string' ? params.theme : '',
    roomCount: rooms.length,
    rooms,
    budgetUsed: typeof map.budgetUsed === 'number' ? map.budgetUsed : 0,
    budgetLimit: typeof map.budgetLimit === 'number' ? map.budgetLimit : 0,
  };
}

export function dungeonManifestToMemoryBody(summary: DungeonManifestSummary): string {
  const lines: string[] = [
    `Imported dungeon map "${summary.name}" (procedural-dungeon-designer/map v1).`,
    `Seed: ${summary.seed || '—'} · Theme: ${summary.theme || '—'} · Encounter budget: ${summary.budgetUsed}/${summary.budgetLimit}`,
    '',
    'Rooms:',
  ];
  for (const room of summary.rooms) {
    lines.push(
      room.placements.length > 0
        ? `- ${room.name} — placements: ${room.placements.join(', ')}`
        : `- ${room.name}`,
    );
  }
  return lines.join('\n');
}
