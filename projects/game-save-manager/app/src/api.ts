import type { IpcResult } from '../shared/types';

/**
 * Unwraps the uniform IPC envelope. Throws a typed error carrying the
 * backend's error code so the UI can render actionable messages.
 */
export class IpcError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'IpcError';
    this.code = code;
  }
}

export function unwrap<T>(result: IpcResult<T>): T {
  if (result.ok) {
    return result.data;
  }
  throw new IpcError(result.error.code, result.error.message);
}
