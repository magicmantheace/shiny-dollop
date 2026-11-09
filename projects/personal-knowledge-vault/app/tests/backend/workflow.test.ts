/**
 * End-to-end backend workflow (no Electron runtime needed):
 * create → approve → search → revise → export → import round-trip.
 * Synthetic fixtures only.
 */
import { describe, expect, it } from 'vitest';
import { exportBackup, importBackup } from '../../db/backup';
import { createNote, getNote, listNotes, listRevisions, searchNotes, updateNote } from '../../db/notes';
import { approveNote } from '../../db/review';
import { makeDb } from './helpers';

describe('full review workflow', () => {
  it('create → approve → search → revise → export → import', () => {
    const db = makeDb();

    // 1. Create two candidate notes with provenance; B links to A.
    const a = createNote(db, {
      title: 'Cold brew ratio',
      body: 'One part coffee to eight parts water, steeped twelve hours.',
      tags: ['coffee', 'recipe'],
      source: {
        title: 'Home brewing handbook',
        author: 'C. Barista',
        url: 'https://example.invalid/brew',
        accessedAt: '2026-10-20T09:00:00Z',
      },
      links: [],
    });
    const b = createNote(db, {
      title: 'Grinder settings',
      body: 'Coarse grind for cold brew, like raw sugar.',
      tags: ['coffee', 'equipment'],
      links: [a.id],
    });
    expect(a.status).toBe('candidate');
    expect(b.links.map((l) => l.id)).toEqual([a.id]);

    // 2. Approve only A.
    const approvedA = approveNote(db, a.id);
    expect(approvedA.status).toBe('verified');
    expect(getNote(db, b.id)?.status).toBe('candidate');

    // 3. Search finds both under the coffee tag term.
    const hits = searchNotes(db, 'coffee');
    expect(hits.map((n) => n.id).sort()).toEqual([a.id, b.id].sort());
    expect(searchNotes(db, 'coffee', { status: 'verified' }).map((n) => n.id)).toEqual([a.id]);

    // 4. Revise A: one immutable revision row appears.
    const revised = updateNote(db, a.id, {
      body: 'One part coffee to ten parts water, steeped twelve hours.',
      changeSummary: 'Corrected ratio after taste test.',
    });
    expect(revised.revisionCount).toBe(1);
    expect(listRevisions(db, a.id)).toHaveLength(1);

    // 5. Export and import into a fresh database.
    const payload = exportBackup(db, '2026-10-23T15:39:00.000Z');
    db.close();

    const db2 = makeDb();
    const result = importBackup(db2, payload);
    expect(result).toEqual({ imported: 2, skipped: 0 });

    const importedA = getNote(db2, a.id);
    expect(importedA?.status).toBe('verified');
    expect(importedA?.body).toContain('ten parts water');
    expect(importedA?.source?.title).toBe('Home brewing handbook');
    expect(importedA?.tags).toEqual(['coffee', 'recipe']);
    expect(importedA?.revisionCount).toBe(1);
    expect(listRevisions(db2, a.id)[0]?.changeSummary).toBe('Corrected ratio after taste test.');

    const importedB = getNote(db2, b.id);
    expect(importedB?.status).toBe('candidate');
    expect(importedB?.links.map((l) => l.id)).toEqual([a.id]);

    // Search and listing survive the restore.
    expect(searchNotes(db2, 'brew').map((n) => n.id)).toContain(a.id);
    expect(listNotes(db2, { status: 'verified' }).map((n) => n.id)).toEqual([a.id]);
    db2.close();
  });
});
