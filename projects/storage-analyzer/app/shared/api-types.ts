/**
 * Typed renderer-facing API, shared between preload and the React app.
 * Every method returns the uniform IpcResult envelope.
 * Preload exposes this as `window.storageAnalyzer`.
 */
import type {
  DuplicateGroupsResult,
  ExportReportInput,
  ExportReportResult,
  IpcResult,
  ScanCancelResult,
  ScanFinishedEvent,
  ScanIdInput,
  ScanListResult,
  ScanProgressEvent,
  ScanStartInput,
  ScanStartResult,
  ScanStatus,
  SearchInput,
  SearchResults,
  ResultsSummary,
  Unsubscribe,
} from './types';

export type { Unsubscribe };

export interface StorageAnalyzerApi {
  dialog: {
    chooseDirectory: () => Promise<IpcResult<{ path: string | null }>>;
  };
  scan: {
    start: (input: ScanStartInput) => Promise<IpcResult<ScanStartResult>>;
    cancel: (input: ScanIdInput) => Promise<IpcResult<ScanCancelResult>>;
    status: (input: ScanIdInput) => Promise<IpcResult<ScanStatus>>;
    list: () => Promise<IpcResult<ScanListResult>>;
  };
  results: {
    summary: (input: ScanIdInput) => Promise<IpcResult<ResultsSummary>>;
    duplicates: (input: ScanIdInput) => Promise<IpcResult<DuplicateGroupsResult>>;
    search: (input: SearchInput) => Promise<IpcResult<SearchResults>>;
  };
  export: {
    report: (input: ExportReportInput) => Promise<IpcResult<ExportReportResult>>;
  };
  /** Subscribe to scan.progress events; returns an unsubscribe function. */
  onProgress: (listener: (event: ScanProgressEvent) => void) => Unsubscribe;
  /** Subscribe to scan.finished events; returns an unsubscribe function. */
  onFinished: (listener: (event: ScanFinishedEvent) => void) => Unsubscribe;
}
