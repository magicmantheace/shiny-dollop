import type { PddApi } from '../../shared/types';
import { isPddError } from '../../shared/errors';

// Note: the `window.pdd` global itself is declared in app/pdd-api.d.ts.
// This module only wraps access to it.

/**
 * Typed accessor for the preload bridge. The `window.pdd` lookup happens
 * lazily at call time so tests can install a fake before each render/call.
 * Throws a human-readable error when the renderer is opened outside the
 * Electron shell (e.g. plain browser).
 */
export function api(): PddApi {
  if (typeof window === 'undefined' || !window.pdd) {
    throw new Error(
      'Procedural Dungeon Designer backend API (window.pdd) is unavailable. ' +
        'Open this UI inside the Procedural Dungeon Designer app.',
    );
  }
  return window.pdd;
}

/** Alias matching the sibling-app naming convention (`lacc()`, etc.). */
export const pdd = api;

export interface PddErrorInfo {
  code: string;
  message: string;
}

/** Extract the { code, message } pair from an API failure for display. */
export function pddErrorInfo(err: unknown): PddErrorInfo {
  if (isPddError(err)) {
    return { code: err.code, message: err.message };
  }
  if (err && typeof err === 'object') {
    const e = err as { code?: unknown; message?: unknown };
    if (typeof e.message === 'string' && e.message.length > 0) {
      return {
        code:
          typeof e.code === 'string' && e.code.length > 0 ? e.code : 'ERROR',
        message: e.message,
      };
    }
  }
  if (err instanceof Error) {
    return { code: 'ERROR', message: err.message };
  }
  return { code: 'ERROR', message: String(err) };
}

/**
 * Format a thrown value for the error banner. PddError-shaped failures and
 * any error carrying a `code` render as `CODE: message`; plain errors show
 * just their message.
 */
export function formatError(err: unknown): string {
  const info = pddErrorInfo(err);
  return info.code && info.code !== 'ERROR'
    ? `${info.code}: ${info.message}`
    : info.message;
}
