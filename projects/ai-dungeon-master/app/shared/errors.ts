// Named error codes for the AI Dungeon Master.
// Every IPC failure carries { code, message } so the UI can act on it.

export const AIDM_ERROR_CODES = {
  INPUT_INVALID: 'INPUT_INVALID',
  INPUT_TOO_LARGE: 'INPUT_TOO_LARGE',
  CAMPAIGN_NOT_FOUND: 'CAMPAIGN_NOT_FOUND',
  SESSION_NOT_FOUND: 'SESSION_NOT_FOUND',
  CHARACTER_NOT_FOUND: 'CHARACTER_NOT_FOUND',
  ENCOUNTER_NOT_FOUND: 'ENCOUNTER_NOT_FOUND',
  ENCOUNTER_NOT_ACTIVE: 'ENCOUNTER_NOT_ACTIVE',
  MEMORY_NOT_FOUND: 'MEMORY_NOT_FOUND',
  LOG_ENTRY_NOT_FOUND: 'LOG_ENTRY_NOT_FOUND',
  DICE_NOTATION_INVALID: 'DICE_NOTATION_INVALID',
  IMPORT_INVALID: 'IMPORT_INVALID',
  IMPORT_VERSION_UNSUPPORTED: 'IMPORT_VERSION_UNSUPPORTED',
  NARRATION_UNAVAILABLE: 'NARRATION_UNAVAILABLE',
} as const;

export type AidmErrorCode =
  (typeof AIDM_ERROR_CODES)[keyof typeof AIDM_ERROR_CODES];

export interface AidmError {
  code: AidmErrorCode;
  message: string;
}

/**
 * Structured result returned by every Electron IPC handler. Failures are
 * resolved as data rather than thrown across the IPC bridge, where Electron
 * would serialize a thrown plain object as `[object Object]` and lose the
 * actionable code/message. The preload unwraps this envelope for callers.
 */
export type AidmIpcResult<T> =
  | { ok: true; value: T }
  | { ok: false; error: AidmError };

export function aidmError(code: AidmErrorCode, message: string): AidmError {
  return { code, message };
}

export function isAidmError(value: unknown): value is AidmError {
  return (
    typeof value === 'object' &&
    value !== null &&
    'code' in value &&
    'message' in value &&
    typeof (value as AidmError).code === 'string' &&
    typeof (value as AidmError).message === 'string' &&
    Object.values(AIDM_ERROR_CODES).includes(
      (value as AidmError).code as AidmErrorCode,
    )
  );
}
