/**
 * Backup import validation tests:
 * - corrupt JSON → BACKUP_CORRUPT
 * - unknown major version → BACKUP_VERSION_UNSUPPORTED
 * - schema/shape violations → BACKUP_IMPORT_INVALID
 * - self-links and dangling links in the payload are rejected
 * - re-importing the same payload is idempotent ({ imported: 0, skipped: n })
 */
import { describe, expect, it } from 'vitest';
import { PkvError } from '../../shared/errors';
import { exportBackup, importBackup } from '../../db/backup';
import { createNote, listNotes, listRevisions, searchNotes, updateNote } from '../../db/notes';
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

function buildSampleExport(): string {
  const db = makeDb();
  const a = createNote(db, {
    title: 'Sourdough starter',
    body: 'Feed with rye flour.',
    tags: ['baking'],
    source: { title: 'Bread book', author: 'B. Baker', url: 'https://example.invalid/bread' },
    links: [],
  });
  createNote(db, {
    title: 'Rye flour notes',
    body: 'Stone-milled works best.',
    tags: ['baking', 'ingredients'],
    links: [a.id],
  });
  updateNote(db, a.id, { body: 'Feed with rye flour twice daily.', changeSummary: 'Frequency fix.' });
  const payload = exportBackup(db, '2026-10-23T15:00:00.000Z');
  db.close();
  return payload;
}

describe('importBackup validation', () => {
  it('rejects garbage JSON with BACKUP_CORRUPT', () => {
    const db = makeDb();
    expectPkvError(() => importBackup(db, 'this is not json {{{'), 'BACKUP_CORRUPT');
    expectPkvError(() => importBackup(db, ''), 'BACKUP_CORRUPT');
    expect(listNotes(db)).toHaveLength(0);
    db.close();
  });

  it('rejects unknown major versions with BACKUP_VERSION_UNSUPPORTED', () => {
    const db = makeDb();
    for (const version of ['2.0.0', '0.9.0', 'banana']) {
      const payload = JSON.stringify({ formatVersion: version, exportedAt: 'x', notes: [] });
      expectPkvError(() => importBackup(db, payload), 'BACKUP_VERSION_UNSUPPORTED');
    }
    expect(listNotes(db)).toHaveLength(0);
    db.close();
  });

  it('rejects schema violations with BACKUP_IMPORT_INVALID', () => {
    const db = makeDb();
    const cases: unknown[] = [
      { formatVersion: '1.0.0', exportedAt: 'x' }, // missing notes
      { formatVersion: '1.0.0', exportedAt: 'x', notes: 'nope' }, // notes not array
      { formatVersion: '1.0.0', exportedAt: 'x', notes: [{ id: 'not-a-uuid' }] }, // bad note
      { formatVersion: '1.0.0', exportedAt: 'x', notes: [] }, // valid envelope, zero notes
    ];
    expectPkvError(() => importBackup(db, JSON.stringify(cases[0])), 'BACKUP_IMPORT_INVALID');
    expectPkvError(() => importBackup(db, JSON.stringify(cases[1])), 'BACKUP_IMPORT_INVALID');
    expectPkvError(() => importBackup(db, JSON.stringify(cases[2])), 'BACKUP_IMPORT_INVALID');
    // The valid empty envelope imports cleanly.
    expect(importBackup(db, JSON.stringify(cases[3]))).toEqual({ imported: 0, skipped: 0 });
    expect(listNotes(db)).toHaveLength(0);
    db.close();
  });

  it('rejects self-links and dangling links in the payload', () => {
    const db = makeDb();
    const good = JSON.parse(buildSampleExport()) as {
      formatVersion: string;
      exportedAt: string;
      notes: { id: string; links: string[] }[];
    };

    const selfLinked = structuredClone(good);
    selfLinked.notes[0]!.links = [selfLinked.notes[0]!.id];
    expectPkvError(() => importBackup(db, JSON.stringify(selfLinked)), 'BACKUP_IMPORT_INVALID');

    const dangling = structuredClone(good);
    dangling.notes[1]!.links = ['11111111-1111-4111-8111-111111111111'];
    expectPkvError(() => importBackup(db, JSON.stringify(dangling)), 'BACKUP_IMPORT_INVALID');

    // Both failures were atomic: nothing landed.
    expect(listNotes(db)).toHaveLength(0);
    db.close();
  });
});

describe('importBackup round-trip', () => {
  it('imports notes, sources, tags, links and revisions', () => {
    const payload = buildSampleExport();
    const db = makeDb();
    const result = importBackup(db, payload);
    expect(result).toEqual({ imported: 2, skipped: 0 });

    const notes = listNotes(db);
    expect(notes).toHaveLength(2);
    const sourdough = notes.find((n) => n.title === 'Sourdough starter');
    expect(sourdough).toBeDefined();
    expect(sourdough?.source?.title).toBe('Bread book');
    expect(sourdough?.tags).toContain('baking');
    expect(sourdough?.revisionCount).toBe(1);
    const revs = listRevisions(db, sourdough!.id);
    expect(revs[0]?.changeSummary).toBe('Frequency fix.');

    const rye = notes.find((n) => n.title === 'Rye flour notes');
    expect(rye?.links.map((l) => l.id)).toEqual([sourdough!.id]);

    // FTS index works on imported rows.
    expect(searchNotes(db, 'rye').map((n) => n.title)).toContain('Sourdough starter');
    db.close();
  });

  it('is idempotent: re-import skips existing notes', () => {
    const payload = buildSampleExport();
    const db = makeDb();
    expect(importBackup(db, payload)).toEqual({ imported: 2, skipped: 0 });
    expect(importBackup(db, payload)).toEqual({ imported: 0, skipped: 2 });
    expect(listNotes(db)).toHaveLength(2);
    db.close();
  });
});

describe('exportBackup determinism', () => {
  it('produces byte-identical output for the same data and timestamp', () => {
    const payload = buildSampleExport();
    const db = makeDb();
    importBackup(db, payload);
    const stamp = '2026-10-23T15:00:00.000Z';
    const first = exportBackup(db, stamp);
    const second = exportBackup(db, stamp);
    expect(first).toBe(second);
    // And it matches the original payload byte-for-byte.
    expect(first).toBe(payload);
    db.close();
  });

  it('carries the versioned envelope', () => {
    const db = makeDb();
    createNote(db, { title: 'T', body: '', tags: [], links: [] });
    const parsed = JSON.parse(exportBackup(db, '2026-01-01T00:00:00.000Z')) as {
      formatVersion: string;
      exportedAt: string;
      notes: unknown[];
    };
    expect(parsed.formatVersion).toBe('1.0.0');
    expect(parsed.exportedAt).toBe('2026-01-01T00:00:00.000Z');
    expect(parsed.notes).toHaveLength(1);
    db.close();
  });
});
