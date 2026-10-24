import type { WbmApi } from './shared/types';

declare global {
  interface Window {
    wbm: WbmApi;
  }
}

export {};
