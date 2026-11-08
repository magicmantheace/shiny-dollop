// Named error codes for the Local AI Command Center.
// Every IPC failure carries { code, message } so the UI can act on it.

export const LACC_ERROR_CODES = {
  CONFIG_INVALID: 'CONFIG_INVALID',
  CONFIG_NOT_FOUND: 'CONFIG_NOT_FOUND',
  ENDPOINT_NOT_CONFIGURED: 'ENDPOINT_NOT_CONFIGURED',
  ENDPOINT_UNREACHABLE: 'ENDPOINT_UNREACHABLE',
  ENDPOINT_TIMEOUT: 'ENDPOINT_TIMEOUT',
  ENDPOINT_INVALID_RESPONSE: 'ENDPOINT_INVALID_RESPONSE',
  ADAPTER_ERROR: 'ADAPTER_ERROR',
  TASK_NOT_FOUND: 'TASK_NOT_FOUND',
  TASK_INVALID: 'TASK_INVALID',
  TASK_NOT_CANCELLABLE: 'TASK_NOT_CANCELLABLE',
  INPUT_TOO_LARGE: 'INPUT_TOO_LARGE',
  MODEL_NOT_AVAILABLE: 'MODEL_NOT_AVAILABLE',
  PATH_OUTSIDE_WORKSPACE: 'PATH_OUTSIDE_WORKSPACE',
  PROPOSAL_NOT_FOUND: 'PROPOSAL_NOT_FOUND',
  PROPOSAL_NOT_PENDING: 'PROPOSAL_NOT_PENDING',
  PROPOSAL_INVALID: 'PROPOSAL_INVALID',
  PROPOSAL_FILE_CHANGED: 'PROPOSAL_FILE_CHANGED',
} as const;

export type LaccErrorCode =
  (typeof LACC_ERROR_CODES)[keyof typeof LACC_ERROR_CODES];

export interface LaccError {
  code: LaccErrorCode;
  message: string;
}

export function laccError(code: LaccErrorCode, message: string): LaccError {
  return { code, message };
}

/**
 * Structured IPC transport envelope. Electron's ipcMain.handle cannot carry
 * a thrown { code, message } object to the renderer — only the message
 * survives — so handlers RETURN this envelope as data and the preload
 * unwraps it (throwing `error` on failure), preserving the named code.
 */
export type IpcResult<T> =
  | { ok: true; value: T }
  | { ok: false; error: LaccError };

export function isLaccError(value: unknown): value is LaccError {
  return (
    typeof value === 'object' &&
    value !== null &&
    'code' in value &&
    'message' in value &&
    typeof (value as LaccError).code === 'string' &&
    typeof (value as LaccError).message === 'string' &&
    Object.values(LACC_ERROR_CODES).includes(
      (value as LaccError).code as LaccErrorCode,
    )
  );
}
