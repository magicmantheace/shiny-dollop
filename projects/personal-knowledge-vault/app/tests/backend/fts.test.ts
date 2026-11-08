/**
 * FTS5 availability and index-sync tests:
 * - FTS5 is compiled into the runtime SQLite (required by migrations).
 * - Insert / update / delete keep notes_fts in sync via triggers.
 * - Hostile query syntax (quotes, OR, *, parens) cannot break search.
 */
import { describe, expect, it } from 'vitest';
import { assertFts5Available, runMigrations } from '../../db/migrations';
import { createNote, deleteNote, searchNotes, updateNote } from '../../db/notes';
import { makeDb } from './helpers';
import { DatabaseSync } from 'node:sqlite';

describe('FTS5 availability', () => {
  it('has FTS5 compiled in', () => {
    const db = new DatabaseSync(':memory:');
    expect(() => assertFts5Available(db)).not.toThrow();
    const row = db
      .prepare("SELECT sqlite_compileoption_used('ENABLE_FTS5') AS enabled")
      .get() as { enabled: number };
    expect(row.enabled).toBe(1);
    db.close();
  });

  it('migrations fail loudly without FTS5 only when absent (sanity: migrations succeed here)', () => {
    const db = new DatabaseSync(':memory:');
    expect(() => runMigrations(db)).not.toThrow();
    db.close();
  });
});

describe('FTS5 sync via triggers', () => {
  it('finds notes by title, body and tag tokens', () => {
    const db = makeDb();
    const note = createNote(db, {
      title: 'Sourdough starter guide',
      body: 'Feed the starter with rye flour every twelve hours.',
      tags: ['baking', 'fermentation'],
      links: [],
    });
    expect(searchNotes(db, 'sourdough').map((n) => n.id)).toContain(note.id);
    expect(searchNotes(db, 'rye').map((n) => n.id)).toContain(note.id);
    expect(searchNotes(db, 'fermentation').map((n) => n.id)).toContain(note.id);
    expect(searchNotes(db, 'nonexistentterm').map((n) => n.id)).not.toContain(note.id);
    db.close();
  });

  it('reflects edits: old terms vanish, new terms appear', () => {
    const db = makeDb();
    const note = createNote(db, {
      title: 'Old title about telescopes',
      body: 'Aperture matters most.',
      tags: ['astronomy'],
      links: [],
    });
    expect(searchNotes(db, 'telescopes').map((n) => n.id)).toContain(note.id);

    updateNote(db, note.id, {
      title: 'New title about microscopes',
      body: 'Magnification matters most.',
      tags: ['optics'],
      changeSummary: 'Swapped topic for test.',
    });

    const ids = (q: string) => searchNotes(db, q).map((n) => n.id);
    expect(ids('microscopes')).toContain(note.id);
    expect(ids('magnification')).toContain(note.id);
    expect(ids('optics')).toContain(note.id);
    expect(ids('telescopes')).not.toContain(note.id);
    expect(ids('aperture')).not.toContain(note.id);
    expect(ids('astronomy')).not.toContain(note.id);
    db.close();
  });

  it('removes deleted notes from the index', () => {
    const db = makeDb();
    const note = createNote(db, {
      title: 'Ephemeral planning note',
      body: 'Temporary content here.',
      tags: [],
      links: [],
    });
    expect(searchNotes(db, 'ephemeral').map((n) => n.id)).toContain(note.id);
    expect(deleteNote(db, note.id)).toBe(true);
    expect(searchNotes(db, 'ephemeral')).toHaveLength(0);
    db.close();
  });

  it('survives hostile query syntax without throwing', () => {
    const db = makeDb();
    createNote(db, {
      title: 'Plain note',
      body: 'Nothing special inside.',
      tags: [],
      links: [],
    });
    for (const hostile of [
      'foo OR bar',
      '"unclosed quote',
      'a*b',
      '(parens)',
      'NEAR(foo bar)',
      'title:foo',
      '"; DROP TABLE notes; --',
    ]) {
      expect(() => searchNotes(db, hostile)).not.toThrow();
    }
    db.close();
  });

  it('ranks better matches first', () => {
    const db = makeDb();
    const weak = createNote(db, {
      title: 'Gardening journal',
      body: 'The tomato plants need watering daily.',
      tags: [],
      links: [],
    });
    const strong = createNote(db, {
      title: 'Tomato tomato tomato',
      body: 'tomato tomato tomato tomato tomato',
      tags: [],
      links: [],
    });
    const results = searchNotes(db, 'tomato');
    expect(results[0]?.id).toBe(strong.id);
    expect(results.map((n) => n.id)).toContain(weak.id);
    db.close();
  });
});
