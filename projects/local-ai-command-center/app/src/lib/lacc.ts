import type { LaccApi } from '../../shared/types';
import { isLaccError } from '../../shared/errors';

// Note: the `window.lacc` global itself is declared in app/lacc-api.d.ts.
// This module only wraps access to it.

/**
 * Typed accessor for the preload bridge. Throws a human-readable error when
 * the renderer is opened outside the Electron shell (e.g. plain browser).
 */
export function lacc(): LaccApi {
  if (typeof window === 'undefined' || !window.lacc) {
    throw new Error(
      'Local AI Command Center backend API (window.lacc) is unavailable. ' +
        'Open this UI inside the Local AI Command Center app.',
    );
  }
  return window.lacc;
}

/** Extract the { code, message } pair from an API failure for display. */
export function laccErrorInfo(err: unknown): { code: string; message: string } {
  if (isLaccError(err)) {
    return { code: err.code, message: err.message };
  }
  if (err && typeof err === 'object') {
    const e = err as { code?: unknown; message?: unknown };
    if (typeof e.message === 'string' && e.message.length > 0) {
      return {
        code: typeof e.code === 'string' && e.code.length > 0 ? e.code : 'ERROR',
        message: e.message,
      };
    }
  }
  if (err instanceof Error) {
    return { code: 'ERROR', message: err.message };
  }
  return { code: 'ERROR', message: String(err) };
}

export function laccErrorMessage(err: unknown): string {
  const info = laccErrorInfo(err);
  return `${info.message} (${info.code})`;
}
