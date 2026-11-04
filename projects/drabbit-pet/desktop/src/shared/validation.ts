import { ACTION_KINDS, type ActionKind } from './api-types.js';

/**
 * Hand-rolled IPC payload validation (no schema library at the
 * boundary — payloads are tiny and the checks are explicit).
 */

export interface ValidationFailure {
  code: string;
  message: string;
}

export type ValidationResult<T> = { ok: true; value: T } | { ok: false; error: ValidationFailure };

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

export function isActionKind(v: unknown): v is ActionKind {
  return typeof v === 'string' && (ACTION_KINDS as readonly string[]).includes(v);
}

/** Validate a `pet:action` payload: `{ kind: <ActionKind> }`. */
export function parseActionPayload(payload: unknown): ValidationResult<{ kind: ActionKind }> {
  if (!isRecord(payload)) {
    return { ok: false, error: { code: 'bad_payload', message: 'Action payload must be an object.' } };
  }
  if (!isActionKind(payload.kind)) {
    return {
      ok: false,
      error: {
        code: 'bad_payload',
        message: `Unknown action kind: ${JSON.stringify(payload.kind) ?? 'undefined'}.`,
      },
    };
  }
  return { ok: true, value: { kind: payload.kind } };
}

/** Validate a `companion:setEnabled` payload: `{ enabled: boolean }`. */
export function parseSetEnabledPayload(payload: unknown): ValidationResult<{ enabled: boolean }> {
  if (!isRecord(payload) || typeof payload.enabled !== 'boolean') {
    return {
      ok: false,
      error: { code: 'bad_payload', message: 'Payload must be an object with a boolean "enabled".' },
    };
  }
  return { ok: true, value: { enabled: payload.enabled } };
}
