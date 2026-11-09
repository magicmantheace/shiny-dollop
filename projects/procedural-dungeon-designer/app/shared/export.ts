// Versioned export/import for dungeon maps.
//
// Export envelope (formatVersion "1.0.0"):
// {
//   "format": "procedural-dungeon-designer/map",
//   "formatVersion": "1.0.0",
//   "name": "<saved dungeon name>",
//   "map": { ...DungeonMap }
// }
// The bytes are deterministic: stableStringify sorts object keys
// recursively and the envelope carries no timestamps, so exporting the
// same map under the same name always yields byte-identical output.
// This envelope is the manifest other tools (e.g. AI Dungeon Master)
// can consume; see docs/IMPLEMENTATION_STATUS.md.

import { PDD_ERROR_CODES, pddError } from './errors.js';
import { computeBudgetUsed } from './generator.js';
import type { DungeonMap, SavedDungeon } from './types.js';

export const EXPORT_FORMAT = 'procedural-dungeon-designer/map';
export const EXPORT_FORMAT_VERSION = '1.0.0';
export const MAX_IMPORT_CHARS = 1_000_000;

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

export interface ExportEnvelope {
  format: string;
  formatVersion: string;
  name: string;
  map: DungeonMap;
}

export function buildExport(saved: SavedDungeon): string {
  const envelope: ExportEnvelope = {
    format: EXPORT_FORMAT,
    formatVersion: EXPORT_FORMAT_VERSION,
    name: saved.name,
    map: saved.map,
  };
  return stableStringify(envelope);
}

export function parseExport(text: string): { name: string; map: DungeonMap } {
  if (text.length > MAX_IMPORT_CHARS) {
    throw pddError(
      PDD_ERROR_CODES.INPUT_TOO_LARGE,
      `Import is ${text.length} characters; the limit is ${MAX_IMPORT_CHARS}.`,
    );
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw pddError(PDD_ERROR_CODES.IMPORT_INVALID, 'Import is not valid JSON.');
  }
  if (typeof parsed !== 'object' || parsed === null) {
    throw pddError(PDD_ERROR_CODES.IMPORT_INVALID, 'Import must be a JSON object.');
  }
  const env = parsed as Partial<ExportEnvelope>;
  if (env.format !== EXPORT_FORMAT) {
    throw pddError(
      PDD_ERROR_CODES.IMPORT_INVALID,
      `Import format must be "${EXPORT_FORMAT}".`,
    );
  }
  if (typeof env.formatVersion !== 'string') {
    throw pddError(PDD_ERROR_CODES.IMPORT_INVALID, 'Import is missing formatVersion.');
  }
  const major = env.formatVersion.split('.')[0];
  if (major !== '1') {
    throw pddError(
      PDD_ERROR_CODES.IMPORT_VERSION_UNSUPPORTED,
      `Unsupported format version "${env.formatVersion}"; this build reads 1.x exports.`,
    );
  }
  if (typeof env.name !== 'string' || env.name.trim().length === 0) {
    throw pddError(PDD_ERROR_CODES.IMPORT_INVALID, 'Import is missing a dungeon name.');
  }
  const map = env.map as DungeonMap | undefined;
  if (
    !map ||
    typeof map !== 'object' ||
    !Array.isArray(map.tiles) ||
    !Array.isArray(map.rooms) ||
    typeof map.gridWidth !== 'number' ||
    typeof map.gridHeight !== 'number' ||
    typeof map.budgetLimit !== 'number' ||
    typeof map.params !== 'object' ||
    map.params === null
  ) {
    throw pddError(PDD_ERROR_CODES.IMPORT_INVALID, 'Import map is missing or malformed.');
  }
  // Never trust a stored budgetUsed: recompute it from the placements.
  const fixed: DungeonMap = { ...map, budgetUsed: computeBudgetUsed(map) };
  return { name: env.name, map: fixed };
}

/** Human-readable Markdown rendering of a saved dungeon, incl. ASCII map. */
export function buildMarkdown(saved: SavedDungeon): string {
  const { map } = saved;
  const lines: string[] = [];
  lines.push(`# ${saved.name}`);
  lines.push('');
  lines.push(`- Seed: \`${map.params.seed}\``);
  lines.push(`- Theme: ${map.params.theme}`);
  lines.push(`- Grid: ${map.gridWidth} x ${map.gridHeight}`);
  lines.push(`- Difficulty: ${map.params.difficulty}`);
  lines.push(`- Budget: ${map.budgetUsed} / ${map.budgetLimit} points`);
  lines.push('');
  lines.push('## Map');
  lines.push('');
  lines.push('```text');
  lines.push(...map.tiles);
  lines.push('```');
  lines.push('');
  lines.push('Legend: `#` wall, `.` room floor, `+` corridor.');
  lines.push('');
  lines.push('## Rooms');
  for (const room of map.rooms) {
    lines.push('');
    lines.push(
      `### ${room.name} (\`${room.id}\`)${room.isEntrance ? ' — Entrance' : ''}`,
    );
    lines.push(
      `Tiles x=${room.x}..${room.x + room.w - 1}, y=${room.y}..${room.y + room.h - 1}; center (${room.cx}, ${room.cy}).`,
    );
    if (room.placements.length === 0) {
      lines.push('No placements.');
    } else {
      for (const p of room.placements) {
        lines.push(`- ${p.kind}: ${p.name} (cost ${p.cost})`);
      }
    }
  }
  lines.push('');
  return lines.join('\n');
}
