/**
 * Maps backend error codes to human-readable, actionable UI messages.
 * The backend's own message is appended when it carries extra detail.
 */

const FRIENDLY: Record<string, { title: string; hint: string }> = {
  GAME_NOT_FOUND: {
    title: 'Game not found',
    hint: 'The game was removed or its entry is stale. Refresh the library.',
  },
  SAVE_DIR_MISSING: {
    title: 'Save folder is missing',
    hint: 'The save folder no longer exists on disk. Check the game is still installed or update the save path.',
  },
  BACKUP_NOT_FOUND: {
    title: 'Backup not found',
    hint: 'That backup record no longer exists. Refresh the backup history.',
  },
  BACKUP_DIR_MISSING: {
    title: 'Backup files are missing',
    hint: 'The backup record exists but its files are gone from disk. The backup cannot be verified or restored.',
  },
  RESTORE_NOT_CONFIRMED: {
    title: 'Restore was not confirmed',
    hint: 'Restores require explicit confirmation. Please confirm the restore dialog again.',
  },
  INVALID_INPUT: {
    title: 'Invalid input',
    hint: 'One of the fields is invalid. Check the values and try again.',
  },
  BACKUP_FAILED: {
    title: 'Backup failed',
    hint: 'The backup could not be completed. See the message for details.',
  },
  INTERNAL_ERROR: {
    title: 'Something went wrong',
    hint: 'An unexpected error occurred. Try again, and restart the app if it persists.',
  },
};

export interface FriendlyError {
  title: string;
  detail: string;
}

/**
 * Builds a readable error summary for an error code + backend message.
 * Unknown codes fall back to the raw message so nothing is ever swallowed.
 */
export function friendlyError(code: string, message?: string): FriendlyError {
  const known = FRIENDLY[code];
  if (known) {
    return {
      title: known.title,
      detail: message && message !== known.title ? `${known.hint} (${message})` : known.hint,
    };
  }
  return {
    title: code ? `Error (${code})` : 'Error',
    detail: message ?? 'An unknown error occurred.',
  };
}

/** Renders a one-line summary suitable for toast bodies. */
export function errorSummary(code: string, message?: string): string {
  const f = friendlyError(code, message);
  return `${f.title}. ${f.detail}`;
}
