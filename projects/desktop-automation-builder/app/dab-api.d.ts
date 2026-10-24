import type { DabApi } from './shared/types.js';

declare global {
  interface Window {
    dab: DabApi;
  }
}

export {};
