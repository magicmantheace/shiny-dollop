/**
 * Review workflow tests:
 * - reject without a reason is blocked with REJECT_REASON_REQUIRED.
 * - approve/reject move candidate notes exactly once.
 * - approving note A never touches note B (isolation).
 */
import { describe, expect, it } from 'vitest';
import { PkvError } from '../../shared/errors';
import { createNote, getNote } from '../../db/notes';
import { approveNote, rejectNote } from '../../db/review';
import { makeDb } from './helpers';

function expectPkvError(fn: () => unknown, code: string): void {
  try {
    fn();
  } catch (err) {
    expect(err).toBeInstanceOf(PkvError);
    expect((err as PkvError).code).toBe(code);
    return;
  }
  throw new Error(`Expected PkvError ${code} but nothing was thrown.`);
}

describe('rejectNote', () => {
  it('blocks empty, whitespace-only and missing reasons', () => {
    const db = makeDb();
    const note = createNote(db, { title: 'T', body: '', tags: [], links: [] });
    for (const bad of ['', '   ', '\n\t ']) {
      expectPkvError(() => rejectNote(db, note.id, bad), 'REJECT_REASON_REQUIRED');
    }
    // Note untouched by the failed attempts.
    expect(getNote(db, note.id)?.status).toBe('candidate');
    db.close();
  });

  it('moves candidate → rejected and stores the reason', () => {
    const db = makeDb();
    const note = createNote(db, { title: 'T', body: '', tags: [], links: [] });
    const rejected = rejectNote(db, note.id, '  Source could not be verified. ');
    expect(rejected.status).toBe('rejected');
    expect(rejected.rejectionReason).toBe('Source could not be verified.');
    db.close();
  });

  it('refuses to reject non-candidate or unknown notes', () => {
    const db = makeDb();
    const note = createNote(db, { title: 'T', body: '', tags: [], links: [] });
    approveNote(db, note.id);
    expectPkvError(() => rejectNote(db, note.id, 'too late'), 'INVALID_STATUS_TRANSITION');
    expectPkvError(
      () => rejectNote(db, '00000000-0000-4000-8000-000000000000', 'nope'),
      'NOTE_NOT_FOUND',
    );
    db.close();
  });
});

describe('approveNote', () => {
  it('moves candidate → verified', () => {
    const db = makeDb();
    const note = createNote(db, { title: 'T', body: '', tags: [], links: [] });
    const approved = approveNote(db, note.id);
    expect(approved.status).toBe('verified');
    db.close();
  });

  it('refuses to approve non-candidate or unknown notes', () => {
    const db = makeDb();
    const note = createNote(db, { title: 'T', body: '', tags: [], links: [] });
    rejectNote(db, note.id, 'bad data');
    expectPkvError(() => approveNote(db, note.id), 'INVALID_STATUS_TRANSITION');
    expectPkvError(
      () => approveNote(db, '00000000-0000-4000-8000-000000000000'),
      'NOTE_NOT_FOUND',
    );
    db.close();
  });

  it('approve isolation: approving A never touches B', () => {
    const db = makeDb();
    const a = createNote(db, { title: 'A', body: 'alpha', tags: ['t1'], links: [] });
    const b = createNote(db, { title: 'B', body: 'beta', tags: ['t2'], links: [] });
    const bBefore = getNote(db, b.id);
    const approved = approveNote(db, a.id);

    expect(approved.status).toBe('verified');
    const bAfter = getNote(db, b.id);
    expect(bAfter?.status).toBe('candidate');
    expect(bAfter?.title).toBe(bBefore?.title);
    expect(bAfter?.body).toBe(bBefore?.body);
    expect(bAfter?.tags).toEqual(bBefore?.tags);
    expect(bAfter?.updatedAt).toBe(bBefore?.updatedAt);
    expect(bAfter?.revisionCount).toBe(0);
    db.close();
  });
});
