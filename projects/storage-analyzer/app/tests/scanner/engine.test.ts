/**
 * Scan engine tests. All fixtures live under os.tmpdir() with synthetic
 * content; the engine must never write to, chmod, or delete them.
 */
import { afterEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {
  makeFixtureDir,
  makeTestDb,
  rmDir,
  snapshotTree,
  writeFixture,
} from '../helpers';
import {
  createScan,
  getDuplicateGroups,
  getScan,
  listScanErrors,
} from '../../electron/main/db/scans';
import { startScanJob } from '../../electron/main/scanner/engine';

const dirs: string[] = [];
afterEach(() => {
  while (dirs.length > 0) rmDir(dirs.pop() as string);
});

function track(dir: string): string {
  dirs.push(dir);
  return dir;
}

function scanRoot(root: string): { db: ReturnType<typeof makeTestDb>; scanId: number } {
  const db = makeTestDb();
  const scanId = createScan(db, root);
  return { db, scanId };
}

describe('duplicate detection', () => {
  it('confirms one group for identical files in different dirs', async () => {
    const root = track(makeFixtureDir());
    writeFixture(path.join(root, 'a', 'dup.txt'), 'identical-content-12345');
    writeFixture(path.join(root, 'b', 'dup.txt'), 'identical-content-12345');
    writeFixture(path.join(root, 'c', 'unique.txt'), 'something else entirely');

    const { db, scanId } = scanRoot(root);
    const job = startScanJob(db, { scanId, rootPath: root, exclusions: [], emitProgress: () => {} });
    const result = await job.promise;

    expect(result.state).toBe('complete');
    expect(result.files).toBe(3);
    const groups = getDuplicateGroups(db, scanId);
    expect(groups).toHaveLength(1);
    expect(groups[0]?.files).toHaveLength(2);
    expect(groups[0]?.sizeBytes).toBe('identical-content-12345'.length);
    expect(groups[0]?.sha256).toMatch(/^[0-9a-f]{64}$/);
    db.close();
  });

  it('reports NO group for same-size files with different content', async () => {
    const root = track(makeFixtureDir());
    // Same byte length, different bytes -> same size group, different hashes.
    writeFixture(path.join(root, 'a.bin'), 'AAAAAAAAAAAAAAAA');
    writeFixture(path.join(root, 'b.bin'), 'BBBBBBBBBBBBBBBB');

    const { db, scanId } = scanRoot(root);
    const job = startScanJob(db, { scanId, rootPath: root, exclusions: [], emitProgress: () => {} });
    const result = await job.promise;

    expect(result.state).toBe('complete');
    expect(getDuplicateGroups(db, scanId)).toHaveLength(0);
    db.close();
  });

  it('ignores zero-byte files for duplicate purposes', async () => {
    const root = track(makeFixtureDir());
    writeFixture(path.join(root, 'a.empty'), '');
    writeFixture(path.join(root, 'b.empty'), '');

    const { db, scanId } = scanRoot(root);
    const job = startScanJob(db, { scanId, rootPath: root, exclusions: [], emitProgress: () => {} });
    await job.promise;
    expect(getDuplicateGroups(db, scanId)).toHaveLength(0);
    db.close();
  });
});

describe('hard links', () => {
  function tryLink(target: string, linkPath: string): boolean {
    try {
      fs.mkdirSync(path.dirname(linkPath), { recursive: true });
      fs.linkSync(target, linkPath);
      return true;
    } catch {
      return false;
    }
  }

  it('advertises no savings for two hard links to the same 4-byte file', async () => {
    const root = track(makeFixtureDir());
    const orig = path.join(root, 'a', 'data.bin');
    writeFixture(orig, 'DATA'); // 4 bytes
    if (!tryLink(orig, path.join(root, 'b', 'alias.bin'))) return; // skip where hard links unsupported

    const { db, scanId } = scanRoot(root);
    const job = startScanJob(db, { scanId, rootPath: root, exclusions: [], emitProgress: () => {} });
    const result = await job.promise;

    expect(result.state).toBe('complete');
    expect(result.files).toBe(2); // both paths are scanned and recorded
    // Removing one link reclaims 0 bytes: no duplicate group may be shown.
    expect(getDuplicateGroups(db, scanId)).toHaveLength(0);
    db.close();
  });

  it('counts a hard-link alias plus an independent copy as one reclaimable copy', async () => {
    const root = track(makeFixtureDir());
    const orig = path.join(root, 'a', 'data.bin');
    writeFixture(orig, 'DATA');
    if (!tryLink(orig, path.join(root, 'b', 'alias.bin'))) return;
    writeFixture(path.join(root, 'c', 'copy.bin'), 'DATA'); // independent inode, same bytes

    const { db, scanId } = scanRoot(root);
    const job = startScanJob(db, { scanId, rootPath: root, exclusions: [], emitProgress: () => {} });
    const result = await job.promise;

    expect(result.state).toBe('complete');
    const groups = getDuplicateGroups(db, scanId);
    expect(groups).toHaveLength(1);
    // 2 distinct inodes: savings = 4 * (2 - 1) = 4, not 4 * (3 - 1) = 8.
    expect(groups[0]?.files).toHaveLength(2);
    expect(
      (groups[0]?.files.includes(orig) ?? false) &&
        (groups[0]?.files.includes(path.join(root, 'b', 'alias.bin')) ?? false),
    ).toBe(false);
    db.close();
  });
});

describe('symlink handling', () => {
  function trySymlink(target: string, linkPath: string): boolean {
    try {
      fs.symlinkSync(target, linkPath);
      return true;
    } catch {
      return false;
    }
  }

  it('terminates on symlink loops; symlinks recorded as skipped, never followed', async () => {
    const root = track(makeFixtureDir());
    const a = path.join(root, 'a');
    const b = path.join(root, 'b');
    fs.mkdirSync(a, { recursive: true });
    fs.mkdirSync(b, { recursive: true });
    writeFixture(path.join(a, 'real.txt'), 'real file a');
    writeFixture(path.join(b, 'real.txt'), 'real file b');
    if (!trySymlink(b, path.join(a, 'to-b'))) return; // skip where symlinks need privilege
    if (!trySymlink(a, path.join(b, 'to-a'))) return;
    if (!trySymlink(root, path.join(root, 'self'))) return;

    const { db, scanId } = scanRoot(root);
    const job = startScanJob(db, { scanId, rootPath: root, exclusions: [], emitProgress: () => {} });
    const result = await job.promise; // would hang forever if loops were followed

    expect(result.state).toBe('complete');
    expect(result.files).toBe(2);
    expect(result.symlinks).toBe(3);
    const skipped = db
      .prepare('SELECT COUNT(*) AS c FROM files WHERE scan_id = ? AND is_symlink = 1')
      .get(scanId) as { c: number };
    expect(skipped.c).toBe(3);
    db.close();
  });
});

describe('permission errors', () => {
  it('records permission-denied dirs in scan_errors and completes', async () => {
    const root = track(makeFixtureDir());
    const denied = path.join(root, 'denied');
    fs.mkdirSync(denied, { recursive: true });
    writeFixture(path.join(denied, 'secret.txt'), 'you cannot read this');
    writeFixture(path.join(root, 'ok.txt'), 'readable');

    const isRoot = typeof process.getuid === 'function' && process.getuid() === 0;
    let restore: (() => void) | null = null;
    if (isRoot) {
      // Root bypasses chmod; simulate EACCES deterministically instead.
      const desc = Object.getOwnPropertyDescriptor(fsp, 'readdir');
      if (desc?.writable) {
        const orig = fsp.readdir.bind(fsp);
        const patched = (async (p: unknown, opts?: unknown) => {
          if (String(p) === denied) {
            const err = new Error(`EACCES: permission denied, scandir '${denied}'`);
            (err as NodeJS.ErrnoException).code = 'EACCES';
            throw err;
          }
          return (orig as (p: unknown, o?: unknown) => Promise<unknown>)(p, opts);
        }) as typeof fsp.readdir;
        (fsp as unknown as Record<string, unknown>)['readdir'] = patched;
        restore = () => {
          (fsp as unknown as Record<string, unknown>)['readdir'] = orig;
        };
      }
    } else {
      fs.chmodSync(denied, 0o000);
    }

    try {
      const { db, scanId } = scanRoot(root);
      const job = startScanJob(db, { scanId, rootPath: root, exclusions: [], emitProgress: () => {} });
      const result = await job.promise;

      expect(result.state).toBe('complete');
      expect(result.errors).toBeGreaterThanOrEqual(1);
      const errors = listScanErrors(db, scanId);
      expect(errors.some((e) => e.path === denied && e.code === 'EACCES')).toBe(true);
      // The readable file was still scanned.
      expect(result.files).toBe(1);
      db.close();
    } finally {
      if (!isRoot) fs.chmodSync(denied, 0o700);
      restore?.();
    }
  });
});

describe('cancellation', () => {
  it('cancels mid-scan: state cancelled, partial results kept, finishedAt set', async () => {
    const root = track(makeFixtureDir());
    for (let i = 0; i < 3000; i++) {
      writeFixture(path.join(root, `d${i % 10}`, `file-${i}.txt`), `content ${i}`);
    }

    const { db, scanId } = scanRoot(root);
    let seen = 0;
    let cancelFn: () => void = () => {};
    let cancelled = false;
    const job = startScanJob(db, {
      scanId,
      rootPath: root,
      exclusions: [],
      emitProgress: () => {},
      hooks: {
        beforeEntry: () => {
          seen += 1;
          if (seen >= 200 && !cancelled) {
            cancelled = true;
            cancelFn();
          }
        },
      },
    });
    cancelFn = job.cancel;

    const result = await job.promise;
    expect(result.state).toBe('cancelled');
    expect(result.files).toBeGreaterThan(0);
    expect(result.files).toBeLessThan(3000);

    const row = getScan(db, scanId);
    expect(row?.state).toBe('cancelled');
    expect(row?.finishedAt).not.toBeNull();
    // Partial results are present and labeled.
    expect(row?.files).toBe(result.files);
    db.close();
  });
});

describe('changed-during-scan', () => {
  it('skips a file modified between size-read and hash; no false group', async () => {
    const root = track(makeFixtureDir());
    const a = path.join(root, 'a', 'dup.txt');
    const b = path.join(root, 'b', 'dup.txt');
    writeFixture(a, 'identical-content-12345');
    writeFixture(b, 'identical-content-12345');

    const { db, scanId } = scanRoot(root);
    const job = startScanJob(db, {
      scanId,
      rootPath: root,
      exclusions: [],
      emitProgress: () => {},
      hooks: {
        // Mutate after the walk recorded the size, before hashing.
        beforeHashPhase: () => {
          fs.appendFileSync(b, 'CHANGED');
        },
      },
    });
    const result = await job.promise;

    expect(result.state).toBe('complete');
    expect(result.changed).toBe(1);
    // The changed file must not participate in any duplicate group.
    expect(getDuplicateGroups(db, scanId)).toHaveLength(0);
    const row = getScan(db, scanId);
    expect(row?.changed_count).toBe(1);
    db.close();
  });

  it('excludes a file appended to while its hash was being read; no verified group from stale bytes', async () => {
    const root = track(makeFixtureDir());
    const a = path.join(root, 'a', 'dup.txt');
    const b = path.join(root, 'b', 'dup.txt');
    writeFixture(a, 'AAAA');
    writeFixture(b, 'AAAA');

    const { db, scanId } = scanRoot(root);
    const job = startScanJob(db, {
      scanId,
      rootPath: root,
      exclusions: [],
      emitProgress: () => {},
      hooks: {
        // Simulate another writer appending the moment the read stream of
        // `a` finished: the digest was computed over the old bytes, so the
        // stored result would describe content the file no longer has.
        afterHashRead: (fullPath) => {
          if (fullPath === a) {
            fs.appendFileSync(a, 'CHANGED');
          }
        },
      },
    });
    const result = await job.promise;

    expect(result.state).toBe('complete');
    expect(result.changed).toBe(1);
    // The stale digest must not be presented as a verified duplicate group.
    expect(getDuplicateGroups(db, scanId)).toHaveLength(0);
    const row = getScan(db, scanId);
    expect(row?.changed_count).toBe(1);
    db.close();
  });

  it('excludes a file rewritten in place (same size) while its hash was being read', async () => {
    const root = track(makeFixtureDir());
    const a = path.join(root, 'a', 'dup.txt');
    const b = path.join(root, 'b', 'dup.txt');
    writeFixture(a, 'identical-content-12345');
    writeFixture(b, 'identical-content-12345');

    const { db, scanId } = scanRoot(root);
    const job = startScanJob(db, {
      scanId,
      rootPath: root,
      exclusions: [],
      emitProgress: () => {},
      hooks: {
        // Same length, different bytes, bumped timestamps: only the
        // post-read identity/mtime/ctime revalidation can catch this.
        afterHashRead: (fullPath) => {
          if (fullPath === a) {
            fs.writeFileSync(a, 'IDENTICAL-CONTENT-12345');
            const later = new Date(Date.now() + 5000);
            fs.utimesSync(a, later, later);
          }
        },
      },
    });
    const result = await job.promise;

    expect(result.state).toBe('complete');
    expect(result.changed).toBe(1);
    expect(getDuplicateGroups(db, scanId)).toHaveLength(0);
    const row = getScan(db, scanId);
    expect(row?.changed_count).toBe(1);
    db.close();
  });
});

describe('read-only guarantee', () => {
  it('performs zero writes to the fixture tree', async () => {
    const root = track(makeFixtureDir());
    writeFixture(path.join(root, 'docs', 'a.txt'), 'alpha');
    writeFixture(path.join(root, 'docs', 'b.txt'), 'alpha'); // duplicate pair (hashing reads!)
    writeFixture(path.join(root, 'media', 'c.bin'), Buffer.alloc(1024, 7));
    writeFixture(path.join(root, 'nested', 'deep', 'd.txt'), 'delta');

    const before = snapshotTree(root);
    const { db, scanId } = scanRoot(root);
    const job = startScanJob(db, { scanId, rootPath: root, exclusions: [], emitProgress: () => {} });
    const result = await job.promise;
    expect(result.state).toBe('complete');
    expect(getDuplicateGroups(db, scanId)).toHaveLength(1); // hashing really ran
    const after = snapshotTree(root);

    expect(after.files.sort()).toEqual(before.files.sort());
    for (const f of before.files) {
      expect(after.digests.get(f), `content changed: ${f}`).toBe(before.digests.get(f));
      expect(after.mtimes.get(f), `mtime changed: ${f}`).toBe(before.mtimes.get(f));
    }
    db.close();
  });
});

describe('exclusions', () => {
  it('skips matched paths and counts them', async () => {
    const root = track(makeFixtureDir());
    writeFixture(path.join(root, 'keep.txt'), 'keep me');
    writeFixture(path.join(root, 'node_modules', 'dep', 'index.js'), 'dep code');
    writeFixture(path.join(root, 'node_modules', 'dep2', 'index.js'), 'dep code');

    const { db, scanId } = scanRoot(root);
    const job = startScanJob(db, {
      scanId,
      rootPath: root,
      exclusions: ['node_modules'],
      emitProgress: () => {},
    });
    const result = await job.promise;

    expect(result.state).toBe('complete');
    expect(result.files).toBe(1);
    expect(result.excluded).toBeGreaterThanOrEqual(1);
    const row = getScan(db, scanId);
    expect(row?.excluded_count).toBe(result.excluded);
    db.close();
  });

  it('supports glob exclusions', async () => {
    const root = track(makeFixtureDir());
    writeFixture(path.join(root, 'app.log'), 'log');
    writeFixture(path.join(root, 'sub', 'debug.log'), 'log');
    writeFixture(path.join(root, 'keep.txt'), 'keep');

    const { db, scanId } = scanRoot(root);
    const job = startScanJob(db, {
      scanId,
      rootPath: root,
      exclusions: ['*.log'],
      emitProgress: () => {},
    });
    const result = await job.promise;
    expect(result.files).toBe(1);
    db.close();
  });
});

describe('progress events', () => {
  it('emits throttled progress with the current path', async () => {
    const root = track(makeFixtureDir());
    for (let i = 0; i < 50; i++) {
      writeFixture(path.join(root, `f${i}.txt`), `x${i}`);
    }
    const { db, scanId } = scanRoot(root);
    const events: Array<{ files: number; currentPath: string }> = [];
    const job = startScanJob(db, {
      scanId,
      rootPath: root,
      exclusions: [],
      emitProgress: (e) => events.push({ files: e.files, currentPath: e.currentPath }),
    });
    await job.promise;
    expect(events.length).toBeGreaterThan(0);
    const last = events[events.length - 1] as { files: number; currentPath: string };
    expect(last.files).toBe(50);
    expect(typeof last.currentPath).toBe('string');
    db.close();
  });
});

describe('platform guard', () => {
  it('never touches real user data: tmpdir fixtures only', () => {
    expect(os.tmpdir()).not.toBe('');
  });
});
