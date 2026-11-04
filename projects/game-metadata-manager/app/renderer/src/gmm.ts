import { useEffect, useState } from 'react';

/**
 * Renderer-side view of the `window.gmm` IPC contract.
 *
 * Entity types are imported from the shared contract
 * (`projects/game-metadata-manager/app/shared/ipc-contract.ts`) via the
 * `@shared` alias so the renderer can never drift from it.
 *
 * API SHAPE NOTE (2026-10-23, reconciled): the flat API exposed by the
 * preload script (`gmm.list()`, `gmm.updateGame()`, `gmm.artworkFileUrl()`,
 * …) is canonical — it is implemented, typed and tested end to end. The
 * nested `GmmApi` in this module is a renderer-side facade over that flat
 * bridge; `getGmm()` accepts either shape and `adaptFlatApi()` performs the
 * mapping (both covered by tests in renderer/tests/gmm.test.tsx).
 */

import type {
  Artwork,
  ChangeEntry,
  Collection,
  ConflictInfo,
  Game,
  Tag,
} from '@shared/ipc-contract';

export type { Artwork, ChangeEntry, Collection, ConflictInfo, Game, Tag };

export interface GamePatch {
  title?: string;
  description?: string;
  artworkId?: string | null;
  tagIds?: string[];
  collectionIds?: string[];
}

export interface ImportRootsResult {
  imported: number;
  skipped: number;
  games: Game[];
}

export interface RescanResult {
  missingIds: string[];
}

export interface BundleExportResult {
  json: string;
}

export interface BundleImportResult {
  added: number;
  updated: number;
  conflicts: ConflictInfo[];
}

export interface UndoResult {
  reverted: boolean;
  gameId?: string;
}

/** The flat bridge shape actually exposed by app/preload/preload.ts. */
export interface FlatGmmApi {
  importRoots(roots: string[]): Promise<{ imported: number; skipped: number; games: Game[] }>;
  list(): Promise<Game[]>;
  rescan(): Promise<{ missingIds: string[] }>;
  updateGame(gameId: string, patch: GamePatch): Promise<Game>;
  addArtwork(sourcePath: string, provenance?: string): Promise<Artwork>;
  listArtwork(): Promise<Artwork[]>;
  artworkFileUrl(artworkId: string): Promise<string>;
  listTags(): Promise<Tag[]>;
  addTag(name: string): Promise<Tag>;
  removeTag(id: string): Promise<void>;
  listCollections(): Promise<Collection[]>;
  addCollection(name: string): Promise<Collection>;
  removeCollection(id: string): Promise<void>;
  exportBundle(): Promise<{ json: string }>;
  importBundle(jsonText: string): Promise<{ added: number; updated: number; conflicts: ConflictInfo[] }>;
  listChanges(gameId: string): Promise<ChangeEntry[]>;
  undo(): Promise<{ reverted: boolean; gameId?: string }>;
}

/** The nested `window.gmm` shape from the project spec; what renderer code uses. */
export interface GmmApi {
  lib: {
    importRoots(roots: string[]): Promise<ImportRootsResult>;
    list(): Promise<Game[]>;
    rescan(): Promise<RescanResult>;
  };
  game: {
    update(gameId: string, patch: GamePatch): Promise<Game>;
  };
  artwork: {
    add(sourcePath: string, provenance: string): Promise<Artwork>;
    list(): Promise<Artwork[]>;
    /** May be sync (spec) or async (current preload) — callers must tolerate both. */
    fileUrl(artworkId: string): string | Promise<string>;
  };
  tags: {
    list(): Promise<Tag[]>;
    add(name: string): Promise<Tag>;
    remove(id: string): Promise<void>;
  };
  collections: {
    list(): Promise<Collection[]>;
    add(name: string): Promise<Collection>;
    remove(id: string): Promise<void>;
  };
  bundle: {
    export(): Promise<BundleExportResult>;
    import(jsonText: string): Promise<BundleImportResult>;
  };
  changes: {
    list(gameId: string): Promise<ChangeEntry[]>;
    undo(): Promise<UndoResult>;
  };
}

declare global {
  interface Window {
    gmm: GmmApi | FlatGmmApi;
  }
}

function isNestedApi(raw: unknown): raw is GmmApi {
  if (!raw || typeof raw !== 'object') return false;
  const lib = (raw as { lib?: unknown }).lib;
  return !!lib && typeof (lib as { list?: unknown }).list === 'function';
}

function isFlatApi(raw: unknown): raw is FlatGmmApi {
  if (!raw || typeof raw !== 'object') return false;
  return typeof (raw as { list?: unknown }).list === 'function';
}

/** Wraps Worker A's flat preload bridge in the spec's nested API shape. */
export function adaptFlatApi(flat: FlatGmmApi): GmmApi {
  return {
    lib: {
      importRoots: (roots) => flat.importRoots(roots),
      list: () => flat.list(),
      rescan: () => flat.rescan(),
    },
    game: {
      update: (gameId, patch) => flat.updateGame(gameId, patch),
    },
    artwork: {
      add: (sourcePath, provenance) => flat.addArtwork(sourcePath, provenance),
      list: () => flat.listArtwork(),
      fileUrl: (artworkId) => flat.artworkFileUrl(artworkId),
    },
    tags: {
      list: () => flat.listTags(),
      add: (name) => flat.addTag(name),
      remove: (id) => flat.removeTag(id),
    },
    collections: {
      list: () => flat.listCollections(),
      add: (name) => flat.addCollection(name),
      remove: (id) => flat.removeCollection(id),
    },
    bundle: {
      export: () => flat.exportBundle(),
      import: (jsonText) => flat.importBundle(jsonText),
    },
    changes: {
      list: (gameId) => flat.listChanges(gameId),
      undo: () => flat.undo(),
    },
  };
}

/**
 * Returns the `window.gmm` bridge as the spec's nested API. Accepts the nested
 * shape directly; adapts the flat shape exposed by the current preload.
 * Throws a descriptive error when the UI runs outside the app shell or the
 * bridge has an unrecognized shape.
 */
export function getGmm(): GmmApi {
  const raw: unknown =
    typeof window === 'undefined' ? undefined : (window as { gmm?: unknown }).gmm;
  if (isNestedApi(raw)) return raw;
  if (isFlatApi(raw)) return adaptFlatApi(raw);
  if (!raw) {
    throw new Error('window.gmm is not available. This UI must run inside the app shell.');
  }
  throw new Error('window.gmm has an unrecognized shape; expected the nested or flat API.');
}

/**
 * Resolves an artwork URL for rendering. Tolerates sync and async `fileUrl`
 * implementations and degrades to null (placeholder) on any failure.
 */
export function useArtworkUrl(artworkId: string | null | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!artworkId) {
      setUrl(null);
      return;
    }
    let fileUrl: string | Promise<string>;
    try {
      fileUrl = getGmm().artwork.fileUrl(artworkId);
    } catch {
      setUrl(null);
      return;
    }
    void Promise.resolve(fileUrl).then(
      (u) => {
        if (!cancelled) setUrl(u ?? null);
      },
      () => {
        if (!cancelled) setUrl(null);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [artworkId]);

  return url;
}
