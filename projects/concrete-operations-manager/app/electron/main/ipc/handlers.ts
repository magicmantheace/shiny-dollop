/**
 * IPC handlers. Every payload is validated with zod before anything touches
 * the database or filesystem. Responses use the uniform IpcResult envelope:
 * { ok: true, data } or { ok: false, error: { code, message } }.
 *
 * The renderer is untrusted: it can only invoke these narrow channels, never
 * raw filesystem or SQL access.
 */
import { BrowserWindow, dialog, ipcMain } from 'electron';
import type { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';
import { z } from 'zod';
import { IpcChannels } from '../../../shared/ipc-channels';
import {
  auditListSchema,
  calibrationRemoveSchema,
  consumptionAddSchema,
  customerAddSchema,
  customerUpdateSchema,
  emptySchema,
  idParam,
  invoiceCreateSchema,
  jobAddSchema,
  jobIdParam,
  jobUpdateSchema,
  materialAddSchema,
  pourAddSchema,
  pourSetDeliveredSchema,
  pourUpdateSchema,
  quoteCreateSchema,
  quoteUpdateDraftSchema,
  receiptAddSchema,
  settingsSetSchema,
  taxRateAddSchema,
  taxRateUpdateSchema,
  intSettingSchema,
} from '../../../shared/schemas';
import type { IpcResult } from '../../../shared/types';
import { OpsError, OpsErrorCodes } from '../errors';
import {
  addCustomer,
  getCustomer,
  listCustomers,
  removeCustomer,
  updateCustomer,
} from '../db/customers';
import { addJob, getJob, listJobs, removeJob, updateJob } from '../db/jobs';
import {
  addPour,
  listPoursByJob,
  removePour,
  setDeliveredLiters,
  updatePour,
} from '../db/pours';
import {
  createInvoice,
  getInvoice,
  listInvoices,
  markInvoicePaid,
  voidInvoice,
} from '../db/invoices';
import {
  createQuote,
  deleteDraft,
  getQuote,
  issueQuote,
  listQuotesByJob,
  reviseQuote,
  updateDraft,
} from '../db/quotes';
import { getAllSettings, setSetting } from '../db/settings';
import { addTaxRate, listTaxRates, removeTaxRate, updateTaxRate } from '../db/taxrates';
import {
  addConsumption,
  addMaterial,
  addReceipt,
  getStock,
  listConsumption,
  listMaterials,
  listReceipts,
} from '../db/inventory';
import { listAudit } from '../db/audit';
import {
  getCalibrationProfile,
  importCalibrationProfile,
  listCalibrationProfiles,
  removeCalibrationProfile,
} from '../db/calibration';
import { customersCsv, inventoryCsv, invoicesCsv, jobsCsv } from '../export/csv';
import { renderInvoicePdf } from '../export/pdf';
import { backupDatabase, restoreDatabase } from '../backup';

export interface HandlerDeps {
  db: DatabaseSync;
  /** Absolute path of the live database file (needed for backup/restore). */
  dbPath: string;
  getMainWindow: () => BrowserWindow | null;
  /** Reopen the database after a restore. Returns the new connection. */
  reopenDatabase: () => DatabaseSync;
}

function ok<T>(data: T): IpcResult<T> {
  return { ok: true, data };
}

function fail(code: string, message: string): IpcResult<never> {
  return { ok: false, error: { code, message } };
}

function toErrorResult(err: unknown): IpcResult<never> {
  if (err instanceof OpsError) return fail(err.code, err.message);
  if (err instanceof z.ZodError) {
    return fail('INVALID_INPUT', err.issues.map((i) => `${i.path.join('.') || 'input'}: ${i.message}`).join('; '));
  }
  return fail('INTERNAL_ERROR', err instanceof Error ? err.message : String(err));
}

/** Guard a user-chosen path: must be absolute, inside an allowed root. */
function assertSafePath(p: string, allowedRoots: string[]): string {
  const resolved = path.resolve(p);
  const allowed = allowedRoots.some(
    (root) => resolved === path.resolve(root) || resolved.startsWith(path.resolve(root) + path.sep),
  );
  if (!allowed) {
    throw new OpsError(OpsErrorCodes.VALIDATION, 'Chosen path is outside the allowed folders.');
  }
  return resolved;
}

async function chooseSaveFile(
  win: BrowserWindow | null,
  title: string,
  defaultName: string,
  filters: { name: string; extensions: string[] }[],
): Promise<string | null> {
  const result = win
    ? await dialog.showSaveDialog(win, { title, defaultPath: defaultName, filters })
    : await dialog.showSaveDialog({ title, defaultPath: defaultName, filters });
  return result.canceled || !result.filePath ? null : result.filePath;
}

async function chooseOpenFile(
  win: BrowserWindow | null,
  title: string,
  filters: { name: string; extensions: string[] }[],
): Promise<string | null> {
  const result = win
    ? await dialog.showOpenDialog(win, { title, properties: ['openFile'], filters })
    : await dialog.showOpenDialog({ title, properties: ['openFile'], filters });
  return result.canceled ? null : (result.filePaths[0] ?? null);
}

const SETTING_VALIDATORS: Record<string, (v: string) => void> = {
  default_concrete_rate_cents_per_m3: (v) => intSettingSchema(0, 100_000_000).parse(v),
  default_small_load_charge_cents: (v) => intSettingSchema(0, 10_000_000).parse(v),
  small_load_threshold_liters: (v) => intSettingSchema(0, 1_000_000).parse(v),
  default_delivery_mode: (v) => {
    if (v !== 'flat' && v !== 'mileage') throw new Error('must be flat or mileage');
  },
  default_delivery_flat_cents: (v) => intSettingSchema(0, 10_000_000).parse(v),
  default_delivery_per_km_cents: (v) => intSettingSchema(0, 10_000_000).parse(v),
  company_name: (v) => {
    if (v.trim().length === 0) throw new Error('company name cannot be empty');
  },
  company_address: () => undefined,
};

export function registerIpcHandlers(deps: HandlerDeps): void {
  let { db } = deps;
  const { dbPath, getMainWindow } = deps;

  const handle = <T>(channel: string, fn: (payload: unknown) => Promise<T>): void => {
    ipcMain.handle(channel, async (_event, payload: unknown) => {
      try {
        return ok(await fn(payload));
      } catch (err) {
        return toErrorResult(err);
      }
    });
  };

  const notFound = (entity: string, id: number): OpsError =>
    new OpsError(OpsErrorCodes.NOT_FOUND, `${entity} #${id} does not exist.`);

  // ---- customers ----
  handle(IpcChannels.customersList, async (payload) => {
    emptySchema.parse(payload ?? {});
    return listCustomers(db);
  });
  handle(IpcChannels.customersGet, async (payload) => {
    const input = idParam.parse(payload);
    const c = getCustomer(db, input.id);
    if (!c) throw notFound('Customer', input.id);
    return c;
  });
  handle(IpcChannels.customersAdd, async (payload) => addCustomer(db, customerAddSchema.parse(payload)));
  handle(IpcChannels.customersUpdate, async (payload) => {
    const c = updateCustomer(db, customerUpdateSchema.parse(payload));
    if (!c) throw notFound('Customer', (payload as { id: number }).id);
    return c;
  });
  handle(IpcChannels.customersRemove, async (payload) => {
    const input = idParam.parse(payload);
    return { removed: removeCustomer(db, input.id) };
  });

  // ---- jobs ----
  handle(IpcChannels.jobsList, async (payload) => {
    const input = z.object({ customerId: z.number().int().positive().optional() }).parse(payload ?? {});
    return listJobs(db, input.customerId);
  });
  handle(IpcChannels.jobsGet, async (payload) => {
    const input = idParam.parse(payload);
    const j = getJob(db, input.id);
    if (!j) throw notFound('Job', input.id);
    return j;
  });
  handle(IpcChannels.jobsAdd, async (payload) => addJob(db, jobAddSchema.parse(payload)));
  handle(IpcChannels.jobsUpdate, async (payload) => {
    const j = updateJob(db, jobUpdateSchema.parse(payload));
    if (!j) throw notFound('Job', (payload as { id: number }).id);
    return j;
  });
  handle(IpcChannels.jobsRemove, async (payload) => {
    const input = idParam.parse(payload);
    return { removed: removeJob(db, input.id) };
  });

  // ---- pours ----
  handle(IpcChannels.poursListByJob, async (payload) => listPoursByJob(db, jobIdParam.parse(payload).jobId));
  handle(IpcChannels.poursAdd, async (payload) => addPour(db, pourAddSchema.parse(payload)));
  handle(IpcChannels.poursUpdate, async (payload) => {
    const input = pourUpdateSchema.parse(payload);
    const patch: { mixDesignId?: string; quotedLiters?: number } = {};
    if (input.mixDesignId !== undefined) patch.mixDesignId = input.mixDesignId;
    if (input.quotedLiters !== undefined) patch.quotedLiters = input.quotedLiters;
    const p = updatePour(db, input.id, patch);
    if (!p) throw notFound('Pour', input.id);
    return p;
  });
  handle(IpcChannels.poursSetDelivered, async (payload) => {
    const input = pourSetDeliveredSchema.parse(payload);
    const p = setDeliveredLiters(db, input.id, input.deliveredLiters);
    if (!p) throw notFound('Pour', input.id);
    return p;
  });
  handle(IpcChannels.poursRemove, async (payload) => {
    const input = idParam.parse(payload);
    return { removed: removePour(db, input.id) };
  });

  // ---- quotes ----
  handle(IpcChannels.quotesListByJob, async (payload) => listQuotesByJob(db, jobIdParam.parse(payload).jobId));
  handle(IpcChannels.quotesGet, async (payload) => {
    const input = idParam.parse(payload);
    const q = getQuote(db, input.id);
    if (!q) throw notFound('Quote', input.id);
    return q;
  });
  handle(IpcChannels.quotesCreate, async (payload) => {
    const input = quoteCreateSchema.parse(payload);
    return createQuote(db, input.jobId, input.notes ?? null);
  });
  handle(IpcChannels.quotesUpdateDraft, async (payload) => {
    const input = quoteUpdateDraftSchema.parse(payload);
    return updateDraft(db, input.id, {
      notes: input.notes,
      rateOverrideCentsPerM3: input.rateOverrideCentsPerM3 ?? null,
      smallLoadChargeOverrideCents: input.smallLoadChargeOverrideCents ?? null,
    });
  });
  handle(IpcChannels.quotesIssue, async (payload) => issueQuote(db, idParam.parse(payload).id));
  handle(IpcChannels.quotesRevise, async (payload) => reviseQuote(db, idParam.parse(payload).id));
  handle(IpcChannels.quotesDeleteDraft, async (payload) => {
    const input = idParam.parse(payload);
    return { removed: deleteDraft(db, input.id) };
  });

  // ---- invoices ----
  handle(IpcChannels.invoicesList, async (payload) => {
    emptySchema.parse(payload ?? {});
    return listInvoices(db);
  });
  handle(IpcChannels.invoicesGet, async (payload) => {
    const input = idParam.parse(payload);
    const inv = getInvoice(db, input.id);
    if (!inv) throw notFound('Invoice', input.id);
    return inv;
  });
  handle(IpcChannels.invoicesCreate, async (payload) => createInvoice(db, invoiceCreateSchema.parse(payload).quoteId));
  handle(IpcChannels.invoicesMarkPaid, async (payload) => markInvoicePaid(db, idParam.parse(payload).id));
  handle(IpcChannels.invoicesVoid, async (payload) => voidInvoice(db, idParam.parse(payload).id));

  // ---- settings & tax rates ----
  handle(IpcChannels.settingsGet, async (payload) => {
    emptySchema.parse(payload ?? {});
    return getAllSettings(db);
  });
  handle(IpcChannels.settingsSet, async (payload) => {
    const input = settingsSetSchema.parse(payload);
    const validate = SETTING_VALIDATORS[input.key];
    if (!validate) throw new OpsError(OpsErrorCodes.VALIDATION, `Unknown setting ${input.key}.`);
    try {
      validate(input.value);
    } catch (err) {
      throw new OpsError(OpsErrorCodes.VALIDATION, `Invalid value for ${input.key}: ${err instanceof Error ? err.message : String(err)}`);
    }
    setSetting(db, input.key, input.value);
    return getAllSettings(db);
  });
  handle(IpcChannels.taxRatesList, async (payload) => {
    emptySchema.parse(payload ?? {});
    return listTaxRates(db);
  });
  handle(IpcChannels.taxRatesAdd, async (payload) => {
    const input = taxRateAddSchema.parse(payload);
    return addTaxRate(db, input.name, input.rateBps, input.enabled);
  });
  handle(IpcChannels.taxRatesUpdate, async (payload) => {
    const input = taxRateUpdateSchema.parse(payload);
    const patch: { name?: string; rateBps?: number; enabled?: boolean } = {};
    if (input.name !== undefined) patch.name = input.name;
    if (input.rateBps !== undefined) patch.rateBps = input.rateBps;
    if (input.enabled !== undefined) patch.enabled = input.enabled;
    const t = updateTaxRate(db, input.id, patch);
    if (!t) throw notFound('Tax rate', input.id);
    return t;
  });
  handle(IpcChannels.taxRatesRemove, async (payload) => {
    const input = idParam.parse(payload);
    return { removed: removeTaxRate(db, input.id) };
  });

  // ---- inventory ----
  handle(IpcChannels.inventoryMaterials, async (payload) => {
    emptySchema.parse(payload ?? {});
    return listMaterials(db);
  });
  handle(IpcChannels.inventoryMaterialAdd, async (payload) => {
    const input = materialAddSchema.parse(payload);
    try {
      return addMaterial(db, input.name, input.unit);
    } catch (err) {
      if (err instanceof Error && err.message.includes('UNIQUE')) {
        throw new OpsError(OpsErrorCodes.VALIDATION, `Material "${input.name}" already exists.`);
      }
      throw err;
    }
  });
  handle(IpcChannels.inventoryReceipts, async (payload) => {
    const input = z.object({ materialId: z.number().int().positive().optional() }).parse(payload ?? {});
    return listReceipts(db, input.materialId);
  });
  handle(IpcChannels.inventoryReceiptAdd, async (payload) => {
    const input = receiptAddSchema.parse(payload);
    return addReceipt(db, { ...input, notes: input.notes ?? null });
  });
  handle(IpcChannels.inventoryConsumption, async (payload) => {
    const input = z.object({ pourId: z.number().int().positive().optional() }).parse(payload ?? {});
    return listConsumption(db, input.pourId);
  });
  handle(IpcChannels.inventoryConsumptionAdd, async (payload) =>
    addConsumption(db, consumptionAddSchema.parse(payload)),
  );
  handle(IpcChannels.inventoryStock, async (payload) => {
    emptySchema.parse(payload ?? {});
    return getStock(db);
  });

  // ---- audit ----
  handle(IpcChannels.auditList, async (payload) => listAudit(db, auditListSchema.parse(payload ?? {})));

  // ---- exports ----
  handle(IpcChannels.exportsCsv, async (payload) => {
    emptySchema.parse(payload ?? {});
    const win = getMainWindow();
    const dirResult = win
      ? await dialog.showOpenDialog(win, { title: 'Choose a folder for the CSV exports', properties: ['openDirectory', 'createDirectory'] })
      : await dialog.showOpenDialog({ title: 'Choose a folder for the CSV exports', properties: ['openDirectory', 'createDirectory'] });
    if (dirResult.canceled || dirResult.filePaths.length === 0) return { written: [] as string[] };
    const dir = dirResult.filePaths[0] as string;
    const written: string[] = [];
    const files: [string, string][] = [
      ['customers.csv', customersCsv(db)],
      ['jobs.csv', jobsCsv(db)],
      ['invoices.csv', invoicesCsv(db)],
      ['inventory.csv', inventoryCsv(db)],
    ];
    for (const [name, content] of files) {
      const target = assertSafePath(path.join(dir, name), [dir]);
      fs.writeFileSync(target, content, 'utf8');
      written.push(target);
    }
    return { written };
  });

  handle(IpcChannels.invoicePdf, async (payload) => {
    const input = idParam.parse(payload);
    const inv = getInvoice(db, input.id);
    if (!inv) throw notFound('Invoice', input.id);
    const { buffer, fileName } = await renderInvoicePdf(db, input.id);
    const target = await chooseSaveFile(getMainWindow(), 'Save invoice PDF', fileName, [
      { name: 'PDF', extensions: ['pdf'] },
    ]);
    if (!target) return { written: null as string | null };
    const safe = assertSafePath(target, [path.dirname(target)]);
    try {
      fs.writeFileSync(safe, buffer);
    } catch (err) {
      throw new OpsError(OpsErrorCodes.IO_ERROR, `Could not write PDF: ${err instanceof Error ? err.message : String(err)}`);
    }
    return { written: safe };
  });

  // ---- backup / restore ----
  handle(IpcChannels.backupCreate, async (payload) => {
    emptySchema.parse(payload ?? {});
    const stamp = new Date().toISOString().slice(0, 10);
    const target = await chooseSaveFile(getMainWindow(), 'Save database backup', `concrete-ops-backup-${stamp}.db`, [
      { name: 'SQLite database', extensions: ['db'] },
    ]);
    if (!target) return { written: null as string | null };
    if (dbPath === ':memory:') {
      throw new OpsError(OpsErrorCodes.INVALID_STATE, 'Cannot back up an in-memory database.');
    }
    const safe = assertSafePath(target, [path.dirname(target)]);
    return { written: backupDatabase(db, dbPath, safe) };
  });

  handle(IpcChannels.backupRestore, async (payload) => {
    emptySchema.parse(payload ?? {});
    const candidate = await chooseOpenFile(getMainWindow(), 'Choose a database backup to restore', [
      { name: 'SQLite database', extensions: ['db', 'sqlite', 'sqlite3'] },
    ]);
    if (!candidate) return { restored: false, rollbackPath: null as string | null };
    if (dbPath === ':memory:') {
      throw new OpsError(OpsErrorCodes.INVALID_STATE, 'Cannot restore into an in-memory database.');
    }
    const rollbackDir = path.join(path.dirname(dbPath), 'rollbacks');
    // Close the live connection before replacing the file, then reopen.
    try {
      db.close();
    } catch {
      // ignore
    }
    try {
      const { rollbackPath } = restoreDatabase(dbPath, candidate, rollbackDir);
      db = deps.reopenDatabase();
      return { restored: true, rollbackPath };
    } catch (err) {
      // Best effort: reopen the original database so the app keeps working.
      try {
        db = deps.reopenDatabase();
      } catch {
        // ignore
      }
      throw err;
    }
  });

  // ---- calibration exchange (interop with the Mix Calculator) ----
  handle(IpcChannels.calibrationList, async (payload) => {
    emptySchema.parse(payload ?? {});
    return listCalibrationProfiles(db).map((p) => ({
      id: p.id,
      name: p.name,
      formatVersion: p.formatVersion,
      importedAt: p.importedAt,
    }));
  });
  handle(IpcChannels.calibrationExport, async (payload) => {
    const input = idParam.parse(payload);
    const profile = getCalibrationProfile(db, input.id);
    if (!profile) throw notFound('Calibration profile', input.id);
    const target = await chooseSaveFile(getMainWindow(), 'Export calibration profile', `${profile.name.replace(/[^a-z0-9-_]+/gi, '_')}.calibration.json`, [
      { name: 'JSON', extensions: ['json'] },
    ]);
    if (!target) return { written: null as string | null };
    const safe = assertSafePath(target, [path.dirname(target)]);
    fs.writeFileSync(safe, profile.payloadJson, 'utf8');
    return { written: safe };
  });
  handle(IpcChannels.calibrationImport, async (payload) => {
    emptySchema.parse(payload ?? {});
    const candidate = await chooseOpenFile(getMainWindow(), 'Import calibration profile', [
      { name: 'JSON', extensions: ['json'] },
    ]);
    if (!candidate) return { imported: null };
    let text: string;
    try {
      text = fs.readFileSync(candidate, 'utf8');
    } catch (err) {
      throw new OpsError(OpsErrorCodes.IO_ERROR, `Could not read file: ${err instanceof Error ? err.message : String(err)}`);
    }
    if (text.length > 5 * 1024 * 1024) {
      throw new OpsError(OpsErrorCodes.VALIDATION, 'Calibration file is too large (>5 MB).');
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      throw new OpsError(OpsErrorCodes.VALIDATION, 'File is not valid JSON.');
    }
    const profile = importCalibrationProfile(db, parsed);
    return {
      imported: { id: profile.id, name: profile.name, formatVersion: profile.formatVersion },
    };
  });
  handle(IpcChannels.calibrationRemove, async (payload) => {
    const input = calibrationRemoveSchema.parse(payload);
    return { removed: removeCalibrationProfile(db, input.id) };
  });
}
