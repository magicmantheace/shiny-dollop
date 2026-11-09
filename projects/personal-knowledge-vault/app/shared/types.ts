/**
 * Shared type definitions — the SINGLE SOURCE OF TRUTH for the
 * `window.pkv` API contract, the method→IPC-channel mapping, and the
 * domain model shapes exchanged over IPC.
 *
 * Both the main-process handlers (app/electron/ipc.ts) and the preload
 * bridge (app/electron/preload.ts) derive from this file. Worker B's
 * renderer code should import these types too.
 *
 * ## Canonical IPC contract (method → channel)
 *
 * | window.pkv method              | IPC channel              |
 * |-------------------------------|--------------------------|
 * | pkv.notes.create              | pkv:notes:create         |
 * | pkv.notes.get                 | pkv:notes:get            |
 * | pkv.notes.list                | pkv:notes:list           |
 * | pkv.notes.update              | pkv:notes:update         |
 * | pkv.notes.delete              | pkv:notes:delete         |
 * | pkv.notes.search              | pkv:notes:search         |
 * | pkv.review.approve            | pkv:review:approve        |
 * | pkv.review.reject             | pkv:review:reject         |
 * | pkv.revisions.list            | pkv:revisions:list       |
 * | pkv.backup.export             | pkv:backup:export        |
 * | pkv.backup.import             | pkv:backup:import        |
 *
 * All payloads are validated with zod (app/shared/schemas.ts) in the main
 * process before touching the database. Responses use the IpcResult
 * envelope: `{ ok: true, data }` or `{ ok: false, error: { code, message } }`.
 */

/** Method → IPC channel mapping. The preload and main must use these constants. */
export const PkvChannels = {
  notesCreate: 'pkv:notes:create',
  notesGet: 'pkv:notes:get',
  notesList: 'pkv:notes:list',
  notesUpdate: 'pkv:notes:update',
  notesDelete: 'pkv:notes:delete',
  notesSearch: 'pkv:notes:search',
  reviewApprove: 'pkv:review:approve',
  reviewReject: 'pkv:review:reject',
  revisionsList: 'pkv:revisions:list',
  backupExport: 'pkv:backup:export',
  backupImport: 'pkv:backup:import',
} as const;

export type NoteStatus = 'candidate' | 'verified' | 'rejected';

/** Provenance for a note. At least one of url / docPointer / title is required. */
export interface NoteSource {
  id: string;
  title: string | null;
  author: string | null;
  url: string | null;
  docPointer: string | null;
  accessedAt: string | null;
}

export interface LinkedNote {
  id: string;
  title: string;
  status: NoteStatus;
}

export interface Note {
  id: string;
  title: string;
  body: string;
  status: NoteStatus;
  rejectionReason: string | null;
  createdAt: string;
  updatedAt: string;
  source: NoteSource | null;
  tags: string[];
  links: LinkedNote[];
  revisionCount: number;
}

export interface Revision {
  id: string;
  noteId: string;
  revNo: number;
  title: string;
  body: string;
  tags: string[];
  status: NoteStatus;
  changeSummary: string;
  createdAt: string;
}

export interface NoteInput {
  title: string;
  body: string;
  tags: string[];
  source?: {
    title?: string;
    author?: string;
    url?: string;
    docPointer?: string;
    accessedAt?: string;
  };
  links?: string[];
}

export interface NoteUpdateInput {
  title?: string | undefined;
  body?: string | undefined;
  tags?: string[] | undefined;
  links?: string[] | undefined;
  changeSummary: string;
}

export interface NoteFilters {
  status?: NoteStatus | undefined;
  tag?: string | undefined;
  sourceId?: string | undefined;
}

export interface SearchFilters {
  status?: NoteStatus | undefined;
  tag?: string | undefined;
}

export interface BackupImportResult {
  imported: number;
  skipped: number;
}

/** Uniform IPC response envelope. */
export type IpcResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string } };

/**
 * The typed `window.pkv` API exposed by the preload bridge.
 * Flat namespace: pkv.notes.*, pkv.review.*, pkv.revisions.*, pkv.backup.*.
 */
export interface PkvApi {
  notes: {
    /** Create a note; status always starts as `candidate`. */
    create: (input: NoteInput) => Promise<Note>;
    /** Fetch one note with source, tags, links and revision count. */
    get: (id: string) => Promise<Note | null>;
    /** List notes, optionally filtered. */
    list: (filters?: NoteFilters) => Promise<Note[]>;
    /** Update a note; appends an immutable revision. changeSummary is required. */
    update: (id: string, input: NoteUpdateInput) => Promise<Note>;
    /** Delete a note; returns true when a note was removed. */
    delete: (id: string) => Promise<boolean>;
    /** Full-text search over title, body and tags, ranked by relevance. */
    search: (query: string, filters?: SearchFilters) => Promise<Note[]>;
  };
  review: {
    /** Move candidate → verified. Never affects other notes. */
    approve: (id: string) => Promise<Note>;
    /** Move candidate → rejected. reason is required. */
    reject: (id: string, reason: string) => Promise<Note>;
  };
  revisions: {
    /** Immutable revision history for a note, oldest first. */
    list: (noteId: string) => Promise<Revision[]>;
  };
  backup: {
    /**
     * Build the versioned export payload (JSON string). The main process
     * also writes it to disk through a save dialog.
     */
    export: () => Promise<string>;
    /** Validate and import an export payload. Returns { imported, skipped }. */
    import: (json: string) => Promise<BackupImportResult>;
  };
}
