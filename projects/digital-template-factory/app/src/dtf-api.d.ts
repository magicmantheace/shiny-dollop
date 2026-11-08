/**
 * Renderer-side declaration of the backend bridge.
 *
 * The preload script (owned by Worker A) exposes the flat-ish `DtfApi`
 * defined in `../shared/types` as `window.dtf`. This declaration keeps a
 * single source of truth: the shape in `shared/types.ts`.
 */
import type { DtfApi } from '../shared/types';

declare global {
  interface Window {
    dtf: DtfApi;
  }
}

export {};
