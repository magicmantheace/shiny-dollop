import { vi } from 'vitest';
import type {
  DuplicateGroup,
  ScanFinishedEvent,
  ScanProgressEvent,
  ScanStatus,
  ScanSummaryInfo,
  SearchResult,
  StorageAnalyzerApi,
  SummaryResult,
} from '../types';

/** Convenience: successful IPC envelope. */
export function ok<T>(data: T) {
  return { ok: true as const, data };
}

/** Failure envelope. */
export function err(code: string, message: string) {
  return { ok: false as const, error: { code, message } };
}

/** Captured event listeners so tests can fire scan.progress / scan.finished. */
export interface EventCaptures {
  progress: Array<(e: ScanProgressEvent) => void>;
  finished: Array<(e: ScanFinishedEvent) => void>;
}

export const defaultStatus: ScanStatus = {
  state: 'running',
  files: 0,
  dirs: 0,
  bytes: 0,
  startedAt: '2026-10-23T10:00:00.000Z',
  finishedAt: null,
  errors: 0,
  changedFiles: 0,
};

export const defaultSummary: SummaryResult = {
  totalFiles: 42,
  totalBytes: 1024,
  largestFiles: [{ path: 'C:\\data\\big.iso', size: 900 }],
  dirSizes: [{ path: 'C:\\data', bytes: 1024, files: 42 }],
  typeSummary: [{ ext: '.iso', files: 1, bytes: 900 }],
};

export const defaultScans: ScanSummaryInfo[] = [
  {
    id: 1,
    rootPath: 'C:\\data',
    state: 'complete',
    files: 42,
    bytes: 1024,
    startedAt: '2026-10-23T10:00:00.000Z',
    finishedAt: '2026-10-23T10:05:00.000Z',
  },
];

export const defaultGroups: DuplicateGroup[] = [
  {
    sizeBytes: 500,
    sha256: 'ab'.repeat(32),
    files: ['C:\\data\\a.txt', 'C:\\data\\b.txt'],
  },
];

export const defaultSearch: SearchResult[] = [{ path: 'C:\\data\\photo1.png', size: 2048 }];

/**
 * Builds a fully mocked StorageAnalyzerApi matching app/shared/api-types.ts.
 * Every method resolves a successful envelope by default; override individual
 * methods per test. Installs itself as window.storageAnalyzer and returns the
 * mocks plus captured event listeners.
 */
export function installMock(overrides: Partial<StorageAnalyzerApi> = {}) {
  const captures: EventCaptures = { progress: [], finished: [] };

  const mock: StorageAnalyzerApi = {
    dialog: {
      chooseDirectory: vi.fn(async () => ok({ path: 'C:\\data' })),
    },
    scan: {
      start: vi.fn(async () => ok({ scanId: 1 })),
      cancel: vi.fn(async () => ok({ ok: true as const })),
      status: vi.fn(async () => ok({ ...defaultStatus })),
      list: vi.fn(async () => ok({ scans: defaultScans })),
    },
    results: {
      summary: vi.fn(async () => ok({ ...defaultSummary })),
      duplicates: vi.fn(async () => ok({ groups: defaultGroups })),
      search: vi.fn(async () => ok({ files: defaultSearch })),
    },
    export: {
      report: vi.fn(async (args: { outPath: string }) => ok({ outPath: args.outPath })),
    },
    onProgress: vi.fn((listener) => {
      captures.progress.push(listener);
      return () => {};
    }),
    onFinished: vi.fn((listener) => {
      captures.finished.push(listener);
      return () => {};
    }),
  };

  const merged = { ...mock, ...overrides } as StorageAnalyzerApi;
  Object.assign(window, { storageAnalyzer: merged });
  return { api: merged, captures };
}
