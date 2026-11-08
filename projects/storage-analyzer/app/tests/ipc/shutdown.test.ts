/**
 * Shutdown-during-scan regression tests.
 *
 * Quitting mid-scan used to close the database immediately after signalling
 * cancellation: the job's asynchronous cleanup then failed with
 * "database is not open" and the scan stayed 'running' forever. Shutdown
 * must wait for jobs to settle (settleAllScans) before closing, and any
 * scan still left 'running' is reconciled on the next startup
 * (markRunningScansInterrupted).
 */
import { afterEach, describe, expect, it } from 'vitest';
import { DatabaseSync } from 'node:sqlite';
import path from 'node:path';
import { makeFixtureDir, rmDir, writeFixture } from '../helpers';
import { runMigrations } from '../../electron/main/db/migrations';
import {
  createScan,
  getScan,
  markRunningScansInterrupted,
} from '../../electron/main/db/scans';
import { startScanJob } from '../../electron/main/scanner/engine';
import { settleAllScans, trackScanJob } from '../../electron/main/ipc/handlers';

const dirs: string[] = [];
afterEach(() => {
  while (dirs.length > 0) rmDir(dirs.pop() as string);
});

function openFileDb(dir: string): DatabaseSync {
  const db = new DatabaseSync(path.join(dir, 'test.db'));
  runMigrations(db);
  return db;
}

describe('shutdown during a scan', () => {
  it('settles the cancelled job and persists its terminal state before the database closes', async () => {
    const dir = makeFixtureDir();
    dirs.push(dir);
    const root = path.join(dir, 'tree');
    writeFixture(path.join(root, 'a', 'dup.txt'), 'identical-content-12345');
    writeFixture(path.join(root, 'b', 'dup.txt'), 'identical-content-12345');

    const db = openFileDb(dir);
    const scanId = createScan(db, root);

    // Park the job in the hash phase so it is genuinely mid-scan when the
    // "quit" begins.
    let releaseHashPhase: () => void = () => {};
    let hashPhaseReached: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      releaseHashPhase = resolve;
    });
    const reached = new Promise<void>((resolve) => {
      hashPhaseReached = resolve;
    });
    const job = startScanJob(db, {
      scanId,
      rootPath: root,
      exclusions: [],
      emitProgress: () => {},
      hooks: {
        beforeHashPhase: async () => {
          hashPhaseReached();
          await gate;
        },
      },
    });
    trackScanJob(job.promise);
    await reached;
    expect(getScan(db, scanId)?.state).toBe('running');

    // Quit sequence: signal cancellation, then wait for jobs to settle
    // BEFORE closing the database (this is what index.ts now does).
    job.cancel();
    const settling = settleAllScans();
    releaseHashPhase();
    await settling;

    const result = await job.promise;
    expect(result.state).toBe('cancelled');
    // Terminal state was committed while the database was still open.
    expect(getScan(db, scanId)?.state).toBe('cancelled');
    db.close();

    // Reopening (next launch) must not find a scan stuck at 'running'.
    const reopened = openFileDb(dir);
    expect(getScan(reopened, scanId)?.state).toBe('cancelled');
    expect(markRunningScansInterrupted(reopened)).toBe(0);
    reopened.close();
  });

  it('reconciles a scan whose process died before cleanup could persist', async () => {
    const dir = makeFixtureDir();
    dirs.push(dir);

    // Simulate the old failure: a scan row created 'running', then the
    // process vanishes without ever persisting a terminal state.
    const db = openFileDb(dir);
    const scanId = createScan(db, path.join(dir, 'tree'));
    expect(getScan(db, scanId)?.state).toBe('running');
    db.close();

    // Next startup reconciliation closes it out instead of showing it
    // as running forever.
    const reopened = openFileDb(dir);
    expect(markRunningScansInterrupted(reopened)).toBe(1);
    const row = getScan(reopened, scanId);
    expect(row?.state).toBe('failed');
    expect(row?.error).toMatch(/Interrupted/);
    expect(row?.finished_at).not.toBeNull();
    reopened.close();
  });

  it('settleAllScans resolves promptly when nothing is running', async () => {
    await expect(settleAllScans(1000)).resolves.toBeUndefined();
  });
});
