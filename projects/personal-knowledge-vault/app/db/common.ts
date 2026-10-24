/**
 * Shared database helpers for the notes/review/backup modules.
 * Must NOT import 'electron' (backend tests import these directly).
 */
import type { DatabaseSync } from 'node:sqlite';
import type { Note, NoteSource, NoteStatus, Revision } from '../shared/types';

export function nowIso(): string {
  return new Date().toISOString();
}

/** Run fn inside an explicit transaction; roll back on any error. */
export function tx<T>(db: DatabaseSync, fn: () => T): T {
  db.exec('BEGIN');
  try {
    const result = fn();
    db.exec('COMMIT');
    return result;
  } catch (err) {
    try {
      db.exec('ROLLBACK');
    } catch {
      /* already rolled back */
    }
    throw err;
  }
}

/** Trim, drop empties, and dedupe tags (case-sensitive, order preserved). */
export function normalizeTags(tags: readonly string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of tags) {
    const tag = raw.trim();
    if (tag.length === 0 || seen.has(tag)) continue;
    seen.add(tag);
    out.push(tag);
  }
  return out;
}

interface NoteRow {
  id: string;
  title: string;
  body: string;
  status: NoteStatus;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
}

interface SourceRow {
  id: string;
  title: string | null;
  author: string | null;
  url: string | null;
  doc_pointer: string | null;
  accessed_at: string | null;
}

function noteSourceFromRow(row: SourceRow | undefined): NoteSource | null {
  if (!row) return null;
  return {
    id: row.id,
    title: row.title,
    author: row.author,
    url: row.url,
    docPointer: row.doc_pointer,
    accessedAt: row.accessed_at,
  };
}

/**
 * Assemble a full Note from its normalized tables. Throws NOTE_NOT_FOUND
 * (as PkvError) when the id does not exist.
 */
export function noteExists(db: DatabaseSync, id: string): boolean {
  const row = db.prepare('SELECT 1 AS ok FROM notes WHERE id = ?').get(id) as
    | { ok: number }
    | undefined;
  return row !== undefined;
}

/** Fetch a fully-assembled Note; returns null when missing. */
export function getNoteRow(db: DatabaseSync, id: string): Note | null {
  const row = db.prepare('SELECT * FROM notes WHERE id = ?').get(id) as NoteRow | undefined;
  if (!row) return null;

  const tagRows = db
    .prepare('SELECT tag FROM note_tags WHERE note_id = ? ORDER BY tag')
    .all(id) as { tag: string }[];

  const sourceRow = db.prepare('SELECT * FROM sources WHERE note_id = ?').get(id) as
    | SourceRow
    | undefined;

  const linkRows = db
    .prepare(
      `SELECT t.id AS id, t.title AS title, t.status AS status
         FROM note_links l JOIN notes t ON t.id = l.target_note_id
        WHERE l.note_id = ? ORDER BY t.title`,
    )
    .all(id) as { id: string; title: string; status: NoteStatus }[];

  const revCount = (
    db.prepare('SELECT COUNT(*) AS n FROM revisions WHERE note_id = ?').get(id) as { n: number }
  ).n;

  return {
    id: row.id,
    title: row.title,
    body: row.body,
    status: row.status,
    rejectionReason: row.rejection_reason,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    source: noteSourceFromRow(sourceRow),
    tags: tagRows.map((t) => t.tag),
    links: linkRows,
    revisionCount: revCount,
  };
}

/** Assemble a Revision from a DB row. */
export function revisionFromRow(row: {
  id: string;
  note_id: string;
  rev_no: number;
  title: string;
  body: string;
  tags_json: string;
  status: NoteStatus;
  change_summary: string;
  created_at: string;
}): Revision {
  return {
    id: row.id,
    noteId: row.note_id,
    revNo: row.rev_no,
    title: row.title,
    body: row.body,
    tags: JSON.parse(row.tags_json) as string[],
    status: row.status,
    changeSummary: row.change_summary,
    createdAt: row.created_at,
  };
}
