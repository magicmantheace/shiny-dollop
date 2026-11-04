import { vi } from 'vitest';
import type {
  Artwork,
  ChangeEntry,
  Collection,
  ConflictInfo,
  FlatGmmApi,
  Game,
  GamePatch,
  GmmApi,
  ImportRootsResult,
  Tag,
  UndoResult,
} from '../src/gmm';

let seq = 0;
const nid = (prefix: string): string => `${prefix}-${(seq += 1)}`;
const numId = (): number => {
  seq += 1;
  return seq;
};

export function makeGame(overrides: Partial<Game> = {}): Game {
  const id = overrides.id ?? nid('g');
  return {
    id,
    title: `Game ${id}`,
    originalTitle: '',
    description: '',
    installPath: `C:\\Games\\${id}`,
    artworkId: null,
    tagIds: [],
    collectionIds: [],
    missing: false,
    createdAt: '2026-10-23T00:00:00.000Z',
    updatedAt: '2026-10-23T00:00:00.000Z',
    ...overrides,
  };
}

export function makeArtwork(overrides: Partial<Artwork> = {}): Artwork {
  const id = overrides.id ?? nid('a');
  return {
    id,
    fileName: `${id}.png`,
    provenance: 'test fixture',
    mime: 'image/png',
    addedAt: '2026-10-23T00:00:00.000Z',
    ...overrides,
  };
}

export function makeTag(overrides: Partial<Tag> = {}): Tag {
  const id = overrides.id ?? nid('t');
  return { id, name: `Tag ${id}`, ...overrides };
}

export function makeCollection(overrides: Partial<Collection> = {}): Collection {
  const id = overrides.id ?? nid('c');
  return { id, name: `Collection ${id}`, ...overrides };
}

export function makeConflict(overrides: Partial<ConflictInfo> = {}): ConflictInfo {
  return {
    gameId: 'g-1',
    field: 'title',
    localValue: 'Local title',
    bundleValue: 'Bundle title',
    chosen: 'bundle',
    ...overrides,
  };
}

export function makeChange(overrides: Partial<ChangeEntry> = {}): ChangeEntry {
  return {
    id: numId(),
    gameId: 'g-1',
    field: 'title',
    before: 'Old',
    after: 'New',
    at: '2026-10-23T12:00:00.000Z',
    ...overrides,
  };
}

/** Installs a fully-mocked `window.gmm` and returns the mock for assertions. */
export function installGmmMock() {
  const mock = {
    lib: {
      importRoots: vi.fn(
        async (_roots: string[]): Promise<ImportRootsResult> => ({
          imported: 0,
          skipped: 0,
          games: [],
        }),
      ),
      list: vi.fn(async (): Promise<Game[]> => []),
      rescan: vi.fn(async (): Promise<{ missingIds: string[] }> => ({ missingIds: [] })),
    },
    game: {
      update: vi.fn(async (gameId: string, patch: GamePatch): Promise<Game> => {
        const base = makeGame({ id: gameId });
        return {
          ...base,
          title: patch.title ?? base.title,
          description: patch.description ?? base.description,
          artworkId: patch.artworkId !== undefined ? patch.artworkId : base.artworkId,
          tagIds: patch.tagIds ?? base.tagIds,
          collectionIds: patch.collectionIds ?? base.collectionIds,
        };
      }),
    },
    artwork: {
      add: vi.fn(
        async (sourcePath: string, provenance: string): Promise<Artwork> =>
          makeArtwork({ fileName: sourcePath.split(/[\\/]/).pop() ?? sourcePath, provenance }),
      ),
      list: vi.fn(async (): Promise<Artwork[]> => []),
      fileUrl: vi.fn((artworkId: string): string => `file:///artwork-cache/${artworkId}`),
    },
    tags: {
      list: vi.fn(async (): Promise<Tag[]> => []),
      add: vi.fn(async (name: string): Promise<Tag> => makeTag({ name })),
      remove: vi.fn(async (_id: string): Promise<void> => undefined),
    },
    collections: {
      list: vi.fn(async (): Promise<Collection[]> => []),
      add: vi.fn(async (name: string): Promise<Collection> => makeCollection({ name })),
      remove: vi.fn(async (_id: string): Promise<void> => undefined),
    },
    bundle: {
      export: vi.fn(async (): Promise<{ json: string }> => ({ json: '{}' })),
      import: vi.fn(
        async (_jsonText: string): Promise<{ added: number; updated: number; conflicts: ConflictInfo[] }> => ({
          added: 0,
          updated: 0,
          conflicts: [],
        }),
      ),
    },
    changes: {
      list: vi.fn(async (_gameId: string): Promise<ChangeEntry[]> => []),
      undo: vi.fn(async (): Promise<UndoResult> => ({ reverted: false })),
    },
  };
  Object.defineProperty(window, 'gmm', {
    value: mock as unknown as GmmApi,
    configurable: true,
    writable: true,
  });
  return mock;
}

export function uninstallGmmMock(): void {
  delete (window as unknown as Record<string, unknown>).gmm;
}

/**
 * Installs a mock of the FLAT bridge shape actually exposed by
 * app/preload/preload.ts, for adapter tests.
 */
export function installFlatGmmMock() {
  const mock = {
    importRoots: vi.fn(
      async (_roots: string[]): Promise<ImportRootsResult> => ({
        imported: 0,
        skipped: 0,
        games: [],
      }),
    ),
    list: vi.fn(async (): Promise<Game[]> => []),
    rescan: vi.fn(async (): Promise<{ missingIds: string[] }> => ({ missingIds: [] })),
    updateGame: vi.fn(
      async (gameId: string, _patch: GamePatch): Promise<Game> => makeGame({ id: gameId }),
    ),
    addArtwork: vi.fn(
      async (sourcePath: string, _provenance?: string): Promise<Artwork> =>
        makeArtwork({ fileName: sourcePath.split(/[\\/]/).pop() ?? sourcePath }),
    ),
    listArtwork: vi.fn(async (): Promise<Artwork[]> => []),
    artworkFileUrl: vi.fn(
      async (artworkId: string): Promise<string> => `file:///artwork-cache/${artworkId}`,
    ),
    listTags: vi.fn(async (): Promise<Tag[]> => []),
    addTag: vi.fn(async (name: string): Promise<Tag> => makeTag({ name })),
    removeTag: vi.fn(async (_id: string): Promise<void> => undefined),
    listCollections: vi.fn(async (): Promise<Collection[]> => []),
    addCollection: vi.fn(async (name: string): Promise<Collection> => makeCollection({ name })),
    removeCollection: vi.fn(async (_id: string): Promise<void> => undefined),
    exportBundle: vi.fn(async (): Promise<{ json: string }> => ({ json: '{}' })),
    importBundle: vi.fn(
      async (
        _jsonText: string,
      ): Promise<{ added: number; updated: number; conflicts: ConflictInfo[] }> => ({
        added: 0,
        updated: 0,
        conflicts: [],
      }),
    ),
    listChanges: vi.fn(async (_gameId: string): Promise<ChangeEntry[]> => []),
    undo: vi.fn(async (): Promise<UndoResult> => ({ reverted: false })),
  };
  Object.defineProperty(window, 'gmm', {
    value: mock as unknown as FlatGmmApi,
    configurable: true,
    writable: true,
  });
  return mock;
}
