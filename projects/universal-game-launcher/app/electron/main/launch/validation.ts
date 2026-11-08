/**
 * Validation for user-supplied launch targets. Pure logic where possible so it
 * is unit-testable; filesystem checks are isolated in async helpers.
 */
import fs from 'node:fs/promises';
import path from 'node:path';

export class ValidationError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = 'ValidationError';
    this.code = code;
  }
}

/** Reject null bytes and other control characters that have no business in a path or argument. */
function assertNoControlChars(value: string, what: string): void {
  // eslint-disable-next-line no-control-regex
  if (/[\0-\x1F\x7F]/.test(value)) {
    throw new ValidationError('INVALID_CHARACTERS', `${what} contains invalid control characters.`);
  }
}

/**
 * Resolve a user-supplied path to an absolute normalized path.
 * Throws ValidationError for empty input or embedded null bytes.
 */
export function canonicalizePath(input: string): string {
  if (typeof input !== 'string' || input.trim().length === 0) {
    throw new ValidationError('EMPTY_PATH', 'Path must not be empty.');
  }
  assertNoControlChars(input, 'Path');
  return path.resolve(input);
}

/**
 * Comparison key for duplicate detection. Case-insensitive on Windows,
 * where the filesystem is case-insensitive by default.
 */
export function canonicalKey(input: string, platform: NodeJS.Platform = process.platform): string {
  const canonical = canonicalizePath(input);
  return platform === 'win32' ? canonical.toLowerCase() : canonical;
}

/** Display title default: file name without extension. */
export function defaultTitleFor(exePath: string): string {
  const base = path.basename(exePath);
  const ext = path.extname(base);
  const name = ext ? base.slice(0, -ext.length) : base;
  return name.trim() || base;
}

const MAX_ARGS = 64;
const MAX_ARG_LENGTH = 4096;

/** Validate a structured argv array. Never accepts shell metacharacter tricks silently. */
export function validateArgsArray(args: unknown): string[] {
  if (args === undefined) return [];
  if (!Array.isArray(args)) {
    throw new ValidationError('INVALID_ARGS', 'Launch arguments must be an array of strings.');
  }
  if (args.length > MAX_ARGS) {
    throw new ValidationError('INVALID_ARGS', `Too many launch arguments (max ${MAX_ARGS}).`);
  }
  return args.map((a, i) => {
    if (typeof a !== 'string') {
      throw new ValidationError('INVALID_ARGS', `Launch argument ${i + 1} must be a string.`);
    }
    if (a.length === 0 || a.length > MAX_ARG_LENGTH) {
      throw new ValidationError(
        'INVALID_ARGS',
        `Launch argument ${i + 1} must be 1–${MAX_ARG_LENGTH} characters.`,
      );
    }
    assertNoControlChars(a, `Launch argument ${i + 1}`);
    return a;
  });
}

/** Confirm the path exists and is a regular file. Throws ValidationError otherwise. */
export async function assertExecutableUsable(exePath: string): Promise<void> {
  const canonical = canonicalizePath(exePath);
  let stat: Awaited<ReturnType<typeof fs.stat>>;
  try {
    stat = await fs.stat(canonical);
  } catch {
    throw new ValidationError(
      'FILE_NOT_FOUND',
      `Executable not found: ${canonical}. It may have been moved, renamed or uninstalled.`,
    );
  }
  if (!stat.isFile()) {
    throw new ValidationError('NOT_A_FILE', `Selected path is not a file: ${canonical}.`);
  }
}

/** Confirm the working directory exists and is a directory. */
export async function assertDirectoryUsable(dir: string): Promise<void> {
  const canonical = canonicalizePath(dir);
  let stat: Awaited<ReturnType<typeof fs.stat>>;
  try {
    stat = await fs.stat(canonical);
  } catch {
    throw new ValidationError(
      'WORKDIR_NOT_FOUND',
      `Working directory not found: ${canonical}.`,
    );
  }
  if (!stat.isDirectory()) {
    throw new ValidationError('WORKDIR_NOT_DIR', `Working directory is not a folder: ${canonical}.`);
  }
}
