import type { IpcResult, StorageAnalyzerApi } from './types';

/**
 * Typed error carrying the backend's error code so the UI can render
 * actionable messages instead of raw strings.
 */
export class IpcError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'IpcError';
    this.code = code;
  }
}

/**
 * Unwraps the uniform IPC envelope. Throws IpcError on failure.
 */
export function unwrap<T>(result: IpcResult<T>): T {
  if (result.ok) {
    return result.data;
  }
  throw new IpcError(result.error.code, result.error.message);
}

/** The preload-exposed API. In tests this is mocked. */
export function api(): StorageAnalyzerApi {
  const bridge = window.storageAnalyzer;
  if (!bridge) {
    throw new IpcError('NO_BRIDGE', 'The application bridge is not available.');
  }
  return bridge;
}

/**
 * Friendly, actionable message for a scan/result failure. Keeps the raw
 * backend message available for diagnosis but leads with what the user can do.
 */
export function friendlyErrorMessage(err: unknown): string {
  if (err instanceof IpcError) {
    switch (err.code) {
      case 'NO_BRIDGE':
        return 'The app bridge did not load. Restart the application and try again.';
      case 'SCAN_NOT_FOUND':
        return `That scan could not be found. It may have been removed; run a new scan. (${err.message})`;
      case 'PATH_NOT_FOUND':
        return `The selected folder no longer exists. Choose another folder and rescan. (${err.message})`;
      case 'ACCESS_DENIED':
        return `Permission was denied while reading files. Run as administrator or choose a different folder. (${err.message})`;
      case 'EXPORT_FAILED':
        return `The report could not be written. Check the output path and try again. (${err.message})`;
      default:
        return `${err.message} (${err.code})`;
    }
  }
  if (err instanceof Error) {
    return err.message;
  }
  return 'An unexpected error occurred.';
}
