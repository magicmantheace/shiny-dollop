import type { SpectatorApi } from './shared/types';

declare global {
  interface Window {
    spectator: SpectatorApi;
  }
}

export {};
