import type { BwgApi } from '../shared/types';

/**
 * Returns the backend bridge. Throws a descriptive error when the preload
 * script has not installed it (dev without Electron, broken preload, …).
 */
export function getApi(): BwgApi {
  const api = (window as unknown as { bwg?: BwgApi }).bwg;
  if (!api) {
    throw new Error(
      'window.bwg is not available. Run inside the Electron shell, or install a mock in tests.',
    );
  }
  return api;
}

/** Format an ISO timestamp for display in the dashboard list. */
export function formatUpdatedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}
