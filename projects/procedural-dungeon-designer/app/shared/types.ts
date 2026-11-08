// Shared domain contract for the Procedural Dungeon Designer.
// The renderer only ever sees these types via the flat `window.pdd` API
// (PddApi below); the main process validates every input with zod before
// it reaches the generator, store or export code. The generator library
// in this folder is pure and deterministic: no Math.random(), no Date.

export type ThemeId = 'sunken-crypt' | 'ember-deep';

export type PlacementKind = 'encounter' | 'trap' | 'hazard' | 'treasure';

export interface GenParams {
  /** Free-text seed; any non-empty string up to 64 chars. */
  seed: string;
  /** Grid width in tiles, 12..60. */
  gridWidth: number;
  /** Grid height in tiles, 12..48. */
  gridHeight: number;
  /** Target room count, 3..40. The generator places as many as fit. */
  roomCount: number;
  theme: ThemeId;
  /** Difficulty 1..5; scales the placement budget. */
  difficulty: number;
}

export interface Placement {
  /** Deterministic id within the map, e.g. "p1", "p2", ... */
  id: string;
  kind: PlacementKind;
  /** Key into the theme table for the kind, e.g. "pale-warden". */
  key: string;
  /** Display name copied from the theme table at placement time. */
  name: string;
  /** Budget cost copied from the theme table at placement time. */
  cost: number;
}

export interface Room {
  /** Deterministic id, e.g. "room-1" (placement order). */
  id: string;
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
  /** Center tile — corridors connect room centers. */
  cx: number;
  cy: number;
  isEntrance: boolean;
  placements: Placement[];
}

export interface DungeonMap {
  params: GenParams;
  gridWidth: number;
  gridHeight: number;
  /** One string per row. '#'=wall, '.'=room floor, '+'=corridor floor. */
  tiles: string[];
  rooms: Room[];
  /** Total placement budget allowed for this map. */
  budgetLimit: number;
  /** Sum of placement costs currently on the map. */
  budgetUsed: number;
}

export interface SavedDungeon {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  map: DungeonMap;
}

export interface DungeonSummary {
  id: string;
  name: string;
  seed: string;
  theme: ThemeId;
  roomCount: number;
  budgetUsed: number;
  budgetLimit: number;
  updatedAt: string;
}

export interface ThemePalette {
  wall: string;
  floor: string;
  corridor: string;
  entrance: string;
  accent: string;
  text: string;
}

export interface TableEntry {
  key: string;
  name: string;
  cost: number;
}

export interface ThemeInfo {
  id: ThemeId;
  name: string;
  tagline: string;
  palette: ThemePalette;
  roomNamePrefixes: string[];
  roomNameNouns: string[];
  tables: Record<PlacementKind, TableEntry[]>;
}

export interface ValidationResult {
  /** True when every room is reachable from the entrance over floor tiles. */
  connected: boolean;
  roomCount: number;
  reachableRoomCount: number;
  unreachableRoomIds: string[];
  budgetUsed: number;
  budgetLimit: number;
  overBudget: boolean;
  valid: boolean;
}

export interface PlacementOp {
  roomId: string;
  kind: PlacementKind;
  key: string;
}

export interface PddApi {
  themesList: () => Promise<ThemeInfo[]>;
  generate: (params: GenParams) => Promise<DungeonMap>;
  validateMap: (map: DungeonMap) => Promise<ValidationResult>;
  dungeonsSave: (input: { name: string; map: DungeonMap }) => Promise<SavedDungeon>;
  dungeonsList: () => Promise<DungeonSummary[]>;
  dungeonsGet: (id: string) => Promise<SavedDungeon>;
  dungeonsDelete: (id: string) => Promise<void>;
  placementsAdd: (dungeonId: string, op: PlacementOp) => Promise<SavedDungeon>;
  placementsRemove: (dungeonId: string, placementId: string) => Promise<SavedDungeon>;
  placementsMove: (dungeonId: string, placementId: string, toRoomId: string) => Promise<SavedDungeon>;
  exportJson: (dungeonId: string) => Promise<string>;
  exportMarkdown: (dungeonId: string) => Promise<string>;
  importJson: (text: string) => Promise<SavedDungeon>;
}
