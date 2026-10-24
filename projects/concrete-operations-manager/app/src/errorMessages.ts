import { IpcError } from './api';

/**
 * Actionable, human-readable messages for backend error codes.
 * Falls back to the backend's own message for unknown codes.
 */
export function friendlyError(err: unknown): string {
  if (err instanceof IpcError) {
    switch (err.code) {
      case 'INVALID_INPUT':
        return `Couldn't save that: ${err.message}`;
      case 'NOT_FOUND':
        return err.message;
      case 'INVALID_STATE':
        return err.message;
      case 'REFERENCED':
        return err.message;
      case 'INSUFFICIENT_STOCK':
        return err.message;
      case 'IO_ERROR':
        return `A file operation failed: ${err.message}`;
      case 'RESTORE_INVALID':
        return `That file can't be restored: ${err.message}`;
      case 'NO_BRIDGE':
        return 'The app bridge is unavailable. Restart the application.';
      default:
        return err.message || 'Something went wrong.';
    }
  }
  if (err instanceof Error) return err.message;
  return String(err);
}
