/**
 * Shared IPC contract for the Game Library Metadata Enricher (Worker A / Worker B).
 *
 * Entity types and the IPC channel names below are the single source of truth.
 * The preload script exposes `window.gmm` as a FLAT typed API (see
 * preload/preload.ts `GmmApi`): each method maps 1:1 to one channel —
 *   importRoots -> 'lib:importRoots', list -> 'lib:list', rescan -> 'lib:rescan',
 *   updateGame -> 'game:update', addArtwork -> 'artwork:add',
 *   listArtwork -> 'artwork:list', artworkFileUrl -> 'artwork:fileUrl',
 *   listTags/addTag/removeTag -> 'tags:list'/'tags:add'/'tags:remove',
 *   listCollections/addCollection/removeCollection -> 'collections:list'/'collections:add'/'collections:remove',
 *   exportBundle -> 'bundle:export', importBundle -> 'bundle:import',
 *   listChanges -> 'changes:list', undo -> 'changes:undo'.
 * Main validates all arguments with zod before dispatching to the engine.
 * Return shapes are JSON-serializable.
 */

export interface Game {
  id: string;
  title: string;
  originalTitle: string;
  description: string;
  installPath: string;
  artworkId: string | null;
  tagIds: string[];
  collectionIds: string[];
  /** Computed on demand (lib:rescan) — never persisted. */
  missing: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface Artwork {
  id: string;
  fileName: string;
  /** How the file got here: "file" (picked by user) or "bundle" (imported). */
  provenance: string;
  mime: string;
  addedAt: string;
}

export interface Tag {
  id: string;
  name: string;
}

export interface Collection {
  id: string;
  name: string;
}

export interface ConflictInfo {
  gameId: string;
  /** Which field diverged between local and bundle. */
  field: string;
  localValue: string;
  bundleValue: string;
  /** The winner that was applied. */
  chosen: 'bundle' | 'local';
}

export interface ChangeEntry {
  id: number;
  gameId: string;
  field: string;
  before: string;
  after: string;
  /** ISO-8601 timestamp of the change. */
  at: string;
}

/** JSON bundle exchanged by bundle:export / bundle:import. */
export interface MetadataBundle {
  formatVersion: string;
  exportedAt: string;
  exporter: string;
  games: Game[];
  artwork: Array<{
    id: string;
    provenance: string;
    mime: string;
    dataBase64: string;
  }>;
}

/**
 * Every channel exposed on window.gmm. The preload implements
 * `invoke(channel, ...args)` and main routes it to a zod-validated handler.
 *
 * lib:importRoots(roots: string[]) => { imported: number; skipped: number; games: Game[] }
 * lib:list() => Game[]
 * lib:rescan() => { missingIds: string[] }
 * game:update(gameId: string, patch: { title?: string; description?: string; artworkId?: string|null; tagIds?: string[]; collectionIds?: string[] }) => Game
 * artwork:add(sourcePath: string, provenance: string) => Artwork
 * artwork:list() => Artwork[]
 * artwork:fileUrl(artworkId: string) => string
 * tags:list() => Tag[]
 * tags:add(name: string) => Tag
 * tags:remove(id: string) => void
 * collections:list() => Collection[]
 * collections:add(name: string) => Collection
 * collections:remove(id: string) => void
 * bundle:export() => { json: string }
 * bundle:import(jsonText: string) => { added: number; updated: number; conflicts: ConflictInfo[] }
 * changes:list(gameId: string) => ChangeEntry[]
 * changes:undo() => { reverted: boolean; gameId?: string }
 */
export type GmmChannel =
  | 'lib:importRoots'
  | 'lib:list'
  | 'lib:rescan'
  | 'game:update'
  | 'artwork:add'
  | 'artwork:list'
  | 'artwork:fileUrl'
  | 'tags:list'
  | 'tags:add'
  | 'tags:remove'
  | 'collections:list'
  | 'collections:add'
  | 'collections:remove'
  | 'bundle:export'
  | 'bundle:import'
  | 'changes:list'
  | 'changes:undo';

export const GMM_CHANNELS: GmmChannel[] = [
  'lib:importRoots',
  'lib:list',
  'lib:rescan',
  'game:update',
  'artwork:add',
  'artwork:list',
  'artwork:fileUrl',
  'tags:list',
  'tags:add',
  'tags:remove',
  'collections:list',
  'collections:add',
  'collections:remove',
  'bundle:export',
  'bundle:import',
  'changes:list',
  'changes:undo',
];
