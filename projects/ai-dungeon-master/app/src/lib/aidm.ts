import type { AidmApi } from '../../shared/types';
import { isAidmError } from '../../shared/errors';

// Note: the `window.aidm` global itself is declared in app/aidm-api.d.ts.
// This module only wraps access to it.

/**
 * Typed accessor for the preload bridge. The `window.aidm` lookup happens
 * lazily at call time so tests can install a fake before each render/call.
 * Throws a human-readable error when the renderer is opened outside the
 * Electron shell (e.g. plain browser).
 */
export function api(): AidmApi {
  if (typeof window === 'undefined' || !window.aidm) {
    throw new Error(
      'AI Dungeon Master backend API (window.aidm) is unavailable. ' +
        'Open this UI inside the AI Dungeon Master app.',
    );
  }
  return window.aidm;
}

/** Alias matching the sibling-app naming convention. */
export const aidm = api;

export interface AidmErrorInfo {
  code: string;
  message: string;
}

/** Extract the { code, message } pair from an API failure for display. */
export function aidmErrorInfo(err: unknown): AidmErrorInfo {
  if (isAidmError(err)) {
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

/**
 * Format a thrown value for the error banner. AidmError-shaped failures
 * render as `CODE: message`; plain errors show just their message.
 */
export function formatError(err: unknown): string {
  const info = aidmErrorInfo(err);
  return info.code && info.code !== 'ERROR' ? `${info.code}: ${info.message}` : info.message;
}
