/**
 * Versioned backup export / import.
 *
 * Export payload shape (JSON string):
 *   { formatVersion: '1.0.0', exportedAt, notes: [{...note, source, revisions, links}] }
 *
 * The payload is byte-deterministic: fixed key order everywhere, notes
 * sorted by id, tags/links/revisions in stable order. Pass an explicit
 * `exportedAt` in tests to get identical bytes across runs.
 *
 * Import validates the formatVersion major (only major 1 is supported),
 * rejects corrupt JSON (BACKUP_CORRUPT) and schema violations
 * (BACKUP_IMPORT_INVALID), and returns { imported, skipped } where
 * skipped counts notes whose id already exists in the database.
 * Must NOT import 'electron' (backend tests import this directly).
 */
import { randomUUID } from 'node:crypto';
import type { DatabaseSync } from 'node:sqlite';
import { z } from 'zod';
import { PkvError, PkvErrorCode } from '../shared/errors';
import type { BackupImportResult } from '../shared/types';
import { getNoteRow, noteExists, normalizeTags, tx } from './common';

export const BACKUP_FORMAT_VERSION = '1.0.0' as const;
const BACKUP_FORMAT_MAJOR = 1;

const backupSourceSchema = z.object({
  id: z.string().uuid(),
  title: z.string().nullable(),
  author: z.string().nullable(),
  url: z.string().nullable(),
  docPointer: z.string().nullable(),
  accessedAt: z.string().nullable(),
});

const backupRevisionSchema = z.object({
  revNo: z.number().int().min(1),
  title: z.string(),
  body: z.string(),
  tags: z.array(z.string()),
  status: z.enum(['candidate', 'verified', 'rejected']),
  changeSummary: z.string(),
  createdAt: z.string(),
});

const backupNoteSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  body: z.string(),
  status: z.enum(['candidate', 'verified', 'rejected']),
  rejectionReason: z.string().nullable(),
  createdAt: z.string(),
  updatedAt: z.string(),
  source: backupSourceSchema.nullable(),
  tags: z.array(z.string()),
  links: z.array(z.string().uuid()),
  revisions: z.array(backupRevisionSchema),
});

const backupEnvelopeSchema = z.object({
  formatVersion: z.string(),
  exportedAt: z.string(),
  notes: z.array(backupNoteSchema),
});

/** Build the export payload as a byte-deterministic JSON string. */
export function exportBackup(db: DatabaseSync, exportedAt?: string): string {
  const rows = db.prepare('SELECT id FROM notes ORDER BY id ASC').all() as { id: string }[];
  const notes = rows.map((r) => {
    const note = getNoteRow(db, r.id);
    if (!note) throw new PkvError(PkvErrorCode.INTERNAL_ERROR, `Note vanished during export: ${r.id}.`);
    const revRows = db
      .prepare(
        `SELECT rev_no, title, body, tags_json, status, change_summary, created_at
           FROM revisions WHERE note_id = ? ORDER BY rev_no ASC`,
      )
      .all(note.id) as {
      rev_no: number;
      title: string;
      body: string;
      tags_json: string;
      status: 'candidate' | 'verified' | 'rejected';
      change_summary: string;
      created_at: string;
    }[];
    return {
      id: note.id,
      title: note.title,
      body: note.body,
      status: note.status,
      rejectionReason: note.rejectionReason,
      createdAt: note.createdAt,
      updatedAt: note.updatedAt,
      source: note.source
        ? {
            id: note.source.id,
            title: note.source.title,
            author: note.source.author,
            url: note.source.url,
            docPointer: note.source.docPointer,
            accessedAt: note.source.accessedAt,
          }
        : null,
      tags: [...note.tags].sort(),
      links: note.links.map((l) => l.id).sort(),
      revisions: revRows.map((rev) => ({
        revNo: rev.rev_no,
        title: rev.title,
        body: rev.body,
        tags: JSON.parse(rev.tags_json) as string[],
        status: rev.status,
        changeSummary: rev.change_summary,
        createdAt: rev.created_at,
      })),
    };
  });
  const payload = {
    formatVersion: BACKUP_FORMAT_VERSION,
    exportedAt: exportedAt ?? new Date().toISOString(),
    notes,
  };
  return JSON.stringify(payload);
}

/**
 * Validate and import an export payload.
 * Named failures: BACKUP_CORRUPT (not JSON), BACKUP_VERSION_UNSUPPORTED
 * (unknown major version), BACKUP_IMPORT_INVALID (schema/shape violations).
 * The whole import is atomic: any violation rolls everything back.
 */
export function importBackup(db: DatabaseSync, json: string): BackupImportResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(json);
  } catch {
    throw new PkvError(PkvErrorCode.BACKUP_CORRUPT, 'Backup payload is not valid JSON.');
  }

  const envelope = backupEnvelopeSchema.safeParse(parsed);
  if (!envelope.success) {
    const first = envelope.error.issues[0];
    const where = first?.path.length ? ` (${first.path.join('.')})` : '';
    throw new PkvError(
      PkvErrorCode.BACKUP_IMPORT_INVALID,
      `Backup payload failed schema validation${where}: ${first?.message ?? 'invalid'}.`,
    );
  }

  const major = parseInt(envelope.data.formatVersion.split('.')[0] ?? '', 10);
  if (!Number.isInteger(major) || major !== BACKUP_FORMAT_MAJOR) {
    throw new PkvError(
      PkvErrorCode.BACKUP_VERSION_UNSUPPORTED,
      `Unsupported backup formatVersion "${envelope.data.formatVersion}" (expected major ${BACKUP_FORMAT_MAJOR}).`,
    );
  }

  const notes = envelope.data.notes;
  const payloadIds = new Set(notes.map((n) => n.id));

  return tx(db, () => {
    let imported = 0;
    let skipped = 0;

    // Pass 1: insert notes, tags, sources, revisions (links need all notes present).
    const importedIds = new Set<string>();
    for (const note of notes) {
      if (noteExists(db, note.id)) {
        skipped += 1;
        continue;
      }
      db.prepare(
        `INSERT INTO notes (id, title, body, status, rejection_reason, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
      ).run(
        note.id,
        note.title,
        note.body,
        note.status,
        note.rejectionReason,
        note.createdAt,
        note.updatedAt,
      );
      const tagStmt = db.prepare('INSERT OR IGNORE INTO note_tags (note_id, tag) VALUES (?, ?)');
      for (const tag of normalizeTags(note.tags)) tagStmt.run(note.id, tag);
      if (note.source) {
        db.prepare(
          `INSERT INTO sources (id, note_id, title, author, url, doc_pointer, accessed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)`,
        ).run(
          note.source.id,
          note.id,
          note.source.title,
          note.source.author,
          note.source.url,
          note.source.docPointer,
          note.source.accessedAt,
        );
      }
      const revStmt = db.prepare(
        `INSERT INTO revisions (id, note_id, rev_no, title, body, tags_json, status, change_summary, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      );
      for (const rev of note.revisions) {
        revStmt.run(
          randomUUID(),
          note.id,
          rev.revNo,
          rev.title,
          rev.body,
          JSON.stringify(normalizeTags(rev.tags)),
          rev.status,
          rev.changeSummary,
          rev.createdAt,
        );
      }
      imported += 1;
      importedIds.add(note.id);
    }

    // Pass 2: links, validated against payload + database.
    // Skipped notes keep their existing links untouched.
    for (const note of notes) {
      for (const target of note.links) {
        if (target === note.id) {
          throw new PkvError(
            PkvErrorCode.BACKUP_IMPORT_INVALID,
            `Backup note ${note.id} links to itself.`,
          );
        }
        if (!payloadIds.has(target) && !noteExists(db, target)) {
          throw new PkvError(
            PkvErrorCode.BACKUP_IMPORT_INVALID,
            `Backup note ${note.id} links to unknown target ${target}.`,
          );
        }
      }
      if (!importedIds.has(note.id)) continue;
      const linkStmt = db.prepare(
        'INSERT OR IGNORE INTO note_links (note_id, target_note_id) VALUES (?, ?)',
      );
      for (const target of [...new Set(note.links)]) linkStmt.run(note.id, target);
    }

    return { imported, skipped };
  });
}
