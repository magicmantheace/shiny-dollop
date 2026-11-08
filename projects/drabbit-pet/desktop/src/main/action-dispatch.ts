import { PetError } from 'drabbit-core';
import type { ActionKind, ActionOutcome, IpcResult } from '../shared/api-types.js';
import type { PetService } from './pet-service.js';

/**
 * The one action dispatcher, shared by every front door to the pet:
 * the IPC handlers (care panel) and the companion HTTP server (P3).
 * Same validation upstream, same error codes downstream — a rejected
 * action means the same thing no matter which door it came through.
 *
 * Core `PetError`s become `{ ok: false, error }` results carrying the
 * core's typed code; nothing throws across the boundary.
 */
export function dispatchAction(service: PetService, kind: ActionKind): IpcResult<ActionOutcome> {
  try {
    return { ok: true, data: service.doAction(kind) };
  } catch (err) {
    if (err instanceof PetError) {
      return { ok: false, error: { code: err.code, message: err.message } };
    }
    return {
      ok: false,
      error: { code: 'internal', message: err instanceof Error ? err.message : String(err) },
    };
  }
}
