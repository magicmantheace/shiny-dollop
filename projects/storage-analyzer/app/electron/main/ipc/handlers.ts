/**
 * IPC handlers. Every payload is validated with zod before anything touches
 * the filesystem or database. Responses use the uniform IpcResult envelope:
 * { ok: true, data } or { ok: false, error: { code, message } }.
 *
 * The renderer is untrusted: it can only invoke these narrow channels, never
 * raw filesystem or SQL access. Scans run in the background (never awaited
 * by the invoke) and report through scan.progress / scan.finished events.
 */
import { BrowserWindow, dialog, ipcMain } from 'electron';
import type { DatabaseSync } from 'node:sqlite';
import fsp from 'node:fs/promises';
import path from 'node:path';
import { ZodError } from 'zod';
import { IpcChannels, StorageEvents } from '../../../shared/ipc-channels';
import {
  emptySchema,
  exportReportSchema,
  scanIdSchema,
  scanSearchSchema,
  scanStartSchema,
} from '../../../shared/schemas';
import type {
  DuplicateGroupsResult,
  ExportReportResult,
  IpcResult,
  ScanCancelResult,
  ScanFinishedEvent,
  ScanListResult,
  ScanProgressEvent,
  ScanStartResult,
  ScanStatus,
  SearchResults,
  ResultsSummary,
} from '../../../shared/types';
import { StorageError, StorageErrorCodes } from '../errors';
import {
  createScan,
  getScan,
  getDuplicateGroups,
  getSummary,
  listScans,
  searchFiles,
} from '../db/scans';
import {
  detectProtectedPath,
  startScanJob,
  type ScanProgressData,
} from '../scanner/engine';
import { writeReport } from '../export/report';

export interface HandlerDeps {
  db: DatabaseSync;
  getMainWindow: () => BrowserWindow | null;
}

/** scanId -> cancel function for every scan currently running. */
const activeScans = new Map<number, () => void>();

/** Promises of every scan job that has not settled yet. */
const activeScanJobs = new Set<Promise<unknown>>();

/**
 * Track a scan job's promise so shutdown can wait for it to settle.
 * Exported for tests; registerIpcHandlers calls this for every started scan.
 */
export function trackScanJob(promise: Promise<unknown>): void {
  activeScanJobs.add(promise);
  const done = (): void => {
    activeScanJobs.delete(promise);
  };
  void promise.then(done, done);
}

type InvokeFn = (event: Electron.IpcMainInvokeEvent, payload: unknown) => Promise<unknown>;

function wrap(fn: (payload: unknown) => Promise<unknown> | unknown): InvokeFn {
  return async (_event, payload) => {
    try {
      const data = await fn(payload);
      return { ok: true, data } satisfies IpcResult<unknown>;
    } catch (err) {
      return toErrorResult(err);
    }
  };
}

function toErrorResult(err: unknown): IpcResult<never> {
  if (err instanceof ZodError) {
    const first = err.issues[0];
    const where = first?.path.length ? ` (${first.path.join('.')})` : '';
    return {
      ok: false,
      error: { code: StorageErrorCodes.VALIDATION, message: `${first?.message ?? 'Invalid input'}${where}` },
    };
  }
  if (err instanceof StorageError) {
    return { ok: false, error: { code: err.code, message: err.message } };
  }
  const message = err instanceof Error ? err.message : String(err);
  return { ok: false, error: { code: StorageErrorCodes.INTERNAL_ERROR, message } };
}

function requireScan(db: DatabaseSync, scanId: number): void {
  if (!getScan(db, scanId)) {
    throw new StorageError(StorageErrorCodes.SCAN_NOT_FOUND, `No scan with id ${scanId}.`);
  }
}

export function registerIpcHandlers(deps: HandlerDeps): void {
  const { db, getMainWindow } = deps;

  const emitProgress = (scanId: number, data: ScanProgressData): void => {
    const event: ScanProgressEvent = { scanId, ...data };
    getMainWindow()?.webContents.send(StorageEvents.progress, event);
  };

  const emitFinished = (scanId: number, state: ScanFinishedEvent['state']): void => {
    const event: ScanFinishedEvent = { scanId, state };
    getMainWindow()?.webContents.send(StorageEvents.finished, event);
  };

  ipcMain.handle(
    IpcChannels.dialogChooseDirectory,
    wrap(async (payload) => {
      emptySchema.parse(payload ?? {});
      const win = getMainWindow();
      if (!win) throw new StorageError(StorageErrorCodes.INTERNAL_ERROR, 'No application window.');
      const result = await dialog.showOpenDialog(win, {
        title: 'Choose a folder to analyze',
        properties: ['openDirectory'],
      });
      if (result.canceled || result.filePaths.length === 0) {
        return { path: null };
      }
      return { path: result.filePaths[0] as string };
    }),
  );

  ipcMain.handle(
    IpcChannels.scanStart,
    wrap(async (payload): Promise<ScanStartResult> => {
      const input = scanStartSchema.parse(payload);
      const rootPath = input.rootPath.trim();
      if (!rootPath) {
        throw new StorageError(StorageErrorCodes.VALIDATION, 'Root path must not be empty.');
      }
      const resolved = path.resolve(rootPath);
      let stat: Awaited<ReturnType<typeof fsp.stat>>;
      try {
        stat = await fsp.stat(resolved);
      } catch {
        throw new StorageError(
          StorageErrorCodes.ROOT_INVALID,
          `Folder does not exist or cannot be read: ${resolved}`,
        );
      }
      if (!stat.isDirectory()) {
        throw new StorageError(
          StorageErrorCodes.ROOT_INVALID,
          `Not a folder: ${resolved}`,
        );
      }

      const warning = detectProtectedPath(resolved);
      const scanId = createScan(db, resolved);

      const job = startScanJob(db, {
        scanId,
        rootPath: resolved,
        exclusions: input.exclusions,
        emitProgress: (data) => emitProgress(scanId, data),
      });
      activeScans.set(scanId, job.cancel);
      trackScanJob(job.promise);
      void job.promise
        .then((result) => {
          activeScans.delete(scanId);
          emitFinished(scanId, result.state);
        })
        .catch((err: unknown) => {
          // runScanJob never rejects by contract; this is a last-resort guard.
          activeScans.delete(scanId);
          emitFinished(scanId, 'failed');
          void err;
        });

      return warning ? { scanId, warning } : { scanId };
    }),
  );

  ipcMain.handle(
    IpcChannels.scanCancel,
    wrap((payload): ScanCancelResult => {
      const { scanId } = scanIdSchema.parse(payload);
      requireScan(db, scanId);
      activeScans.get(scanId)?.();
      return { ok: true };
    }),
  );

  ipcMain.handle(
    IpcChannels.scanStatus,
    wrap((payload): ScanStatus => {
      const { scanId } = scanIdSchema.parse(payload);
      const scan = getScan(db, scanId);
      if (!scan) {
        throw new StorageError(StorageErrorCodes.SCAN_NOT_FOUND, `No scan with id ${scanId}.`);
      }
      return {
        state: scan.state,
        files: scan.files,
        dirs: scan.dirs,
        bytes: scan.bytes,
        ...(scan.error ? { error: scan.error } : {}),
        startedAt: scan.started_at,
        finishedAt: scan.finished_at,
        errors: scan.error_count,
        changedFiles: scan.changed_count,
      };
    }),
  );

  ipcMain.handle(
    IpcChannels.scanList,
    wrap((payload): ScanListResult => {
      emptySchema.parse(payload ?? {});
      return { scans: listScans(db) };
    }),
  );

  ipcMain.handle(
    IpcChannels.resultsSummary,
    wrap((payload): ResultsSummary => {
      const { scanId } = scanIdSchema.parse(payload);
      requireScan(db, scanId);
      return getSummary(db, scanId);
    }),
  );

  ipcMain.handle(
    IpcChannels.resultsDuplicates,
    wrap((payload): DuplicateGroupsResult => {
      const { scanId } = scanIdSchema.parse(payload);
      requireScan(db, scanId);
      return { groups: getDuplicateGroups(db, scanId) };
    }),
  );

  ipcMain.handle(
    IpcChannels.resultsSearch,
    wrap((payload): SearchResults => {
      const input = scanSearchSchema.parse(payload);
      requireScan(db, input.scanId);
      return { files: searchFiles(db, input.scanId, input.query) };
    }),
  );

  ipcMain.handle(
    IpcChannels.exportReport,
    wrap((payload): ExportReportResult => {
      const input = exportReportSchema.parse(payload);
      requireScan(db, input.scanId);
      const outPath = writeReport(db, input.scanId, input.format, input.outPath);
      return { outPath };
    }),
  );
}

/** For tests/host shutdown: cancel any running scans. */
export function abortAllScans(): void {
  for (const cancel of activeScans.values()) {
    try {
      cancel();
    } catch {
      // ignore
    }
  }
  activeScans.clear();
}

/**
 * Cancel all running scans AND wait until their jobs have settled — i.e.
 * until each job's asynchronous cleanup has persisted its terminal state to
 * the database. Shutdown must await this BEFORE closing the database:
 * abortAllScans() alone only signals cancellation, and closing the
 * connection while a job is still unwinding makes its cleanup fail with
 * "database is not open", leaving the scan marked 'running' forever.
 *
 * Bounded by `timeoutMs`: if a job somehow never settles, shutdown proceeds
 * anyway and the caller reconciles any leftover 'running' scans (see
 * markRunningScansInterrupted) rather than hanging the quit forever.
 */
export async function settleAllScans(timeoutMs = 10_000): Promise<void> {
  abortAllScans();
  if (activeScanJobs.size === 0) return;
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    await Promise.race([
      Promise.allSettled([...activeScanJobs]),
      new Promise<void>((resolve) => {
        timer = setTimeout(resolve, timeoutMs);
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}
