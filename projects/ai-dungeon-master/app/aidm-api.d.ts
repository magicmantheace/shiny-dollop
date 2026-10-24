import type { AidmApi } from './shared/types';

declare global {
  interface Window {
    aidm: AidmApi;
  }
}

export {};
