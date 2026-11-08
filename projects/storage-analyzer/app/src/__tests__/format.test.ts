import { describe, expect, it } from 'vitest';
import {
  duplicateSavingsBytes,
  formatBytes,
  formatDateTime,
  formatInt,
  isProtectedPath,
  parseExclusions,
} from '../format';

describe('formatBytes', () => {
  it('formats bytes, KB, MB and GB', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(1024)).toBe('1 KB');
    expect(formatBytes(1536)).toBe('1.5 KB');
    expect(formatBytes(1024 * 1024)).toBe('1 MB');
    expect(formatBytes(5 * 1024 ** 3)).toBe('5 GB');
  });

  it('handles invalid input', () => {
    expect(formatBytes(-1)).toBe('—');
    expect(formatBytes(Number.NaN)).toBe('—');
  });
});

describe('formatInt', () => {
  it('groups digits', () => {
    expect(formatInt(1234567)).toBe('1,234,567');
  });
});

describe('formatDateTime', () => {
  it('renders a valid ISO timestamp', () => {
    expect(formatDateTime('2026-10-23T10:00:00.000Z')).toContain('2026');
  });

  it('handles null and garbage', () => {
    expect(formatDateTime(null)).toBe('—');
    expect(formatDateTime('not-a-date')).toBe('not-a-date');
  });
});

describe('isProtectedPath', () => {
  it('flags drive roots and system folders', () => {
    expect(isProtectedPath('C:\\')).toBe(true);
    expect(isProtectedPath('C:')).toBe(true);
    expect(isProtectedPath('C:/')).toBe(true);
    expect(isProtectedPath('C:\\Windows\\System32')).toBe(true);
    expect(isProtectedPath('d:\\Program Files\\app')).toBe(true);
  });

  it('does not flag ordinary folders', () => {
    expect(isProtectedPath('C:\\Users\\adam\\Documents')).toBe(false);
    expect(isProtectedPath('C:\\data')).toBe(false);
    expect(isProtectedPath('')).toBe(false);
  });
});

describe('duplicateSavingsBytes', () => {
  it('computes size * (n - 1)', () => {
    expect(duplicateSavingsBytes(500, 2)).toBe(500);
    expect(duplicateSavingsBytes(500, 4)).toBe(1500);
    expect(duplicateSavingsBytes(500, 1)).toBe(0);
  });
});

describe('parseExclusions', () => {
  it('splits lines, trims, drops blanks and dedupes', () => {
    expect(parseExclusions('node_modules\n\n  $RECYCLE.BIN \nnode_modules\n')).toEqual([
      'node_modules',
      '$RECYCLE.BIN',
    ]);
  });

  it('handles empty input', () => {
    expect(parseExclusions('')).toEqual([]);
  });
});
