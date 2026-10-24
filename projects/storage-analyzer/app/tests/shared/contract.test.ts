/**
 * Contract tests: zod schemas reject malformed inputs; the pure helpers
 * behind exclusions and protected-path warnings behave as specified;
 * IPC channel names are stable.
 */
import { describe, expect, it } from 'vitest';
import {
  emptySchema,
  exportReportSchema,
  scanIdSchema,
  scanSearchSchema,
  scanStartSchema,
} from '../../shared/schemas';
import { IpcChannels, StorageEvents } from '../../shared/ipc-channels';
import {
  detectProtectedPath,
  isExcluded,
  normalizeRel,
} from '../../electron/main/scanner/engine';

describe('zod schemas', () => {
  it('rejects an empty rootPath', () => {
    expect(() => scanStartSchema.parse({ rootPath: '', exclusions: [] })).toThrow();
    expect(() => scanStartSchema.parse({ rootPath: '   '.trim(), exclusions: [] })).toThrow();
  });

  it('accepts a valid scan.start payload and defaults exclusions', () => {
    const parsed = scanStartSchema.parse({ rootPath: 'C:\\data' });
    expect(parsed.exclusions).toEqual([]);
  });

  it('rejects non-integer / non-positive / non-numeric scanIds', () => {
    expect(() => scanIdSchema.parse({ scanId: 0 })).toThrow();
    expect(() => scanIdSchema.parse({ scanId: -3 })).toThrow();
    expect(() => scanIdSchema.parse({ scanId: 1.5 })).toThrow();
    expect(() => scanIdSchema.parse({ scanId: '3' })).toThrow();
    expect(() => scanIdSchema.parse({})).toThrow();
    expect(scanIdSchema.parse({ scanId: 7 })).toEqual({ scanId: 7 });
  });

  it('rejects empty search queries and bad export formats', () => {
    expect(() => scanSearchSchema.parse({ scanId: 1, query: '' })).toThrow();
    expect(() => exportReportSchema.parse({ scanId: 1, format: 'xml', outPath: '/tmp/x' })).toThrow();
    expect(() => exportReportSchema.parse({ scanId: 1, format: 'csv', outPath: '' })).toThrow();
    expect(exportReportSchema.parse({ scanId: 1, format: 'csv', outPath: '/tmp/x.csv' }).format).toBe('csv');
  });

  it('accepts empty payloads for scan.list / chooseDirectory', () => {
    expect(emptySchema.parse({})).toEqual({});
  });
});

describe('exclusion matching', () => {
  it('matches substrings case-insensitively', () => {
    expect(isExcluded('a/node_modules/dep/index.js', ['node_modules'])).toBe(true);
    // Production always normalizes (lower-cases) the rel path first.
    expect(
      isExcluded(normalizeRel('/root', '/root/a/NODE_MODULES/dep/index.js'), ['node_modules']),
    ).toBe(true);
    expect(isExcluded('$recycle.bin/trash', ['$RECYCLE.BIN'])).toBe(true);
    expect(isExcluded('a/keep.txt', ['node_modules'])).toBe(false);
  });

  it('matches globs against the full rel path and trailing segments', () => {
    expect(isExcluded('a/b/debug.log', ['*.log'])).toBe(true);
    expect(isExcluded('debug.log', ['*.log'])).toBe(true);
    expect(isExcluded('a/b/debug.txt', ['*.log'])).toBe(false);
    expect(isExcluded('temp/file.tmp', ['temp/*'])).toBe(true);
  });

  it('ignores blank patterns', () => {
    expect(isExcluded('a/b.txt', ['', '   '])).toBe(false);
  });

  it('normalizeRel uses forward slashes', () => {
    const rel = normalizeRel('/root', '/root/a/b.txt');
    expect(rel).toBe('a/b.txt');
  });
});

describe('protected-path warning', () => {
  it('warns on Windows drive roots and system dirs', () => {
    expect(detectProtectedPath('C:\\', 'win32')).toBe('protected-path');
    expect(detectProtectedPath('C:/', 'win32')).toBe('protected-path');
    expect(detectProtectedPath('C:\\Windows', 'win32')).toBe('protected-path');
    expect(detectProtectedPath('C:\\Windows\\System32', 'win32')).toBe('protected-path');
    expect(detectProtectedPath('D:\\Program Files\\App', 'win32')).toBe('protected-path');
  });

  it('does not warn on ordinary folders', () => {
    expect(detectProtectedPath('C:\\Users\\adam\\Documents', 'win32')).toBeNull();
    expect(detectProtectedPath('D:\\games', 'win32')).toBeNull();
  });

  it('never warns off Windows', () => {
    expect(detectProtectedPath('/', 'linux')).toBeNull();
    expect(detectProtectedPath('C:\\Windows', 'linux')).toBeNull();
  });
});

describe('IPC channels', () => {
  it('exposes the full contract surface with stable names', () => {
    expect(IpcChannels).toEqual({
      dialogChooseDirectory: 'storage.dialog.chooseDirectory',
      scanStart: 'storage.scan.start',
      scanCancel: 'storage.scan.cancel',
      scanStatus: 'storage.scan.status',
      scanList: 'storage.scan.list',
      resultsSummary: 'storage.results.summary',
      resultsDuplicates: 'storage.results.duplicates',
      resultsSearch: 'storage.results.search',
      exportReport: 'storage.export.report',
    });
    expect(StorageEvents).toEqual({
      progress: 'storage.scan.progress',
      finished: 'storage.scan.finished',
    });
  });
});
