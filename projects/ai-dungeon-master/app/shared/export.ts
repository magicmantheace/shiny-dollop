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

export function parseCampaignBundle(text: string): CampaignBundle {
  const env = parseJsonObject(text, 'Campaign import');
  checkFormat(env, CAMPAIGN_FORMAT, 'Campaign import');
  const campaign = env.campaign;
  if (!isRecord(campaign) || typeof campaign.id !== 'string' || typeof campaign.name !== 'string') {
    throw aidmError(AIDM_ERROR_CODES.IMPORT_INVALID, 'Campaign import has no valid campaign record.');
  }
  for (const key of ['sessions', 'characters', 'encounters', 'memory', 'log'] as const) {
    requireArray(env, key, 'Campaign import');
  }
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
