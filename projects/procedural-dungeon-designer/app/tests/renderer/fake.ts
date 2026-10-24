import { PDD_ERROR_CODES, pddError } from '../../shared/errors';
import { buildExport, buildMarkdown, parseExport } from '../../shared/export';
import { generateDungeon } from '../../shared/generator';
import {
  addPlacement,
  movePlacement,
  removePlacement,
} from '../../shared/placements';
import { THEMES } from '../../shared/themes';
import type {
  DungeonSummary,
  GenParams,
  PddApi,
  PlacementOp,
  SavedDungeon,
  ThemeInfo,
} from '../../shared/types';
import { validateDungeon } from '../../shared/validate';

function cloneSaved(saved: SavedDungeon): SavedDungeon {
  return JSON.parse(JSON.stringify(saved)) as SavedDungeon;
}

function cloneMap(map: SavedDungeon['map']): SavedDungeon['map'] {
  return JSON.parse(JSON.stringify(map)) as SavedDungeon['map'];
}

/**
 * In-memory FakePddApi. Generation, validation, placement edits and
 * export/import all delegate to the real shared library, so errors such as
 * BUDGET_EXCEEDED (thrown as PddError objects via shared pddError) are the
 * genuine behaviour, not a stubbed imitation.
 */
export class FakePddApi implements PddApi {
  readonly store = new Map<string, SavedDungeon>();
  readonly calls: string[] = [];
  readonly callArgs: Record<string, unknown[]> = {};
  private nextId = 1;
  private tick = 0;

  private timestamp(): string {
    this.tick += 1;
    return new Date(Date.UTC(2026, 9, 23, 19, 0, this.tick)).toISOString();
  }

  private record(name: string, args: unknown[]): void {
    this.calls.push(name);
    (this.callArgs[name] ??= []).push(args);
  }

  private requireSaved(id: string): SavedDungeon {
    const saved = this.store.get(id);
    if (!saved) {
      throw pddError(
        PDD_ERROR_CODES.DUNGEON_NOT_FOUND,
        `Dungeon not found: ${id}`,
      );
    }
    return saved;
  }

  private persist(name: string, map: SavedDungeon['map']): SavedDungeon {
    const now = this.timestamp();
    const saved: SavedDungeon = {
      id: `saved-${this.nextId++}`,
      name,
      createdAt: now,
      updatedAt: now,
      map: cloneMap(map),
    };
    this.store.set(saved.id, saved);
    return cloneSaved(saved);
  }

  /** Test helper: shrink (or grow) a stored dungeon's budget limit. */
  setBudgetLimit(id: string, limit: number): void {
    const saved = this.requireSaved(id);
    this.store.set(id, {
      ...saved,
      map: { ...saved.map, budgetLimit: limit },
    });
  }

  async themesList(): Promise<ThemeInfo[]> {
    this.record('themesList', []);
    return JSON.parse(JSON.stringify(THEMES)) as ThemeInfo[];
  }

  async generate(params: GenParams) {
    this.record('generate', [params]);
    return generateDungeon(params);
  }

  async validateMap(map: SavedDungeon['map']) {
    this.record('validateMap', [map]);
    return validateDungeon(map);
  }

  async dungeonsSave(input: { name: string; map: SavedDungeon['map'] }) {
    this.record('dungeonsSave', [input]);
    return this.persist(input.name, input.map);
  }

  async dungeonsList(): Promise<DungeonSummary[]> {
    this.record('dungeonsList', []);
    return [...this.store.values()].map((saved) => ({
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

  async dungeonsGet(id: string) {
    this.record('dungeonsGet', [id]);
    return cloneSaved(this.requireSaved(id));
  }

  async dungeonsDelete(id: string) {
    this.record('dungeonsDelete', [id]);
    this.requireSaved(id);
    this.store.delete(id);
  }

  async placementsAdd(dungeonId: string, op: PlacementOp) {
    this.record('placementsAdd', [dungeonId, op]);
    const saved = this.requireSaved(dungeonId);
    const nextMap = addPlacement(saved.map, op.roomId, op.kind, op.key);
    const updated: SavedDungeon = {
      ...saved,
      map: nextMap,
      updatedAt: this.timestamp(),
    };
    this.store.set(dungeonId, updated);
    return cloneSaved(updated);
  }

  async placementsRemove(dungeonId: string, placementId: string) {
    this.record('placementsRemove', [dungeonId, placementId]);
    const saved = this.requireSaved(dungeonId);
    const nextMap = removePlacement(saved.map, placementId);
    const updated: SavedDungeon = {
      ...saved,
      map: nextMap,
      updatedAt: this.timestamp(),
    };
    this.store.set(dungeonId, updated);
    return cloneSaved(updated);
  }

  async placementsMove(
    dungeonId: string,
    placementId: string,
    toRoomId: string,
  ) {
    this.record('placementsMove', [dungeonId, placementId, toRoomId]);
    const saved = this.requireSaved(dungeonId);
    const nextMap = movePlacement(saved.map, placementId, toRoomId);
    const updated: SavedDungeon = {
      ...saved,
      map: nextMap,
      updatedAt: this.timestamp(),
    };
    this.store.set(dungeonId, updated);
    return cloneSaved(updated);
  }

  async exportJson(dungeonId: string) {
    this.record('exportJson', [dungeonId]);
    return buildExport(this.requireSaved(dungeonId));
  }

  async exportMarkdown(dungeonId: string) {
    this.record('exportMarkdown', [dungeonId]);
    return buildMarkdown(this.requireSaved(dungeonId));
  }

  async importJson(text: string) {
    this.record('importJson', [text]);
    const { name, map } = parseExport(text);
    return this.persist(name, map);
  }
}

export interface InstalledFakePdd {
  api: FakePddApi;
  fake: FakePddApi;
  calls: string[];
  callArgs: Record<string, unknown[]>;
  store: Map<string, SavedDungeon>;
  setBudgetLimit: (id: string, limit: number) => void;
}

/** Installs a fresh FakePddApi as `window.pdd` and returns handles to it. */
export function installFakePdd(): InstalledFakePdd {
  const fake = new FakePddApi();
  Object.defineProperty(window, 'pdd', {
    value: fake,
    configurable: true,
    writable: true,
  });
  return {
    api: fake,
    fake,
    calls: fake.calls,
    callArgs: fake.callArgs,
    store: fake.store,
    setBudgetLimit: (id, limit) => fake.setBudgetLimit(id, limit),
  };
}
