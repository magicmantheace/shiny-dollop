/** Typed application errors with stable codes for the UI. */
export class OpsError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'OpsError';
    this.code = code;
  }
}

export const OpsErrorCodes = {
  NOT_FOUND: 'NOT_FOUND',
  INVALID_STATE: 'INVALID_STATE',
  VALIDATION: 'VALIDATION',
  REFERENCED: 'REFERENCED',
  INSUFFICIENT_STOCK: 'INSUFFICIENT_STOCK',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  IO_ERROR: 'IO_ERROR',
  RESTORE_INVALID: 'RESTORE_INVALID',
} as const;
