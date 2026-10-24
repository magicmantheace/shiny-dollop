/** Named, actionable error codes shared by the engine and IPC layer. */
export class AppError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = 'AppError';
    this.code = code;
  }
}

export const ErrorCodes = {
  Validation: 'VALIDATION_ERROR',
  NotFound: 'ENTITY_NOT_FOUND',
  SelfLink: 'SELF_LINK',
  DuplicateLink: 'DUPLICATE_LINK',
  ImportInvalid: 'IMPORT_INVALID',
  ImportTooLarge: 'IMPORT_TOO_LARGE',
  ImportVersionUnsupported: 'IMPORT_VERSION_UNSUPPORTED',
} as const;
