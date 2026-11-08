import { contextBridge, ipcRenderer } from 'electron';
import type {
  Artwork,
  ChangeEntry,
  Collection,
  ConflictInfo,
  Game,
  Tag,
} from '../shared/ipc-contract.js';

/**
 * Typed window.gmm client. Every method maps 1:1 to a channel declared in
 * shared/ipc-contract.ts; main validates args with zod before dispatching.
 */
export interface GamePatch {
  title?: string;
  description?: string;
  artworkId?: string | null;
  tagIds?: string[];
  collectionIds?: string[];
}

export interface GmmApi {
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

const gmm: GmmApi = {
  importRoots: (roots) => ipcRenderer.invoke('lib:importRoots', { roots }),
  list: () => ipcRenderer.invoke('lib:list', {}),
  rescan: () => ipcRenderer.invoke('lib:rescan', {}),
  updateGame: (gameId, patch) => ipcRenderer.invoke('game:update', { gameId, patch }),
  addArtwork: (sourcePath, provenance = 'file') =>
    ipcRenderer.invoke('artwork:add', { sourcePath, provenance }),
  listArtwork: () => ipcRenderer.invoke('artwork:list', {}),
  artworkFileUrl: (artworkId) => ipcRenderer.invoke('artwork:fileUrl', { artworkId }),
  listTags: () => ipcRenderer.invoke('tags:list', {}),
  addTag: (name) => ipcRenderer.invoke('tags:add', { name }),
  removeTag: (id) => ipcRenderer.invoke('tags:remove', { id }),
  listCollections: () => ipcRenderer.invoke('collections:list', {}),
  addCollection: (name) => ipcRenderer.invoke('collections:add', { name }),
  removeCollection: (id) => ipcRenderer.invoke('collections:remove', { id }),
  exportBundle: () => ipcRenderer.invoke('bundle:export', {}),
  importBundle: (jsonText) => ipcRenderer.invoke('bundle:import', { jsonText }),
  listChanges: (gameId) => ipcRenderer.invoke('changes:list', { gameId }),
  undo: () => ipcRenderer.invoke('changes:undo', {}),
};

contextBridge.exposeInMainWorld('gmm', gmm);

declare global {
  interface Window {
    gmm: GmmApi;
  }
}
