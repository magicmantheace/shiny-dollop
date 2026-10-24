/**
 * CSV/JSON report export. Writes the scan's summary (ranked files, folder
 * sizes, type breakdown) plus the hash-confirmed duplicate groups and the
 * recorded scan errors. The output path is validated before anything is
 * written; the export never touches the scanned tree.
 */
import type { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';
import { StorageError } from '../errors';
import {
  getDuplicateGroups,
  getScan,
  getSummary,
  listScanErrors,
} from '../db/scans';
import type {
  DuplicateGroup,
  ResultsSummary,
  ScanState,
} from '../../../shared/types';

export interface ReportMeta {
  scanId: number;
  rootPath: string;
  state: ScanState;
  files: number;
  dirs: number;
  bytes: number;
  excluded: number;
  symlinks: number;
  changedFiles: number;
  errors: number;
  startedAt: string;
  finishedAt: string | null;
  generatedAt: string;
  appVersion: string;
}

export interface ReportPayload {
  meta: ReportMeta;
  summary: ResultsSummary;
  duplicates: { groups: DuplicateGroup[] };
  scanErrors: Array<{ path: string; code: string }>;
}

const APP_VERSION = '0.1.0';

/**
 * Validate that outPath is a writable file path. Throws StorageError with
 * code EXPORT_FAILED when it is not. Does not create the file.
 */
export function validateExportPath(outPath: string): string {
  const trimmed = outPath.trim();
  if (!trimmed) {
    throw new StorageError('EXPORT_FAILED', 'Output path must not be empty.');
  }
  const abs = path.resolve(trimmed);
  const dir = path.dirname(abs);

  let dirStat: fs.Stats;
  try {
    dirStat = fs.statSync(dir);
  } catch (err) {
    if ((err as NodeJS.ErrnoException)?.code === 'ENOENT') {
      throw new StorageError('EXPORT_FAILED', `Output directory does not exist: ${dir}`);
    }
    throw new StorageError('EXPORT_FAILED', `Cannot access output directory: ${dir}`);
  }
  if (!dirStat.isDirectory()) {
    throw new StorageError('EXPORT_FAILED', `Output parent is not a directory: ${dir}`);
  }
  try {
    fs.accessSync(dir, fs.constants.W_OK);
  } catch {
    throw new StorageError('EXPORT_FAILED', `Output directory is not writable: ${dir}`);
  }

  let targetStat: fs.Stats | null = null;
  try {
    targetStat = fs.statSync(abs);
  } catch (err) {
    if ((err as NodeJS.ErrnoException)?.code !== 'ENOENT') {
      throw new StorageError('EXPORT_FAILED', `Cannot access output path: ${abs}`);
    }
  }
  if (targetStat?.isDirectory()) {
    throw new StorageError('EXPORT_FAILED', `Output path is a directory, not a file: ${abs}`);
  }
  return abs;
}

export function buildReportPayload(db: DatabaseSync, scanId: number): ReportPayload {
  const scan = getScan(db, scanId);
  if (!scan) {
    throw new StorageError('SCAN_NOT_FOUND', `No scan with id ${scanId}.`);
  }
  return {
    meta: {
      scanId: scan.id,
      rootPath: scan.root_path,
      state: scan.state,
      files: scan.files,
      dirs: scan.dirs,
      bytes: scan.bytes,
      excluded: scan.excluded_count,
      symlinks: scan.symlink_count,
      changedFiles: scan.changed_count,
      errors: scan.error_count,
      startedAt: scan.started_at,
      finishedAt: scan.finished_at,
      generatedAt: new Date().toISOString(),
      appVersion: APP_VERSION,
    },
    summary: getSummary(db, scanId),
    duplicates: { groups: getDuplicateGroups(db, scanId) },
    scanErrors: listScanErrors(db, scanId),
  };
}

function csvCell(value: string | number): string {
  const s = String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function csvSection(header: string[], rows: Array<Array<string | number>>): string {
  const lines = [header.map(csvCell).join(',')];
  for (const row of rows) lines.push(row.map(csvCell).join(','));
  return lines.join('\n');
}

/** CSV with one section per result area; simple enough for Excel/Sheets. */
export function renderReportCsv(payload: ReportPayload): string {
  const { meta, summary, duplicates, scanErrors } = payload;
  const parts: string[] = [];

  parts.push('# Storage Analyzer report');
  parts.push(`# generated_at,${meta.generatedAt}`);
  parts.push(`# scan_id,${meta.scanId}`);
  parts.push(`# root_path,${meta.rootPath}`);
  parts.push(`# state,${meta.state}`);
  parts.push('');

  parts.push('[summary]');
  parts.push(
    csvSection(
      ['metric', 'value'],
      [
        ['total_files', meta.files],
        ['total_bytes', meta.bytes],
        ['directories', meta.dirs],
        ['excluded', meta.excluded],
        ['symlinks_skipped', meta.symlinks],
        ['changed_during_scan', meta.changedFiles],
        ['errors', meta.errors],
      ],
    ),
  );
  parts.push('');

  parts.push('[largest_files]');
  parts.push(
    csvSection(
      ['path', 'size_bytes'],
      summary.largestFiles.map((f) => [f.path, f.size]),
    ),
  );
  parts.push('');

  parts.push('[dir_sizes]');
  parts.push(
    csvSection(
      ['path', 'bytes', 'files'],
      summary.dirSizes.map((d) => [d.path, d.bytes, d.files]),
    ),
  );
  parts.push('');

  parts.push('[type_summary]');
  parts.push(
    csvSection(
      ['ext', 'files', 'bytes'],
      summary.typeSummary.map((t) => [t.ext === '' ? '(none)' : t.ext, t.files, t.bytes]),
    ),
  );
  parts.push('');

  parts.push('[duplicates]');
  parts.push(
    csvSection(
      ['sha256', 'size_bytes', 'file_count', 'paths'],
      duplicates.groups.map((g) => [g.sha256, g.sizeBytes, g.files.length, g.files.join('|')]),
    ),
  );
  parts.push('');

  parts.push('[scan_errors]');
  parts.push(csvSection(['path', 'code'], scanErrors.map((e) => [e.path, e.code])));
  parts.push('');

  return parts.join('\n');
}

export function renderReportJson(payload: ReportPayload): string {
  return JSON.stringify(payload, null, 2);
}

/**
 * Validate the output path, build the report, write it, return the
 * absolute path written.
 */
export function writeReport(
  db: DatabaseSync,
  scanId: number,
  format: 'csv' | 'json',
  outPath: string,
): string {
  const abs = validateExportPath(outPath);
  const payload = buildReportPayload(db, scanId);
  const content = format === 'csv' ? renderReportCsv(payload) : renderReportJson(payload);
  try {
    fs.writeFileSync(abs, content, 'utf8');
  } catch (err) {
    throw new StorageError(
      'EXPORT_FAILED',
      `Could not write report to ${abs}: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
  return abs;
}
