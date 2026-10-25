import type { LaccApi } from './shared/types';

declare global {
  interface Window {
    lacc: LaccApi;
  }
}

export {};
