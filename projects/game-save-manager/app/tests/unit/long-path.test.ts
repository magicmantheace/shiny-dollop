/**
 * Regression tests for the win32 long-path prefix helper.
 *
 * The conversion is expressed with path.win32 semantics (win32LongPathPrefix)
 * so it can be verified on Linux; real Windows filesystem behaviour remains
 * pending owner validation, as docs/IMPLEMENTATION_STATUS.md records.
 */
import { describe, expect, it } from 'vitest';
import path from 'node:path';
import { win32LongPathPrefix } from '../../electron/main/backup/engine';

describe('win32LongPathPrefix', () => {
  it('converts a long UNC path to the \\\\?\\UNC\\ extended form', () => {
    const unc = `\\\\server\\share\\${'a'.repeat(240)}`;
    expect(unc.length).toBeGreaterThanOrEqual(240);
    const result = win32LongPathPrefix(unc);
    expect(result).toBe(`\\\\?\\UNC\\server\\share\\${'a'.repeat(240)}`);
    // The malformed form the old implementation produced:
    expect(result).not.toBe(`\\\\?\\${unc}`);
    // Cross-check against the platform primitive the finding pointed at.
    expect(result).toBe(path.win32.toNamespacedPath(path.win32.resolve(unc)));
  });

  it('converts a long drive-letter path to the \\\\?\\ extended form', () => {
    const drive = `C:\\saves\\${'b'.repeat(240)}`;
    expect(win32LongPathPrefix(drive)).toBe(`\\\\?\\${drive}`);
  });

  it('leaves short UNC and drive paths unresolved-prefixed (resolved only)', () => {
    expect(win32LongPathPrefix('\\\\server\\share\\saves')).toBe('\\\\server\\share\\saves');
    expect(win32LongPathPrefix('C:\\saves\\game')).toBe('C:\\saves\\game');
  });

  it('leaves already-namespaced paths untouched, even when long', () => {
    const already = `\\\\?\\UNC\\server\\share\\${'c'.repeat(240)}`;
    expect(win32LongPathPrefix(already)).toBe(already);
    const alreadyDrive = `\\\\?\\C:\\${'d'.repeat(240)}`;
    expect(win32LongPathPrefix(alreadyDrive)).toBe(alreadyDrive);
  });
});
