import type { WbmApi } from '../shared/types';

let injected: WbmApi | null = null;

/** Test hook: lets UI tests substitute an in-memory API. */
export function setWbmApi(api: WbmApi | null): void {
  injected = api;
}

export function api(): WbmApi {
  if (injected) return injected;
  if (typeof window !== 'undefined' && window.wbm) return window.wbm;
  throw new Error('Worldbuilding API is not available (preload not loaded).');
}
