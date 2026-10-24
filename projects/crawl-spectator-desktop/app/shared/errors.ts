// Named error codes for the spectator client. Every failure the user can hit
// maps to one of these codes with an actionable message.

export type SpectatorErrorCode =
  | 'BASE_URL_INVALID'
  | 'FEED_UNREACHABLE'
  | 'FEED_TIMEOUT'
  | 'FEED_HTTP_ERROR'
  | 'FEED_CONTRACT_INVALID'
  | 'FEED_RESPONSE_TOO_LARGE'
  | 'FEED_NOT_FOUND'
  | 'NOT_CONNECTED'
  | 'PREFS_INVALID'
  | 'PREFS_VERSION_UNSUPPORTED'
  | 'INPUT_INVALID';

export class SpectatorError extends Error {
  readonly code: SpectatorErrorCode;

  constructor(code: SpectatorErrorCode, message: string) {
    super(message);
    this.name = 'SpectatorError';
    this.code = code;
  }
}

export function isSpectatorError(err: unknown): err is SpectatorError {
  return err instanceof SpectatorError;
}

/** Serialize an unknown thrown value into a plain, IPC-safe shape. */
export function errorMessage(err: unknown): string {
  if (isSpectatorError(err)) return `${err.code}: ${err.message}`;
  if (err instanceof Error) return err.message;
  return String(err);
}
