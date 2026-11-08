/**
 * Review workflow: candidate → verified / candidate → rejected.
 * Approving or rejecting one note never touches any other record —
 * each operation is a single-row UPDATE in its own transaction.
 * Must NOT import 'electron' (backend tests import this directly).
 */
import type { DatabaseSync } from 'node:sqlite';
import { PkvError, PkvErrorCode } from '../shared/errors';
import type { Note } from '../shared/types';
import { getNoteRow, nowIso, tx } from './common';

/**
 * Move a note from candidate → verified.
 * Throws NOTE_NOT_FOUND when missing, INVALID_STATUS_TRANSITION otherwise.
 */
export function approveNote(db: DatabaseSync, id: string): Note {
  return tx(db, () => {
    const existing = getNoteRow(db, id);
    if (!existing) throw new PkvError(PkvErrorCode.NOTE_NOT_FOUND, `Note not found: ${id}.`);
    if (existing.status !== 'candidate') {
      throw new PkvError(
        PkvErrorCode.INVALID_STATUS_TRANSITION,
        `Only candidate notes can be approved (note ${id} is ${existing.status}).`,
      );
    }
    db.prepare(
      `UPDATE notes SET status = 'verified', rejection_reason = NULL, updated_at = ? WHERE id = ?`,
    ).run(nowIso(), id);
    const note = getNoteRow(db, id);
    if (!note) throw new PkvError(PkvErrorCode.INTERNAL_ERROR, 'Note vanished after approve.');
    return note;
  });
}

/**
 * Move a note from candidate → rejected. The reason is required —
 * an empty/missing reason throws REJECT_REASON_REQUIRED before any write.
 */
export function rejectNote(db: DatabaseSync, id: string, reason: string): Note {
  if (!reason || reason.trim().length === 0) {
    throw new PkvError(
      PkvErrorCode.REJECT_REASON_REQUIRED,
      'reject() requires a non-empty reason.',
    );
  }
  return tx(db, () => {
    const existing = getNoteRow(db, id);
    if (!existing) throw new PkvError(PkvErrorCode.NOTE_NOT_FOUND, `Note not found: ${id}.`);
    if (existing.status !== 'candidate') {
      throw new PkvError(
        PkvErrorCode.INVALID_STATUS_TRANSITION,
        `Only candidate notes can be rejected (note ${id} is ${existing.status}).`,
      );
    }
    db.prepare(
      `UPDATE notes SET status = 'rejected', rejection_reason = ?, updated_at = ? WHERE id = ?`,
    ).run(reason.trim(), nowIso(), id);
    const note = getNoteRow(db, id);
    if (!note) throw new PkvError(PkvErrorCode.INTERNAL_ERROR, 'Note vanished after reject.');
    return note;
  });
}
