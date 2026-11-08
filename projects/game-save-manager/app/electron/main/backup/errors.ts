/**
 * Backup-engine error codes. Every error thrown by the engine carries one of
 * these so the UI can show actionable messages instead of raw exceptions.
 */
export const BackupErrorCodes = {
  GAME_NOT_FOUND: 'GAME_NOT_FOUND',
  SAVE_DIR_MISSING: 'SAVE_DIR_MISSING',
  BACKUP_NOT_FOUND: 'BACKUP_NOT_FOUND',
  BACKUP_DIR_MISSING: 'BACKUP_DIR_MISSING',
  RESTORE_NOT_CONFIRMED: 'RESTORE_NOT_CONFIRMED',
  /**
   * The pre-restore safety backup had to skip files (locked, unreadable…).
   * The escape hatch must never be incomplete, so the restore aborts before
   * any writes.
   */
  SAFETY_BACKUP_INCOMPLETE: 'SAFETY_BACKUP_INCOMPLETE',
  /**
   * A file changed between the hash phase and the copy phase: the bytes
   * written to the backup do not match the recorded checksum. The backup is
   * discarded and no DB row is recorded.
   */
  BACKUP_COPY_MISMATCH: 'BACKUP_COPY_MISMATCH',
  /**
   * The registered save folder and the backup storage folder overlap (one
   * contains the other). Walking the save folder would include previous
   * backups, so every new snapshot would swallow all earlier ones and grow
   * without bound. Rejected before anything is walked or written.
   */
  BACKUP_DESTINATION_OVERLAPS_SAVE_DIR: 'BACKUP_DESTINATION_OVERLAPS_SAVE_DIR',
} as const;

export type BackupErrorCode = (typeof BackupErrorCodes)[keyof typeof BackupErrorCodes];

export class BackupError extends Error {
  readonly code: BackupErrorCode;
  constructor(code: BackupErrorCode, message: string) {
    super(message);
    this.name = 'BackupError';
    this.code = code;
  }
}
