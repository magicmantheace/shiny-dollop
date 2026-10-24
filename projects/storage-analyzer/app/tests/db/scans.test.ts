/**
 * Database layer tests: idempotent migrations, scan CRUD, and the result
 * queries behind results.summary / results.duplicates / results.search.
 */
import { describe, expect, it } from 'vitest';
import { DatabaseSync } from 'node:sqlite';
import { makeTestDb } from '../helpers';
import { runMigrations } from '../../electron/main/db/migrations';
import {
  createScan,
  deleteFile,
  finishScan,
  getDuplicateGroups,
  getScan,
  getSummary,
  listScanErrors,
  listScans,
  recordFile,
  recordScanError,
  searchFiles,
  updateFileHash,
  updateScanCounters,
  SEARCH_RESULT_LIMIT,
} from '../../electron/main/db/scans';

describe('migrations', () => {
  it('are idempotent: running twice is safe', () => {
    const db = new DatabaseSync(':memory:');
    runMigrations(db);
    runMigrations(db);
    const rows = db.prepare('SELECT version FROM schema_migrations ORDER BY version').all() as Array<{
      version: number;
    }>;
    expect(rows.map((r) => r.version)).toEqual([1]);
    db.close();
  });
});

describe('scan rows', () => {
  it('creates, updates counters, finishes, and lists newest-first', () => {
    const db = makeTestDb();
    const first = createScan(db, '/tmp/a');
    const second = createScan(db, '/tmp/b');
    expect(second).toBeGreaterThan(first);

    updateScanCounters(db, first, { files: 5, dirs: 2, bytes: 100, excluded: 1, symlinks: 0, changed: 0, errors: 0 });
    finishScan(db, first, 'complete', { files: 5, dirs: 2, bytes: 100, excluded: 1, symlinks: 0, changed: 0, errors: 0 }, null);

    const row = getScan(db, first);
    expect(row?.state).toBe('complete');
    expect(row?.files).toBe(5);
    expect(row?.finished_at).not.toBeNull();

    const running = getScan(db, second);
    expect(running?.state).toBe('running');
    expect(running?.finished_at).toBeNull();

    const list = listScans(db);
    expect(list.map((s) => s.id)).toEqual([second, first]);
    expect(list[0]?.rootPath).toBe('/tmp/b');
    db.close();
  });

  it('returns null for unknown scan ids', () => {
    const db = makeTestDb();
    expect(getScan(db, 999)).toBeNull();
    db.close();
  });
});

describe('summary queries', () => {
  it('computes largest files, dir sizes, and type summary', () => {
    const db = makeTestDb();
    const scanId = createScan(db, '/data');
    recordFile(db, scanId, '/data/a/big.iso', 900, false);
    recordFile(db, scanId, '/data/a/mid.txt', 100, false);
    recordFile(db, scanId, '/data/b/small.TXT', 50, false);
    recordFile(db, scanId, '/data/b/noext', 25, false);
    recordFile(db, scanId, '/data/link', 10, true); // symlink: excluded from totals
    updateScanCounters(db, scanId, { files: 4, dirs: 2, bytes: 1075, excluded: 0, symlinks: 1, changed: 0, errors: 0 });

    const summary = getSummary(db, scanId);
    expect(summary.totalFiles).toBe(4);
    expect(summary.totalBytes).toBe(1075);
    expect(summary.largestFiles[0]).toEqual({ path: '/data/a/big.iso', size: 900 });
    expect(summary.largestFiles).toHaveLength(4);

    const dirA = summary.dirSizes.find((d) => d.path === '/data/a');
    expect(dirA).toEqual({ path: '/data/a', bytes: 1000, files: 2 });
    const dirB = summary.dirSizes.find((d) => d.path === '/data/b');
    expect(dirB).toEqual({ path: '/data/b', bytes: 75, files: 2 });
    // ranked by bytes desc
    expect(summary.dirSizes[0]?.path).toBe('/data/a');

    const iso = summary.typeSummary.find((t) => t.ext === '.iso');
    expect(iso).toEqual({ ext: '.iso', files: 1, bytes: 900 });
    const txt = summary.typeSummary.find((t) => t.ext === '.txt');
    expect(txt).toEqual({ ext: '.txt', files: 2, bytes: 150 }); // case-insensitive
    const none = summary.typeSummary.find((t) => t.ext === '');
    expect(none).toEqual({ ext: '', files: 1, bytes: 25 });
    db.close();
  });
});

describe('duplicate queries', () => {
  it('returns only hash-confirmed groups (>=2 identical sha256)', () => {
    const db = makeTestDb();
    const scanId = createScan(db, '/data');
    const h1 = 'a'.repeat(64);
    const h2 = 'b'.repeat(64);
    const idA = recordFile(db, scanId, '/data/x1.bin', 100, false);
    const idB = recordFile(db, scanId, '/data/x2.bin', 100, false);
    const idC = recordFile(db, scanId, '/data/y.bin', 100, false); // same size, other hash
    const idD = recordFile(db, scanId, '/data/z.bin', 200, false); // hashed but alone
    updateFileHash(db, idA, h1);
    updateFileHash(db, idB, h1);
    updateFileHash(db, idC, h2);
    updateFileHash(db, idD, h1.slice(0, 63) + 'f');

    const groups = getDuplicateGroups(db, scanId);
    expect(groups).toHaveLength(1);
    expect(groups[0]).toEqual({ sizeBytes: 100, sha256: h1, files: ['/data/x1.bin', '/data/x2.bin'] });

    // A changed-then-deleted file can never form a group.
    deleteFile(db, idB);
    expect(getDuplicateGroups(db, scanId)).toHaveLength(0);
    db.close();
  });

  it('excludes symlinks from duplicate groups', () => {
    const db = makeTestDb();
    const scanId = createScan(db, '/data');
    const h = 'c'.repeat(64);
    const idA = recordFile(db, scanId, '/data/real.bin', 50, false);
    const idL = recordFile(db, scanId, '/data/link.bin', 50, true);
    updateFileHash(db, idA, h);
    updateFileHash(db, idL, h);
    expect(getDuplicateGroups(db, scanId)).toHaveLength(0);
    db.close();
  });
});

describe('search', () => {
  it('is case-insensitive, treats % and _ literally, and caps at 500', () => {
    const db = makeTestDb();
    const scanId = createScan(db, '/data');
    recordFile(db, scanId, '/data/Photos/Vacation1.PNG', 10, false);
    recordFile(db, scanId, '/data/photos/vacation2.png', 20, false);
    recordFile(db, scanId, '/data/100%_real.txt', 30, false);
    recordFile(db, scanId, '/data/other.doc', 40, false);

    const hits = searchFiles(db, scanId, 'photo');
    expect(hits.map((h) => h.path).sort()).toEqual([
      '/data/Photos/Vacation1.PNG',
      '/data/photos/vacation2.png',
    ]);

    // Literal % and _ must not act as wildcards.
    const literal = searchFiles(db, scanId, '100%_real');
    expect(literal).toHaveLength(1);
    expect(literal[0]?.path).toBe('/data/100%_real.txt');

    // Cap: insert more than the limit of matching rows.
    for (let i = 0; i < SEARCH_RESULT_LIMIT + 100; i++) {
      recordFile(db, scanId, `/data/bulk/match-${i}.txt`, 1, false);
    }
    expect(searchFiles(db, scanId, 'match-')).toHaveLength(SEARCH_RESULT_LIMIT);
    db.close();
  });
});

describe('scan errors', () => {
  it('records and lists per-path error codes', () => {
    const db = makeTestDb();
    const scanId = createScan(db, '/data');
    recordScanError(db, scanId, '/data/denied', 'EACCES');
    recordScanError(db, scanId, '/data/loop', 'DIRECTORY_LOOP');
    expect(listScanErrors(db, scanId)).toEqual([
      { path: '/data/denied', code: 'EACCES' },
      { path: '/data/loop', code: 'DIRECTORY_LOOP' },
    ]);
    db.close();
  });
});
