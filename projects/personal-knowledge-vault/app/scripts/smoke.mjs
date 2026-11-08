/**
 * Backend smoke test: exercises the compiled backend (dist/) against an
 * in-memory database. Run `npm run build` first, then `npm run smoke`.
 * Exits non-zero on any failure. No Electron window is launched.
 */
import { DatabaseSync } from 'node:sqlite';
import { runMigrations } from '../dist/db/migrations.js';
import { createNote, getNote, searchNotes, updateNote } from '../dist/db/notes.js';
import { approveNote } from '../dist/db/review.js';
import { exportBackup, importBackup } from '../dist/db/backup.js';

function assert(cond, label) {
  if (!cond) {
    console.error(`SMOKE FAIL: ${label}`);
    process.exit(1);
  }
  console.log(`smoke ok: ${label}`);
}

const db = new DatabaseSync(':memory:');
db.exec('PRAGMA foreign_keys = ON;');
runMigrations(db);
assert(true, 'migrations applied (schema v1, FTS5 present)');

const note = createNote(db, {
  title: 'Smoke note',
  body: 'The quick brown fox.',
  tags: ['smoke'],
  source: { title: 'Test source' },
  links: [],
});
assert(note.status === 'candidate', 'note created as candidate');
assert(note.source?.title === 'Test source', 'source stored');

const approved = approveNote(db, note.id);
assert(approved.status === 'verified', 'approve moves candidate → verified');
assert(searchNotes(db, 'quick').length === 1, 'FTS search finds the note');

const revised = updateNote(db, note.id, { body: 'The quick red fox.', changeSummary: 'color fix' });
assert(revised.revisionCount === 1, 'update appends one revision');
assert(getNote(db, note.id)?.body === 'The quick red fox.', 'get returns revised body');

const payload = exportBackup(db, '2026-10-23T00:00:00.000Z');
assert(JSON.parse(payload).formatVersion === '1.0.0', 'export envelope versioned');

const db2 = new DatabaseSync(':memory:');
db2.exec('PRAGMA foreign_keys = ON;');
runMigrations(db2);
const result = importBackup(db2, payload);
assert(result.imported === 1 && result.skipped === 0, 'import round-trip restores the note');
assert(getNote(db2, note.id)?.status === 'verified', 'imported note keeps verified status');

db.close();
db2.close();
console.log('SMOKE PASS: all backend checks green');
