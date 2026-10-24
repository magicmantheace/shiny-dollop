/** Typed application errors with stable codes for the UI. */
export class StorageError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'StorageError';
    this.code = code;
  }
}

export const StorageErrorCodes = {
  VALIDATION: 'VALIDATION',
  SCAN_NOT_FOUND: 'SCAN_NOT_FOUND',
  ROOT_INVALID: 'ROOT_INVALID',
  EXPORT_FAILED: 'EXPORT_FAILED',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
} as const;
