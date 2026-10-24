import type { DabApi } from '../../shared/types';

// Note: the `window.dab` global itself is declared in app/dab-api.d.ts
// (backend-owned). This module only wraps access to it.

/**
 * Typed accessor for the preload bridge. Throws a human-readable error when
 * the renderer is opened outside the Electron shell (e.g. plain browser).
 */
export function getDab(): DabApi {
  if (typeof window === 'undefined' || !window.dab) {
    throw new Error(
      'Desktop Automation Builder backend API (window.dab) is unavailable. ' +
        'Open this UI inside the Desktop Automation Builder app.',
    );
  }
  return window.dab;
}

export function dabErrorMessage(err: unknown): string {
  if (err && typeof err === 'object') {
    const e = err as { code?: unknown; message?: unknown };
    if (typeof e.message === 'string' && e.message.length > 0) {
      return typeof e.code === 'string' && e.code.length > 0
        ? `${e.message} (${e.code})`
        : e.message;
    }
  }
  return String(err);
}
