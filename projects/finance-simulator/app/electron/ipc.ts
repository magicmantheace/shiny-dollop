/**
 * IPC handlers. Every payload is validated with zod before anything touches
 * the database or the engine. Responses use the uniform IpcResult envelope:
 * { ok: true, data } or { ok: false, error: { code, message } }.
 * The preload unwraps the envelope and throws Error on failure, so the
 * renderer sees exactly the typed `window.sim` contract.
 *
 * The renderer is untrusted: it can only invoke these narrow channels, never
 * raw filesystem or SQL access.
 */
import { BrowserWindow, dialog, ipcMain, app } from 'electron';
import type { DatabaseSync } from 'node:sqlite';
import path from 'node:path';
import { ZodError } from 'zod';
import { SimChannels } from '../shared/ipc-channels';
import {
  debtUpsertSchema,
  emptySchema,
  idOnlySchema,
  incomeUpsertSchema,
  reportSaveSchema,
  simulateRunSchema,
} from '../shared/schemas';
import type { IpcResult } from '../shared/types';
import { simulateDebts } from '../engine/simulator';
import {
  deleteDebt,
  deleteIncomeSource,
  listDebts,
  listIncomeSources,
  upsertDebt,
  upsertIncomeSource,
} from '../db/records';
import { debtRecordToInput } from '../shared/types';
import { writeReportFile } from './report';

export interface HandlerDeps {
  db: DatabaseSync;
  getMainWindow: () => BrowserWindow | null;
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
      error: { code: 'VALIDATION', message: `${first?.message ?? 'Invalid input'}${where}` },
    };
  }
  const message = err instanceof Error ? err.message : String(err);
  return { ok: false, error: { code: 'INTERNAL_ERROR', message } };
}

export function registerIpcHandlers(deps: HandlerDeps): void {
  const { db, getMainWindow } = deps;

  ipcMain.handle(
    SimChannels.debtsList,
    wrap(() => {
      emptySchema.parse({});
      return listDebts(db);
    }),
  );

  ipcMain.handle(
    SimChannels.debtsUpsert,
    wrap((payload) => {
      const input = debtUpsertSchema.parse(payload);
      return upsertDebt(db, input);
    }),
  );

  ipcMain.handle(
    SimChannels.debtsDelete,
    wrap((payload) => {
      const { id } = idOnlySchema.parse(payload);
      return deleteDebt(db, id);
    }),
  );

  ipcMain.handle(
    SimChannels.incomeList,
    wrap(() => {
      emptySchema.parse({});
      return listIncomeSources(db);
    }),
  );

  ipcMain.handle(
    SimChannels.incomeUpsert,
    wrap((payload) => {
      const input = incomeUpsertSchema.parse(payload);
      return upsertIncomeSource(db, input);
    }),
  );

  ipcMain.handle(
    SimChannels.incomeDelete,
    wrap((payload) => {
      const { id } = idOnlySchema.parse(payload);
      return deleteIncomeSource(db, id);
    }),
  );

  ipcMain.handle(
    SimChannels.simulateRun,
    wrap((payload) => {
      const { extraPaymentCents } = simulateRunSchema.parse(payload);
      const inputs = listDebts(db).map(debtRecordToInput);
      return {
        avalanche: simulateDebts(inputs, extraPaymentCents, 'avalanche'),
        snowball: simulateDebts(inputs, extraPaymentCents, 'snowball'),
      };
    }),
  );

  ipcMain.handle(
    SimChannels.reportSave,
    wrap(async (payload) => {
      const input = reportSaveSchema.parse(payload);
      const win = getMainWindow();
      if (!win) throw new Error('No application window.');
      // Strip any path components the renderer may have smuggled in.
      const safeName = path.basename(input.defaultName);
      const ext = input.format === 'csv' ? '.csv' : '.json';
      const defaultPath = path.join(app.getPath('documents'), `${safeName}${ext}`);
      const result = await dialog.showSaveDialog(win, {
        title: 'Save scenario report',
        defaultPath,
        filters: [
          input.format === 'csv'
            ? { name: 'CSV', extensions: ['csv'] }
            : { name: 'JSON', extensions: ['json'] },
        ],
      });
      if (result.canceled || !result.filePath) {
        return { cancelled: true } as const;
      }
      const savedPath = await writeReportFile(db, input.format, input.extraPaymentCents, result.filePath);
      return { savedPath };
    }),
  );
}
