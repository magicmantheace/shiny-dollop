/**
 * Note CRUD, full-text search, and revision history.
 * All writes run inside explicit BEGIN/COMMIT/ROLLBACK transactions.
 * Must NOT import 'electron' (backend tests import this directly).
 */
import { randomUUID } from 'node:crypto';
import type { DatabaseSync } from 'node:sqlite';
import { PkvError, PkvErrorCode } from '../shared/errors';
import type { Note, NoteFilters, NoteStatus, Revision, SearchFilters } from '../shared/types';
import { getNoteRow, noteExists, normalizeTags, nowIso, revisionFromRow, tx } from './common';

export interface CreateNoteArgs {
  title: string;
  body: string;
  tags: string[];
  source?: {
    title?: string | undefined;
    author?: string | undefined;
    url?: string | undefined;
    docPointer?: string | undefined;
    accessedAt?: string | undefined;
  } | null;
  links?: string[];
}

export interface UpdateNoteArgs {
  title?: string | undefined;
  body?: string | undefined;
  tags?: string[] | undefined;
  links?: string[] | undefined;
  changeSummary: string;
}

/** Validate a source anchor: at least one of url / docPointer / title. */
function assertSourceAnchor(source: NonNullable<CreateNoteArgs['source']>): void {
  const has = (v: string | undefined) => Boolean(v && v.trim().length > 0);
  if (!has(source.url) && !has(source.docPointer) && !has(source.title)) {
    throw new PkvError(
      PkvErrorCode.SOURCE_ANCHOR_REQUIRED,
      'Source requires at least one of: url, docPointer, title.',
    );
  }
}

/** Validate that every link target exists and no link points back at the note itself. */
function assertLinksValid(db: DatabaseSync, noteId: string, links: readonly string[]): void {
  const seen = new Set<string>();
  for (const target of links) {
    if (target === noteId) {
      throw new PkvError(
        PkvErrorCode.SELF_LINK_NOT_ALLOWED,
        `Note cannot link to itself (${noteId}).`,
      );
    }
    if (seen.has(target)) continue;
    seen.add(target);
    if (!noteExists(db, target)) {
      throw new PkvError(
        PkvErrorCode.LINK_TARGET_NOT_FOUND,
        `Link target note does not exist: ${target}.`,
      );
    }
  }
}

function insertSource(
  db: DatabaseSync,
  noteId: string,
  source: NonNullable<CreateNoteArgs['source']>,
  createdAt: string,
): void {
  db.prepare(
    `INSERT INTO sources (id, note_id, title, author, url, doc_pointer, accessed_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    randomUUID(),
    noteId,
    source.title?.trim() || null,
    source.author?.trim() || null,
    source.url?.trim() || null,
    source.docPointer?.trim() || null,
    source.accessedAt?.trim() || createdAt,
  );
}

function insertTags(db: DatabaseSync, noteId: string, tags: string[]): void {
  const stmt = db.prepare('INSERT OR IGNORE INTO note_tags (note_id, tag) VALUES (?, ?)');
  for (const tag of tags) stmt.run(noteId, tag);
}

function insertLinks(db: DatabaseSync, noteId: string, links: readonly string[]): void {
  const stmt = db.prepare('INSERT OR IGNORE INTO note_links (note_id, target_note_id) VALUES (?, ?)');
  for (const target of links) stmt.run(noteId, target);
}

/**
 * Create a note. Status always starts as `candidate`.
 * Rejects unknown link targets and self-links before any write.
 */
export function createNote(db: DatabaseSync, args: CreateNoteArgs): Note {
  if (args.source) assertSourceAnchor(args.source);
  const tags = normalizeTags(args.tags);
  const links = [...new Set(args.links ?? [])];

  return tx(db, () => {
    const id = randomUUID();
    assertLinksValid(db, id, links);
    const createdAt = nowIso();
    db.prepare(
      `INSERT INTO notes (id, title, body, status, rejection_reason, created_at, updated_at)
       VALUES (?, ?, ?, 'candidate', NULL, ?, ?)`,
    ).run(id, args.title, args.body, createdAt, createdAt);
    insertTags(db, id, tags);
    if (args.source) insertSource(db, id, args.source, createdAt);
    insertLinks(db, id, links);
    const note = getNoteRow(db, id);
    if (!note) throw new PkvError(PkvErrorCode.INTERNAL_ERROR, 'Note vanished after insert.');
    return note;
  });
}

/** Fetch one note with source, tags, links and revision count. Null when missing. */
export function getNote(db: DatabaseSync, id: string): Note | null {
  return getNoteRow(db, id);
}

/** List notes with optional status / tag / source filters, newest first. */
export function listNotes(db: DatabaseSync, filters: NoteFilters = {}): Note[] {
  const conditions: string[] = [];
  const params: string[] = [];
  if (filters.status) {
    conditions.push('n.status = ?');
    params.push(filters.status);
  }
  if (filters.tag) {
    conditions.push(`EXISTS (SELECT 1 FROM note_tags t WHERE t.note_id = n.id AND t.tag = ?)`);
    params.push(filters.tag);
  }
  if (filters.sourceId) {
    conditions.push(`EXISTS (SELECT 1 FROM sources s WHERE s.note_id = n.id AND s.id = ?)`);
    params.push(filters.sourceId);
  }
  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
  const rows = db
    .prepare(`SELECT id FROM notes n ${where} ORDER BY n.created_at DESC, n.id ASC`)
    .all(...params) as { id: string }[];
  return rows
    .map((r) => getNoteRow(db, r.id))
    .filter((n): n is Note => n !== null);
}

/**
 * Update a note. Appends an immutable revision capturing the NEW state;
 * rev_no is strictly monotonic per note. changeSummary is required.
 */
export function updateNote(db: DatabaseSync, id: string, args: UpdateNoteArgs): Note {
  if (!args.changeSummary || args.changeSummary.trim().length === 0) {
    throw new PkvError(PkvErrorCode.CHANGE_SUMMARY_REQUIRED, 'update() requires a changeSummary.');
  }
  const existing = getNoteRow(db, id);
  if (!existing) throw new PkvError(PkvErrorCode.NOTE_NOT_FOUND, `Note not found: ${id}.`);

  const title = args.title ?? existing.title;
  const body = args.body ?? existing.body;
  const tags = args.tags !== undefined ? normalizeTags(args.tags) : existing.tags;
  const links = args.links !== undefined ? [...new Set(args.links)] : existing.links.map((l) => l.id);
  if (args.links !== undefined) assertLinksValid(db, id, links);

  return tx(db, () => {
    const updatedAt = nowIso();
    db.prepare('UPDATE notes SET title = ?, body = ?, updated_at = ? WHERE id = ?').run(
      title,
      body,
      updatedAt,
      id,
    );
    if (args.tags !== undefined) {
      db.prepare('DELETE FROM note_tags WHERE note_id = ?').run(id);
      insertTags(db, id, tags);
    }
    if (args.links !== undefined) {
      db.prepare('DELETE FROM note_links WHERE note_id = ?').run(id);
      insertLinks(db, id, links);
    }
    const maxRev = (
      db.prepare('SELECT COALESCE(MAX(rev_no), 0) AS m FROM revisions WHERE note_id = ?').get(id) as {
        m: number;
      }
    ).m;
    db.prepare(
      `INSERT INTO revisions (id, note_id, rev_no, title, body, tags_json, status, change_summary, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      randomUUID(),
      id,
      maxRev + 1,
      title,
      body,
      JSON.stringify(tags),
      existing.status,
      args.changeSummary.trim(),
      updatedAt,
    );
    const note = getNoteRow(db, id);
    if (!note) throw new PkvError(PkvErrorCode.INTERNAL_ERROR, 'Note vanished after update.');
    return note;
  });
}

/** Delete a note and its tags/sources/links/revisions. Returns true when a note was removed. */
export function deleteNote(db: DatabaseSync, id: string): boolean {
  return tx(db, () => {
    const result = db.prepare('DELETE FROM notes WHERE id = ?').run(id);
    return result.changes > 0;
  });
}

/**
 * Quote each query token as an FTS5 phrase and AND them together.
 * Quoting makes arbitrary user input (quotes, parens, *, OR, …) safe.
 */
function buildMatchExpression(query: string): string {
  const tokens = query
    .split(/\s+/)
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
  return tokens.map((t) => `"${t.replace(/"/g, '""')}"`).join(' AND ');
}

/**
 * Full-text search over title, body and tags, ranked by FTS5 bm25 rank
 * (best match first). Optional status / tag filters.
 */
export function searchNotes(
  db: DatabaseSync,
  query: string,
  filters: SearchFilters = {},
): Note[] {
  const match = buildMatchExpression(query);
  if (match.length === 0) return [];
  const conditions: string[] = ['f.notes_fts MATCH ?'];
  const params: string[] = [match];
  if (filters.status) {
    conditions.push('n.status = ?');
    params.push(filters.status);
  }
  if (filters.tag) {
    conditions.push(`EXISTS (SELECT 1 FROM note_tags t WHERE t.note_id = n.id AND t.tag = ?)`);
    params.push(filters.tag);
  }
  const rows = db
    .prepare(
      `SELECT n.id AS id
         FROM notes_fts f JOIN notes n ON n.id = f.note_id
        WHERE ${conditions.join(' AND ')}
        ORDER BY f.rank`,
    )
    .all(...params) as { id: string }[];
  return rows
    .map((r) => getNoteRow(db, r.id))
    .filter((n): n is Note => n !== null);
}

/** Immutable revision history for a note, oldest first. */
export function listRevisions(db: DatabaseSync, noteId: string): Revision[] {
  if (!noteExists(db, noteId)) {
    throw new PkvError(PkvErrorCode.NOTE_NOT_FOUND, `Note not found: ${noteId}.`);
  }
  const rows = db
    .prepare('SELECT * FROM revisions WHERE note_id = ? ORDER BY rev_no ASC')
    .all(noteId) as Parameters<typeof revisionFromRow>[0][];
  return rows.map(revisionFromRow);
}

export type { NoteStatus };
