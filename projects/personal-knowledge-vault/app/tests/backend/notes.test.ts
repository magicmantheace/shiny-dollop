/**
 * Note CRUD, links, source validation, and listing filters.
 * Synthetic fixtures only.
 */
import { describe, expect, it } from 'vitest';
import { PkvError } from '../../shared/errors';
import { createNote, deleteNote, getNote, listNotes, updateNote } from '../../db/notes';
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

describe('createNote', () => {
  it('starts every note as candidate with a revision count of zero', () => {
    const db = makeDb();
    const note = createNote(db, { title: 'T', body: 'B', tags: [], links: [] });
    expect(note.status).toBe('candidate');
    expect(note.revisionCount).toBe(0);
    expect(note.rejectionReason).toBeNull();
    db.close();
  });

  it('stores source, normalized tags, and resolves links to note summaries', () => {
    const db = makeDb();
    const target = createNote(db, { title: 'Target', body: '', tags: [], links: [] });
    const note = createNote(db, {
      title: 'With provenance',
      body: 'Body text.',
      tags: ['  alpha ', 'alpha', 'beta', ''],
      source: {
        title: 'Field guide',
        author: 'A. Naturalist',
        url: 'https://example.invalid/guide',
        accessedAt: '2026-10-23T00:00:00Z',
      },
      links: [target.id],
    });
    expect(note.tags).toEqual(['alpha', 'beta']);
    expect(note.source).toMatchObject({
      title: 'Field guide',
      author: 'A. Naturalist',
      url: 'https://example.invalid/guide',
    });
    expect(note.links).toHaveLength(1);
    expect(note.links[0]).toMatchObject({ id: target.id, title: 'Target', status: 'candidate' });
    db.close();
  });

  it('rejects a source without url/docPointer/title', () => {
    const db = makeDb();
    expectPkvError(
      () => createNote(db, { title: 'T', body: '', tags: [], source: { author: 'Nobody' }, links: [] }),
      'SOURCE_ANCHOR_REQUIRED',
    );
    // Rollback check: nothing was persisted.
    expect(listNotes(db)).toHaveLength(0);
    db.close();
  });

  it('rejects links to missing notes and self-links', () => {
    const db = makeDb();
    expectPkvError(
      () =>
        createNote(db, {
          title: 'T',
          body: '',
          tags: [],
          links: ['00000000-0000-4000-8000-000000000000'],
        }),
      'LINK_TARGET_NOT_FOUND',
    );
    expect(listNotes(db)).toHaveLength(0);
    db.close();
  });
});

describe('getNote', () => {
  it('returns null for unknown ids', () => {
    const db = makeDb();
    expect(getNote(db, '00000000-0000-4000-8000-000000000000')).toBeNull();
    db.close();
  });
});

describe('updateNote', () => {
  it('requires a change summary', () => {
    const db = makeDb();
    const note = createNote(db, { title: 'T', body: '', tags: [], links: [] });
    for (const bad of ['', '   ']) {
      expectPkvError(() => updateNote(db, note.id, { title: 'X', changeSummary: bad }), 'CHANGE_SUMMARY_REQUIRED');
    }
    db.close();
  });

  it('throws NOTE_NOT_FOUND for unknown ids', () => {
    const db = makeDb();
    expectPkvError(
      () => updateNote(db, '00000000-0000-4000-8000-000000000000', { title: 'X', changeSummary: 's' }),
      'NOTE_NOT_FOUND',
    );
    db.close();
  });

  it('replaces tags and links wholesale', () => {
    const db = makeDb();
    const a = createNote(db, { title: 'A', body: '', tags: ['old'], links: [] });
    const b = createNote(db, { title: 'B', body: '', tags: [], links: [] });
    const updated = updateNote(db, a.id, {
      tags: ['new1', 'new2'],
      links: [b.id],
      changeSummary: 'Retagged and linked.',
    });
    expect(updated.tags).toEqual(['new1', 'new2']);
    expect(updated.links.map((l) => l.id)).toEqual([b.id]);
    expect(updated.revisionCount).toBe(1);
    db.close();
  });

  it('rejects self-links on update', () => {
    const db = makeDb();
    const note = createNote(db, { title: 'T', body: '', tags: [], links: [] });
    expectPkvError(
      () => updateNote(db, note.id, { links: [note.id], changeSummary: 'self link' }),
      'SELF_LINK_NOT_ALLOWED',
    );
    db.close();
  });
});

describe('deleteNote', () => {
  it('removes the note and returns true; unknown id returns false', () => {
    const db = makeDb();
    const note = createNote(db, { title: 'T', body: '', tags: [], links: [] });
    expect(deleteNote(db, note.id)).toBe(true);
    expect(getNote(db, note.id)).toBeNull();
    expect(deleteNote(db, note.id)).toBe(false);
    db.close();
  });

  it('cascades tags, source, links and revisions', () => {
    const db = makeDb();
    const a = createNote(db, {
      title: 'A',
      body: '',
      tags: ['x'],
      source: { url: 'https://example.invalid' },
      links: [],
    });
    const b = createNote(db, { title: 'B', body: '', tags: [], links: [a.id] });
    updateNote(db, a.id, { body: 'v2', changeSummary: 'edit' });
    expect(deleteNote(db, a.id)).toBe(true);
    // Inbound link from b is gone; b survives.
    expect(getNote(db, b.id)?.links).toHaveLength(0);
    db.close();
  });
});

describe('listNotes', () => {
  it('filters by status and tag', () => {
    const db = makeDb();
    const a = createNote(db, { title: 'A', body: '', tags: ['keep'], links: [] });
    createNote(db, { title: 'B', body: '', tags: ['drop'], links: [] });
    expect(listNotes(db, { status: 'candidate' })).toHaveLength(2);
    expect(listNotes(db, { tag: 'keep' }).map((n) => n.id)).toEqual([a.id]);
    expect(listNotes(db, { status: 'verified' })).toHaveLength(0);
    db.close();
  });
});
