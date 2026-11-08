// Renderer type adapter.
//
// The SINGLE SOURCE OF TRUTH for the window.pkv contract is
// app/shared/types.ts (Worker A). This module re-exports the canonical
// types for renderer use and adds only renderer-side helpers.
// Do not redeclare contract shapes here — import them.

import type { NoteStatus, PkvApi } from '../shared/types';

export type {
  BackupImportResult,
  LinkedNote,
  Note,
  NoteFilters,
  NoteInput,
  NoteSource,
  NoteStatus,
  NoteUpdateInput,
  PkvApi,
  Revision,
  SearchFilters,
} from '../shared/types';

export const NOTE_STATUSES: NoteStatus[] = ['candidate', 'verified', 'rejected'];

declare global {
  interface Window {
    pkv?: PkvApi;
  }
}

/** Throws a descriptive error when the preload bridge is missing (e.g. plain browser). */
export function getPkv(): PkvApi {
  const api = window.pkv;
  if (!api) {
    throw new Error('Personal Knowledge Vault bridge (window.pkv) is not available.');
  }
  return api;
}
