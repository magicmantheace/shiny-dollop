// DungeonService: the whole PddApi surface over a SQLite store.
// Every failure is a PddError ({ code, message }) from shared/errors —
// plain generator Errors are wrapped, never leaked across the boundary.
import { randomUUID } from 'node:crypto';
import type { DatabaseSync } from 'node:sqlite';
import { PDD_ERROR_CODES, isPddError, pddError } from '../../shared/errors.js';
import { buildExport, buildMarkdown, parseExport } from '../../shared/export.js';
import { computeBudgetUsed, generateDungeon } from '../../shared/generator.js';
import { addPlacement, movePlacement, removePlacement } from '../../shared/placements.js';
import { THEMES } from '../../shared/themes.js';
import type {
  DungeonMap,
  DungeonSummary,
  GenParams,
  PddApi,
  PlacementOp,
  SavedDungeon,
  ThemeInfo,
  ValidationResult,
} from '../../shared/types.js';
import { validateDungeon } from '../../shared/validate.js';
import { dungeonMapSchema, genParamsSchema, placementOpSchema } from './schemas.js';
import {
  deleteDungeon as storeDeleteDungeon,
  getDungeon as storeGetDungeon,
  insertDungeon,
  listDungeons,
  updateDungeon,
} from './store.js';

function issueSummary(issues: Array<{ message: string }>): string {
  return issues.map((i) => i.message).join('; ');
}

export class DungeonService implements PddApi {
  private readonly db: DatabaseSync;

  constructor(db: DatabaseSync) {
    this.db = db;
  }

  async themesList(): Promise<ThemeInfo[]> {
    return [...THEMES];
  }

  async generate(params: GenParams): Promise<DungeonMap> {
    const parsed = genParamsSchema.safeParse(params);
    if (!parsed.success) {
      throw pddError(
        PDD_ERROR_CODES.PARAMS_INVALID,
        `Invalid generation parameters: ${issueSummary(parsed.error.issues)}`,
      );
    }
    let map: DungeonMap;
    try {
      map = generateDungeon(parsed.data);
    } catch (err) {
      if (isPddError(err)) throw err;
      throw pddError(
        PDD_ERROR_CODES.GENERATION_FAILED,
        err instanceof Error ? err.message : String(err),
      );
    }
    // Defense in depth: the generator connects by construction, but the
    // independent validator must agree before a map leaves the service.
    const validation = validateDungeon(map);
    if (!validation.connected) {
      throw pddError(
        PDD_ERROR_CODES.GENERATION_FAILED,
        `Generated map is not connected; unreachable rooms: ${validation.unreachableRoomIds.join(', ') || 'unknown'}.`,
      );
    }
    return map;
  }

  async validateMap(map: DungeonMap): Promise<ValidationResult> {
    const parsed = dungeonMapSchema.safeParse(map);
    if (!parsed.success) {
      throw pddError(
        PDD_ERROR_CODES.DUNGEON_INVALID,
        `Invalid dungeon map: ${issueSummary(parsed.error.issues)}`,
      );
    }
    return validateDungeon(parsed.data as DungeonMap);
  }

  async dungeonsSave(input: { name: string; map: DungeonMap }): Promise<SavedDungeon> {
    // Validate the name with the same bound the IPC schema enforces,
    // then validate the map structurally via dungeonMapSchema.
    const name = typeof input?.name === 'string' ? input.name.trim() : '';
    if (name.length < 1 || name.length > 120) {
      throw pddError(
        PDD_ERROR_CODES.DUNGEON_INVALID,
        'Dungeon name must be between 1 and 120 characters.',
      );
    }
    const parsed = dungeonMapSchema.safeParse(input?.map);
    if (!parsed.success) {
      throw pddError(
        PDD_ERROR_CODES.DUNGEON_INVALID,
        `Invalid dungeon map: ${issueSummary(parsed.error.issues)}`,
      );
    }
    // Never trust the caller's budgetUsed: recompute from placements.
    const budgetUsed = computeBudgetUsed(parsed.data as DungeonMap);
    const map: DungeonMap = { ...(parsed.data as DungeonMap), budgetUsed };
    if (budgetUsed > map.budgetLimit) {
      throw pddError(
        PDD_ERROR_CODES.BUDGET_EXCEEDED,
        `Placements cost ${budgetUsed} points, over the budget limit of ${map.budgetLimit}.`,
      );
    }
    const validation = validateDungeon(map);
    if (!validation.connected) {
      throw pddError(
        PDD_ERROR_CODES.DUNGEON_INVALID,
        `Dungeon is not connected; unreachable rooms: ${validation.unreachableRoomIds.join(', ') || 'none listed'}.`,
      );
    }
    const now = new Date().toISOString();
    const saved: SavedDungeon = {
      id: randomUUID(),
      name,
      createdAt: now,
      updatedAt: now,
      map,
    };
    insertDungeon(this.db, saved);
    return saved;
  }

  async dungeonsList(): Promise<DungeonSummary[]> {
    return listDungeons(this.db).map((saved) => ({
      id: saved.id,
      name: saved.name,
      seed: saved.map.params.seed,
      theme: saved.map.params.theme,
      roomCount: saved.map.rooms.length,
      budgetUsed: saved.map.budgetUsed,
      budgetLimit: saved.map.budgetLimit,
      updatedAt: saved.updatedAt,
    }));
  }

  async dungeonsGet(id: string): Promise<SavedDungeon> {
    return this.requireSaved(id);
  }

  async dungeonsDelete(id: string): Promise<void> {
    const deleted = typeof id === 'string' && storeDeleteDungeon(this.db, id);
    if (!deleted) {
      throw pddError(PDD_ERROR_CODES.DUNGEON_NOT_FOUND, `Dungeon not found: ${String(id)}`);
    }
  }

  async placementsAdd(dungeonId: string, op: PlacementOp): Promise<SavedDungeon> {
    const saved = this.requireSaved(dungeonId);
    const parsedOp = placementOpSchema.safeParse(op);
    if (!parsedOp.success) {
      throw pddError(
        PDD_ERROR_CODES.PARAMS_INVALID,
        `Invalid placement operation: ${issueSummary(parsedOp.error.issues)}`,
      );
    }
    // Shared pure op: its PddErrors (unknown key, budget, room) propagate.
    const map = addPlacement(saved.map, parsedOp.data.roomId, parsedOp.data.kind, parsedOp.data.key);
    return this.persistMap(saved, map);
  }

  async placementsRemove(dungeonId: string, placementId: string): Promise<SavedDungeon> {
    const saved = this.requireSaved(dungeonId);
    const map = removePlacement(saved.map, placementId);
    return this.persistMap(saved, map);
  }

  async placementsMove(
    dungeonId: string,
    placementId: string,
    toRoomId: string,
  ): Promise<SavedDungeon> {
    const saved = this.requireSaved(dungeonId);
    const map = movePlacement(saved.map, placementId, toRoomId);
    return this.persistMap(saved, map);
  }

  async exportJson(dungeonId: string): Promise<string> {
    return buildExport(this.requireSaved(dungeonId));
  }

  async exportMarkdown(dungeonId: string): Promise<string> {
    return buildMarkdown(this.requireSaved(dungeonId));
  }

  async importJson(text: string): Promise<SavedDungeon> {
    if (typeof text !== 'string') {
      throw pddError(PDD_ERROR_CODES.IMPORT_INVALID, 'Import must be a JSON string.');
    }
    let parsed: { name: string; map: DungeonMap };
    try {
      // parseExport enforces the size limit, envelope format and version.
      parsed = parseExport(text);
    } catch (err) {
      if (isPddError(err)) throw err;
      throw pddError(
        PDD_ERROR_CODES.IMPORT_INVALID,
        err instanceof Error ? err.message : String(err),
      );
    }
    const structural = dungeonMapSchema.safeParse(parsed.map);
    if (!structural.success) {
      throw pddError(
        PDD_ERROR_CODES.IMPORT_INVALID,
        `Imported map is malformed: ${issueSummary(structural.error.issues)}`,
      );
    }
    const map: DungeonMap = {
      ...(structural.data as DungeonMap),
      budgetUsed: computeBudgetUsed(structural.data as DungeonMap),
    };
    if (map.rooms.length > 0) {
      const validation = validateDungeon(map);
      if (!validation.connected) {
        throw pddError(
          PDD_ERROR_CODES.IMPORT_INVALID,
          `Imported dungeon is not connected; unreachable rooms: ${validation.unreachableRoomIds.join(', ')}.`,
        );
      }
    }
    const now = new Date().toISOString();
    const saved: SavedDungeon = {
      id: randomUUID(),
      name: parsed.name,
      createdAt: now,
      updatedAt: now,
      map,
    };
    insertDungeon(this.db, saved);
    return saved;
  }

  private requireSaved(id: string): SavedDungeon {
    const saved = typeof id === 'string' ? storeGetDungeon(this.db, id) : null;
    if (!saved) {
      throw pddError(PDD_ERROR_CODES.DUNGEON_NOT_FOUND, `Dungeon not found: ${String(id)}`);
    }
    return saved;
  }

  private persistMap(saved: SavedDungeon, map: DungeonMap): SavedDungeon {
    const updated: SavedDungeon = {
      ...saved,
      map,
      updatedAt: new Date().toISOString(),
    };
    if (!updateDungeon(this.db, updated)) {
      throw pddError(PDD_ERROR_CODES.DUNGEON_NOT_FOUND, `Dungeon not found: ${saved.id}`);
    }
    return updated;
  }
}
