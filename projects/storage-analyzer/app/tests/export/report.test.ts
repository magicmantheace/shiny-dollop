/**
 * Export tests: CSV/JSON reports are valid and contain the expected rows;
 * invalid output paths are rejected before anything is written.
 */
import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { makeFixtureDir, makeTestDb, rmDir, writeFixture } from '../helpers';
import { createScan } from '../../electron/main/db/scans';
import { startScanJob } from '../../electron/main/scanner/engine';
import {
  buildReportPayload,
  renderReportCsv,
  renderReportJson,
  validateExportPath,
  writeReport,
} from '../../electron/main/export/report';
import { StorageError } from '../../electron/main/errors';

async function scannedDb(): Promise<{ db: ReturnType<typeof makeTestDb>; scanId: number; dir: string }> {
  const dir = makeFixtureDir('sa-export-');
  writeFixture(path.join(dir, 'a', 'dup.txt'), 'identical-content-12345');
  writeFixture(path.join(dir, 'b', 'dup.txt'), 'identical-content-12345');
  writeFixture(path.join(dir, 'c', 'note.md'), '# hello');
  const db = makeTestDb();
  const scanId = createScan(db, dir);
  const job = startScanJob(db, { scanId, rootPath: dir, exclusions: [], emitProgress: () => {} });
  const result = await job.promise;
  if (result.state !== 'complete') throw new Error(`scan did not complete: ${result.state}`);
  return { db, scanId, dir };
}

describe('validateExportPath', () => {
  it('accepts a writable file path and resolves it', () => {
    const dir = makeFixtureDir('sa-val-');
    try {
      const abs = validateExportPath(path.join(dir, 'report.json'));
      expect(path.isAbsolute(abs)).toBe(true);
      expect(abs.endsWith('report.json')).toBe(true);
    } finally {
      rmDir(dir);
    }
  });

  it('rejects a missing parent directory', () => {
    expect(() => validateExportPath(path.join(os.tmpdir(), 'sa-nope-missing-dir', 'r.json'))).toThrowError(
      StorageError,
    );
  });

  it('rejects a directory as the target', () => {
    const dir = makeFixtureDir('sa-valdir-');
    try {
      expect(() => validateExportPath(dir)).toThrowError(/directory, not a file/);
    } finally {
      rmDir(dir);
    }
  });

  it('rejects an empty path', () => {
    expect(() => validateExportPath('   ')).toThrowError(StorageError);
  });
});

describe('report payload', () => {
  it('contains meta, summary, duplicates and scan errors', async () => {
    const { db, scanId, dir } = await scannedDb();
    try {
      const payload = buildReportPayload(db, scanId);
      expect(payload.meta.scanId).toBe(scanId);
      expect(payload.meta.rootPath).toBe(dir);
      expect(payload.meta.state).toBe('complete');
      expect(payload.summary.totalFiles).toBe(3);
      expect(payload.duplicates.groups).toHaveLength(1);
      expect(payload.duplicates.groups[0]?.files).toHaveLength(2);
      expect(Array.isArray(payload.scanErrors)).toBe(true);
      expect(typeof payload.meta.generatedAt).toBe('string');
    } finally {
      db.close();
      rmDir(dir);
    }
  });

  it('throws SCAN_NOT_FOUND for unknown scans', () => {
    const db = makeTestDb();
    try {
      expect(() => buildReportPayload(db, 4242)).toThrowError(StorageError);
    } finally {
      db.close();
    }
  });
});

describe('JSON export', () => {
  it('writes a parseable file with expected rows', async () => {
    const { db, scanId, dir } = await scannedDb();
    const outDir = makeFixtureDir('sa-out-');
    try {
      const outPath = path.join(outDir, 'report.json');
      const written = writeReport(db, scanId, 'json', outPath);
      expect(written).toBe(path.resolve(outPath));
      const parsed = JSON.parse(fs.readFileSync(written, 'utf8')) as ReturnType<typeof buildReportPayload>;
      expect(parsed.meta.files).toBe(3);
      expect(parsed.summary.largestFiles[0]?.size).toBe('identical-content-12345'.length);
      expect(parsed.duplicates.groups).toHaveLength(1);
      expect(parsed.summary.typeSummary.find((t) => t.ext === '.txt')?.files).toBe(2);
    } finally {
      db.close();
      rmDir(dir);
      rmDir(outDir);
    }
  });
});

describe('CSV export', () => {
  it('writes all sections with expected rows', async () => {
    const { db, scanId, dir } = await scannedDb();
    const outDir = makeFixtureDir('sa-out-');
    try {
      const outPath = path.join(outDir, 'report.csv');
      writeReport(db, scanId, 'csv', outPath);
      const csv = fs.readFileSync(outPath, 'utf8');
      expect(csv).toContain('[summary]');
      expect(csv).toContain('[largest_files]');
      expect(csv).toContain('[dir_sizes]');
      expect(csv).toContain('[type_summary]');
      expect(csv).toContain('[duplicates]');
      expect(csv).toContain('[scan_errors]');
      expect(csv).toContain('total_files,3');
      expect(csv).toContain('dup.txt');
      // renderReportCsv is pure: spot-check quoting of a tricky path.
      const payload = buildReportPayload(db, scanId);
      const rendered = renderReportCsv(payload);
      expect(rendered).toContain('[duplicates]');
      const json = renderReportJson(payload);
      expect(() => JSON.parse(json)).not.toThrow();
    } finally {
      db.close();
      rmDir(dir);
      rmDir(outDir);
    }
  });

  it('quotes CSV cells containing commas or quotes', async () => {
    const { db, scanId, dir } = await scannedDb();
    try {
      const payload = buildReportPayload(db, scanId);
      payload.summary.largestFiles.unshift({ path: '/tmp/a,"b".txt', size: 1 });
      const csv = renderReportCsv(payload);
      expect(csv).toContain('"/tmp/a,""b"".txt",1');
    } finally {
      db.close();
      rmDir(dir);
    }
  });
});
