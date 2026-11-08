import type { PddApi } from './shared/types';

declare global {
  interface Window {
    pdd: PddApi;
  }
}

export {};
