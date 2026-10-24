// Named error codes for the Procedural Dungeon Designer.
// Every IPC failure carries { code, message } so the UI can act on it.

export const PDD_ERROR_CODES = {
  PARAMS_INVALID: 'PARAMS_INVALID',
  INPUT_TOO_LARGE: 'INPUT_TOO_LARGE',
  GENERATION_FAILED: 'GENERATION_FAILED',
  DUNGEON_NOT_FOUND: 'DUNGEON_NOT_FOUND',
  DUNGEON_INVALID: 'DUNGEON_INVALID',
  ROOM_NOT_FOUND: 'ROOM_NOT_FOUND',
  PLACEMENT_NOT_FOUND: 'PLACEMENT_NOT_FOUND',
  PLACEMENT_UNKNOWN: 'PLACEMENT_UNKNOWN',
  BUDGET_EXCEEDED: 'BUDGET_EXCEEDED',
  IMPORT_INVALID: 'IMPORT_INVALID',
  IMPORT_VERSION_UNSUPPORTED: 'IMPORT_VERSION_UNSUPPORTED',
} as const;

export type PddErrorCode =
  (typeof PDD_ERROR_CODES)[keyof typeof PDD_ERROR_CODES];

export interface PddError {
  code: PddErrorCode;
  message: string;
}

export function pddError(code: PddErrorCode, message: string): PddError {
  return { code, message };
}

export function isPddError(value: unknown): value is PddError {
  return (
    typeof value === 'object' &&
    value !== null &&
    'code' in value &&
    'message' in value &&
    typeof (value as PddError).code === 'string' &&
    typeof (value as PddError).message === 'string' &&
    Object.values(PDD_ERROR_CODES).includes(
      (value as PddError).code as PddErrorCode,
    )
  );
}
