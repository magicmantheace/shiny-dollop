/**
 * Renderer-side aliases for the canonical IPC contract in `app/shared/`
 * (Worker A's source of truth). Field names are kept in sync by re-exporting
 * the shared types instead of redeclaring them.
 */

export type {
  DuplicateGroup,
  IpcErrorBody,
  IpcResult,
  LargestFileEntry as LargestFile,
  DirSizeEntry as DirSize,
  ScanFinishedEvent,
  ScanListEntry as ScanSummaryInfo,
  ScanProgressEvent,
  ScanStartWarning,
  ScanState,
  ScanStatus,
  SearchHit as SearchResult,
  ResultsSummary as SummaryResult,
  TypeSummaryEntry as TypeSummary,
} from '../shared/types';
export type { StorageAnalyzerApi, Unsubscribe } from '../shared/api-types';
