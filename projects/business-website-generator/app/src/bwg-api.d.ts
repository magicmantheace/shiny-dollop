/**
 * Renderer-side declaration of the backend bridge.
 *
 * The preload script (owned by Worker A) exposes the flat `BwgApi`
 * defined in the canonical `../shared/types` as `window.bwg` through a
 * context-isolated bridge. This declaration is the single source of truth
 * for the renderer; tests install a hermetic mock of the same interface
 * (see `tests/renderer/mock-bwg.ts`) and never touch the real backend.
 */
import type { BwgApi } from '../shared/types';

declare global {
  interface Window {
    bwg: BwgApi;
  }
}

export {};
