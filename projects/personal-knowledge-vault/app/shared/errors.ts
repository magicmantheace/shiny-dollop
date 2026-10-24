/**
 * Named error codes for the Personal Knowledge Vault backend.
 * Every failure surfaced over IPC carries one of these codes so the
 * renderer can react programmatically.
 */
export const PkvErrorCode = {
  /** zod payload validation failed. */
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  /** Referenced note does not exist. */
  NOTE_NOT_FOUND: 'NOTE_NOT_FOUND',
  /** reject() called with an empty/missing reason. */
  REJECT_REASON_REQUIRED: 'REJECT_REASON_REQUIRED',
  /** update() called without a change summary. */
  CHANGE_SUMMARY_REQUIRED: 'CHANGE_SUMMARY_REQUIRED',
  /** Status transition not allowed (e.g. approve a non-candidate). */
  INVALID_STATUS_TRANSITION: 'INVALID_STATUS_TRANSITION',
  /** Link target note does not exist. */
  LINK_TARGET_NOT_FOUND: 'LINK_TARGET_NOT_FOUND',
  /** A note cannot link to itself. */
  SELF_LINK_NOT_ALLOWED: 'SELF_LINK_NOT_ALLOWED',
  /** Source provided but has none of url / docPointer / title. */
  SOURCE_ANCHOR_REQUIRED: 'SOURCE_ANCHOR_REQUIRED',
  /** Backup payload is not valid JSON. */
  BACKUP_CORRUPT: 'BACKUP_CORRUPT',
  /** Backup formatVersion has an unsupported major version. */
  BACKUP_VERSION_UNSUPPORTED: 'BACKUP_VERSION_UNSUPPORTED',
  /** Backup payload fails schema/shape validation. */
  BACKUP_IMPORT_INVALID: 'BACKUP_IMPORT_INVALID',
  /** Unexpected internal failure. */
  INTERNAL_ERROR: 'INTERNAL_ERROR',
} as const;

export type PkvErrorCode = (typeof PkvErrorCode)[keyof typeof PkvErrorCode];

/** Error carrying a machine-readable PkvErrorCode. */
export class PkvError extends Error {
  readonly code: PkvErrorCode;

  constructor(code: PkvErrorCode, message: string) {
    super(message);
    this.name = 'PkvError';
    this.code = code;
  }
}
