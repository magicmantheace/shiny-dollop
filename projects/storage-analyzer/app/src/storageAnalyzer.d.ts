/// <reference types="vite/client" />
import type { StorageAnalyzerApi } from './types';

declare global {
  interface Window {
    /** Preload-exposed storage analyzer bridge (see src/types.ts). */
    storageAnalyzer: StorageAnalyzerApi;
  }
}

export {};
