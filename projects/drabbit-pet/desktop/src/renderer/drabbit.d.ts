import type { DrabbitApi } from '../shared/api-types.js';

declare global {
  interface Window {
    drabbit: DrabbitApi;
  }
}

export {};
