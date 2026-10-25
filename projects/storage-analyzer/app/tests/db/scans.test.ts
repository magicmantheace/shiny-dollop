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
  markRunningScansInterrupted,
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
    expect(rows.map((r) => r.version)).toEqual([1, 2]);
    db.close();
  });

  it('upgrades a v1 database: adds identity/search columns and backfills search keys', () => {
    const db = new DatabaseSync(':memory:');
    // Minimal v1 files table (no dev/ino/path_search), already marked applied.
    db.exec(`
      CREATE TABLE files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER NOT NULL,
        path TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        sha256 TEXT,
        is_symlink INTEGER NOT NULL DEFAULT 0,
        UNIQUE(scan_id, path)
      );
      CREATE TABLE schema_migrations (
        version INTEGER PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at TEXT NOT NULL
      );
      INSERT INTO schema_migrations VALUES (1, 'initial schema', '2026-01-01T00:00:00Z');
      INSERT INTO files (scan_id, path, size_bytes, is_symlink) VALUES (1, '/data/ÉTÉ.txt', 10, 0);
    `);
    runMigrations(db);
    const rows = db.prepare('SELECT version FROM schema_migrations ORDER BY version').all() as Array<{
      version: number;
    }>;
    expect(rows.map((r) => r.version)).toEqual([1, 2]);
    // The pre-existing row must be findable by a Unicode-lowercased query.
    expect(searchFiles(db, 1, 'été').map((h) => h.path)).toEqual(['/data/ÉTÉ.txt']);
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
    // Folder sizes are descendant totals up to the scan root: /data itself
    // aggregates both subfolders and therefore ranks first.
    expect(summary.dirSizes.find((d) => d.path === '/data')).toEqual({
      path: '/data',
      bytes: 1075,
      files: 4,
    });
    // ranked by bytes desc
    expect(summary.dirSizes[0]?.path).toBe('/data');

    const iso = summary.typeSummary.find((t) => t.ext === '.iso');
    expect(iso).toEqual({ ext: '.iso', files: 1, bytes: 900 });
    const txt = summary.typeSummary.find((t) => t.ext === '.txt');
    expect(txt).toEqual({ ext: '.txt', files: 2, bytes: 150 }); // case-insensitive
    const none = summary.typeSummary.find((t) => t.ext === '');
    expect(none).toEqual({ ext: '', files: 1, bytes: 25 });
    db.close();
  });

  it('includes descendant files when calculating folder sizes (regression)', () => {
    const db = makeTestDb();
    const scanId = createScan(db, '/data');
    // /data/large contains ONLY subfolders: part1 and part2 at 600 bytes each.
    recordFile(db, scanId, '/data/large/part1/blob-a.bin', 600, false);
    recordFile(db, scanId, '/data/large/part2/blob-b.bin', 600, false);
    recordFile(db, scanId, '/data/small/blob-c.bin', 900, false);
    updateScanCounters(db, scanId, { files: 3, dirs: 4, bytes: 2100, excluded: 0, symlinks: 0, changed: 0, errors: 0 });

    const summary = getSummary(db, scanId);
    // Before the fix /data/large was absent entirely (each file counted only
    // toward its immediate parent) and /data/small ranked first.
    expect(summary.dirSizes.find((d) => d.path === '/data/large')).toEqual({
      path: '/data/large',
      bytes: 1200,
      files: 2,
    });
    expect(summary.dirSizes.find((d) => d.path === '/data/large/part1')).toEqual({
      path: '/data/large/part1',
      bytes: 600,
      files: 1,
    });
    // The largest CONTAINING folder outranks the flat 900-byte folder, and
    // accumulation stops at the scan root (no '/' entry above it).
    const largeIdx = summary.dirSizes.findIndex((d) => d.path === '/data/large');
    const smallIdx = summary.dirSizes.findIndex((d) => d.path === '/data/small');
    expect(largeIdx).toBeGreaterThanOrEqual(0);
    expect(smallIdx).toBeGreaterThan(largeIdx);
    expect(summary.dirSizes.find((d) => d.path === '/')).toBeUndefined();
    expect(summary.dirSizes.find((d) => d.path === '/data')).toEqual({
      path: '/data',
      bytes: 2100,
      files: 3,
    });
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

  it('excludes hard-link aliases: two paths to one inode form no group', () => {
    const db = makeTestDb();
    const scanId = createScan(db, '/data');
    const h = 'd'.repeat(64);
    // Two directory entries, ONE underlying file (same dev+inode, 4 bytes):
    // deleting one link reclaims 0 bytes, so there is nothing to save.
    const idA = recordFile(db, scanId, '/data/orig.bin', 4, false, { dev: 10, ino: 42 });
    const idB = recordFile(db, scanId, '/data/alias.bin', 4, false, { dev: 10, ino: 42 });
    updateFileHash(db, idA, h);
    updateFileHash(db, idB, h);
    expect(getDuplicateGroups(db, scanId)).toHaveLength(0);
    db.close();
  });

  it('keeps only one path per inode when an independent copy also exists', () => {
    const db = makeTestDb();
    const scanId = createScan(db, '/data');
    const h = 'e'.repeat(64);
    const idA = recordFile(db, scanId, '/data/orig.bin', 4, false, { dev: 10, ino: 42 });
    const idB = recordFile(db, scanId, '/data/alias.bin', 4, false, { dev: 10, ino: 42 });
    const idC = recordFile(db, scanId, '/data/copy.bin', 4, false, { dev: 10, ino: 99 });
    updateFileHash(db, idA, h);
    updateFileHash(db, idB, h);
    updateFileHash(db, idC, h);
    const groups = getDuplicateGroups(db, scanId);
    expect(groups).toHaveLength(1);
    // 2 distinct inodes -> savings = size * (2 - 1), not size * (3 - 1).
    expect(groups[0]?.files).toHaveLength(2);
    expect(
      (groups[0]?.files.includes('/data/orig.bin') ?? false) &&
        (groups[0]?.files.includes('/data/alias.bin') ?? false),
    ).toBe(false);
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

  it('matches non-ASCII names case-insensitively (Unicode-aware on both sides)', () => {
    const db = makeTestDb();
    const scanId = createScan(db, '/data');
    recordFile(db, scanId, '/data/ÉTÉ.txt', 10, false);
    recordFile(db, scanId, '/data/other.doc', 40, false);

    // SQLite lower() is ASCII-only and would leave 'É' unchanged; the stored
    // search key and the query must go through the same JS normalization.
    for (const q of ['été', 'ÉTÉ', 'Été']) {
      const hits = searchFiles(db, scanId, q);
      expect(hits.map((h) => h.path), `query ${q}`).toEqual(['/data/ÉTÉ.txt']);
    }
    db.close();
  });

  it('matches decomposed and precomposed Unicode forms consistently', () => {
    const db = makeTestDb();
    const scanId = createScan(db, '/data');
    // Stored decomposed (E + combining acute), queried precomposed.
    recordFile(db, scanId, '/data/CAFE\u0301.txt', 10, false);
    const hits = searchFiles(db, scanId, 'caf\u00e9');
    expect(hits.map((h) => h.path)).toEqual(['/data/CAFE\u0301.txt']);
    db.close();
  });
});

describe('interrupted scan reconciliation', () => {
  it('closes out scans left running as failed, leaves finished scans untouched', () => {
    const db = makeTestDb();
    const running = createScan(db, '/data/stuck');
    const done = createScan(db, '/data/done');
    finishScan(
      db,
      done,
      'complete',
      { files: 3, dirs: 1, bytes: 42, excluded: 0, symlinks: 0, changed: 0, errors: 0 },
      null,
    );

    expect(markRunningScansInterrupted(db)).toBe(1);

    const stuck = getScan(db, running);
    expect(stuck?.state).toBe('failed');
    expect(stuck?.error).toMatch(/Interrupted/);
    expect(stuck?.finished_at).not.toBeNull();

    const finished = getScan(db, done);
    expect(finished?.state).toBe('complete');
    expect(finished?.error).toBeNull();

    // Idempotent: nothing left in 'running'.
    expect(markRunningScansInterrupted(db)).toBe(0);
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
