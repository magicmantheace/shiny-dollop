/**
 * Renderer-side declaration of the saveManager bridge injected by the preload.
 * The preload's own declaration lives in the preload tsconfig; this one is for
 * the renderer build. The type itself is the source of truth in shared/types.
 */
import type { SaveManagerApi } from '../shared/types';

declare global {
  interface Window {
    saveManager: SaveManagerApi;
  }
}

export {};
