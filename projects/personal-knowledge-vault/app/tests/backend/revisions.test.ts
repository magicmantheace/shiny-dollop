/**
 * Revision immutability tests:
 * - rev_no is strictly monotonic per note, oldest first.
 * - revisions capture the post-update state.
 * - a direct UPDATE on the revisions table is rejected at the DB level
 *   (append-only trigger), so history cannot be silently rewritten.
 */
import { describe, expect, it } from 'vitest';
import { createNote, listRevisions, updateNote } from '../../db/notes';
import { makeDb } from './helpers';

describe('revision history', () => {
  it('appends one revision per update with monotonic rev_no', () => {
    const db = makeDb();
    const note = createNote(db, { title: 'v0', body: 'body0', tags: ['t0'], links: [] });

    updateNote(db, note.id, { title: 'v1', changeSummary: 'First correction.' });
    updateNote(db, note.id, { body: 'body2', tags: ['t2'], changeSummary: 'Second correction.' });
    updateNote(db, note.id, { title: 'v3', body: 'body3', changeSummary: 'Third correction.' });

    const revs = listRevisions(db, note.id);
    expect(revs.map((r) => r.revNo)).toEqual([1, 2, 3]);
    expect(revs.map((r) => r.changeSummary)).toEqual([
      'First correction.',
      'Second correction.',
      'Third correction.',
    ]);
    // Revisions capture the NEW state after each update.
    expect(revs[0]).toMatchObject({ title: 'v1', body: 'body0', tags: ['t0'] });
    expect(revs[1]).toMatchObject({ title: 'v1', body: 'body2', tags: ['t2'] });
    expect(revs[2]).toMatchObject({ title: 'v3', body: 'body3', tags: ['t2'] });
    db.close();
  });

  it('keeps rev_no sequences independent per note', () => {
    const db = makeDb();
    const a = createNote(db, { title: 'A', body: '', tags: [], links: [] });
    const b = createNote(db, { title: 'B', body: '', tags: [], links: [] });
    updateNote(db, a.id, { title: 'A2', changeSummary: 'a1' });
    updateNote(db, a.id, { title: 'A3', changeSummary: 'a2' });
    updateNote(db, b.id, { title: 'B2', changeSummary: 'b1' });
    expect(listRevisions(db, a.id).map((r) => r.revNo)).toEqual([1, 2]);
    expect(listRevisions(db, b.id).map((r) => r.revNo)).toEqual([1]);
    db.close();
  });

  it('rejects direct UPDATE of a revision row at the database level', () => {
    const db = makeDb();
    const note = createNote(db, { title: 'v0', body: '', tags: [], links: [] });
    updateNote(db, note.id, { title: 'v1', changeSummary: 'correction' });
    const revId = listRevisions(db, note.id)[0]?.id;
    expect(revId).toBeDefined();

    let thrown: unknown;
    try {
      db.prepare('UPDATE revisions SET title = ? WHERE id = ?').run('forged', revId as string);
    } catch (err) {
      thrown = err;
    }
    expect(thrown).toBeInstanceOf(Error);
    expect(String((thrown as Error).message)).toMatch(/append-only/i);

    // History is unchanged by the attempt.
    expect(listRevisions(db, note.id)[0]?.title).toBe('v1');
    db.close();
  });

  it('revisions are only ever appended by updateNote (count matches updates)', () => {
    const db = makeDb();
    const note = createNote(db, { title: 'v0', body: '', tags: [], links: [] });
    const before = (
      db.prepare('SELECT COUNT(*) AS n FROM revisions').get() as { n: number }
    ).n;
    updateNote(db, note.id, { body: 'b1', changeSummary: 'one' });
    updateNote(db, note.id, { body: 'b2', changeSummary: 'two' });
    const after = (db.prepare('SELECT COUNT(*) AS n FROM revisions').get() as { n: number }).n;
    expect(after - before).toBe(2);
    db.close();
  });
});
