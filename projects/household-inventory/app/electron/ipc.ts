/**
 * Main-process IPC handlers for the household inventory app.
 * Every payload is parsed with the frozen zod schemas in shared/schemas.ts
 * before touching the database or the filesystem, and every handler returns
 * the IpcResult envelope ({ok:true,data} | {ok:false,error:{code,message}}).
 */
import { app, BrowserWindow, dialog, ipcMain } from 'electron';
import type { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { z } from 'zod';
import { InvChannels } from '../shared/ipc-channels';
import {
  attachmentInputSchema,
  itemFilterSchema,
  itemInputSchema,
  maintenanceInputSchema,
  uuidSchema,
  warrantyQuerySchema,
} from '../shared/schemas';
import type { IpcResult } from '../shared/types';
import {
  ATTACHMENTS_DIR_NAME,
  DB_FILE_NAME,
  closeDatabase,
  getAttachmentsDir,
  getDatabasePath,
  getUserDataDir,
  openDatabase,
} from '../db/store';
import * as records from '../db/records';
import {
  deleteAttachmentFile,
  readAttachmentFile,
  saveAttachmentFile,
} from '../db/attachmentFiles';
import { expiringWarranties, todayUtc } from '../engine/inventory';
import {
  createBackupArchive,
  extractBackupArchive,
  restoreBackupToDir,
  snapshotDatabaseToFile,
} from '../engine/backup';

export interface IpcContext {
  db: DatabaseSync;
  getMainWindow: () => BrowserWindow | null;
}

class IpcError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

function ok<T>(data: T): IpcResult<T> {
  return { ok: true, data };
}

function toFailure(err: unknown): IpcResult<never> {
  if (err instanceof IpcError) {
    return { ok: false, error: { code: err.code, message: err.message } };
  }
  const message = err instanceof Error ? err.message : String(err);
  return { ok: false, error: { code: 'internal', message } };
}

function zodIssuesMessage(err: z.ZodError): string {
  return err.issues
    .map((i) => `${i.path.length > 0 ? i.path.join('.') : 'input'}: ${i.message}`)
    .join('; ');
}

/** Parse with a zod schema; validation failures become IpcError('validation'). */
function parse<T extends z.ZodTypeAny>(schema: T, payload: unknown): z.infer<T> {
  try {
    return schema.parse(payload);
  } catch (err) {
    if (err instanceof z.ZodError) {
      throw new IpcError('validation', zodIssuesMessage(err));
    }
    throw err;
  }
}

const BASE64_RE = /^[A-Za-z0-9+/=\s]*$/;

function decodeBase64(dataBase64: string): Buffer {
  const compact = dataBase64.replace(/\s+/g, '');
  if (!BASE64_RE.test(dataBase64) || compact.length === 0) {
    throw new IpcError('validation', 'dataBase64: must be valid base64 file data');
  }
  return Buffer.from(compact, 'base64');
}

export function registerIpcHandlers(ctx: IpcContext): void {
  // Mutable reference: backup.import closes and reopens the database, so
  // every handler resolves the live connection through this closure.
  let db: DatabaseSync = ctx.db;
  const { getMainWindow } = ctx;

  const handle = (
    channel: string,
    fn: (payload: unknown) => Promise<IpcResult<unknown>> | IpcResult<unknown>,
  ): void => {
    ipcMain.handle(channel, async (_event, payload: unknown) => {
      try {
        return await fn(payload);
      } catch (err) {
        return toFailure(err);
      }
    });
  };

  const attachmentsDir = (): string => getAttachmentsDir();

  // ---- items ----

  handle(InvChannels.itemsList, (payload) => {
    const filter = parse(itemFilterSchema, payload ?? {});
    return ok(records.listItems(db, filter));
  });

  handle(InvChannels.itemsGet, (payload) => {
    const { id } = parse(z.object({ id: uuidSchema }), payload);
    return ok(records.getItemDetail(db, id));
  });

  handle(InvChannels.itemsCreate, (payload) => {
    const input = parse(itemInputSchema, payload);
    return ok(records.createItem(db, input));
  });

  handle(InvChannels.itemsUpdate, (payload) => {
    const { id, input } = parse(
      z.object({ id: uuidSchema, input: itemInputSchema }),
      payload,
    );
    const updated = records.updateItem(db, id, input);
    if (!updated) throw new IpcError('not_found', `Item not found: ${id}`);
    return ok(updated);
  });

  handle(InvChannels.itemsDelete, (payload) => {
    const { id } = parse(z.object({ id: uuidSchema }), payload);
    const item = records.getItem(db, id);
    if (!item) throw new IpcError('not_found', `Item not found: ${id}`);
    // Delete attachment files first; the FK cascade is the backup.
    const attachments = records.listAttachments(db, id);
    for (const a of attachments) {
      deleteAttachmentFile(attachmentsDir(), a.storedName);
    }
    records.deleteItem(db, id);
    return ok({ deletedAttachments: attachments.length });
  });

  handle(InvChannels.categoriesList, () => ok(records.listCategories(db)));

  // ---- attachments ----

  handle(InvChannels.attachmentsAdd, (payload) => {
    const { itemId, input } = parse(
      z.object({ itemId: uuidSchema, input: attachmentInputSchema }),
      payload,
    );
    const item = records.getItem(db, itemId);
    if (!item) throw new IpcError('not_found', `Item not found: ${itemId}`);
    const bytes = decodeBase64(input.dataBase64);
    let saved;
    try {
      saved = saveAttachmentFile(attachmentsDir(), {
        fileName: input.fileName,
        mime: input.mime,
        bytes,
        kind: input.kind,
      });
    } catch (err) {
      throw new IpcError('validation', err instanceof Error ? err.message : String(err));
    }
    const attachment = records.addAttachment(db, {
      itemId,
      originalName: saved.originalName,
      storedName: saved.storedName,
      mime: input.mime,
      sizeBytes: saved.sizeBytes,
      sha256: saved.sha256,
      kind: saved.kind,
    });
    return ok(attachment);
  });

  handle(InvChannels.attachmentsGet, (payload) => {
    const { id } = parse(z.object({ id: uuidSchema }), payload);
    const row = records.getAttachment(db, id);
    if (!row) return ok(null);
    // Row present but file missing on disk: integrity gap -> null, per contract.
    const bytes = readAttachmentFile(attachmentsDir(), row.storedName);
    if (!bytes) return ok(null);
    return ok({ name: row.originalName, mime: row.mime, dataBase64: bytes.toString('base64') });
  });

  handle(InvChannels.attachmentsDelete, (payload) => {
    const { id } = parse(z.object({ id: uuidSchema }), payload);
    const row = records.deleteAttachment(db, id);
    if (row) deleteAttachmentFile(attachmentsDir(), row.storedName);
    return ok(undefined);
  });

  // ---- maintenance ----

  handle(InvChannels.maintenanceList, (payload) => {
    const { itemId } = parse(z.object({ itemId: uuidSchema }), payload);
    return ok(records.listMaintenanceEvents(db, itemId));
  });

  handle(InvChannels.maintenanceAdd, (payload) => {
    const { itemId, input } = parse(
      z.object({ itemId: uuidSchema, input: maintenanceInputSchema }),
      payload,
    );
    const item = records.getItem(db, itemId);
    if (!item) throw new IpcError('not_found', `Item not found: ${itemId}`);
    return ok(records.addMaintenanceEvent(db, itemId, input));
  });

  handle(InvChannels.maintenanceDelete, (payload) => {
    const { id } = parse(z.object({ id: uuidSchema }), payload);
    records.deleteMaintenanceEvent(db, id);
    return ok(undefined);
  });

  // ---- warranties ----

  handle(InvChannels.warrantiesExpiring, (payload) => {
    const query = parse(warrantyQuerySchema, payload ?? {});
    const items = records.listItems(db);
    return ok(expiringWarranties(items, query.withinDays, todayUtc()));
  });

  // ---- backup ----

  handle(InvChannels.backupExport, async () => {
    const win = getMainWindow();
    const stamp = todayUtc().replaceAll('-', '');
    const saveOpts = {
      title: 'Export household inventory backup',
      defaultPath: `household-inventory-backup-${stamp}.zip`,
      filters: [{ name: 'Zip archives', extensions: ['zip'] }],
    };
    const chosen = win
      ? await dialog.showSaveDialog(win, saveOpts)
      : await dialog.showSaveDialog(saveOpts);
    if (chosen.canceled || !chosen.filePath) {
      throw new IpcError('cancelled', 'Backup export cancelled.');
    }
    const archive = createBackupArchive({
      db,
      attachmentsDir: attachmentsDir(),
      appVersion: app.getVersion(),
    });
    try {
      fs.writeFileSync(chosen.filePath, archive.data);
    } catch (err) {
      throw new IpcError('io', `Could not write backup file: ${(err as Error).message}`);
    }
    return ok({
      filePath: chosen.filePath,
      itemCount: archive.itemCount,
      attachmentCount: archive.attachmentCount,
    });
  });

  handle(InvChannels.backupImport, async () => {
    const win = getMainWindow();
    const openOpts = {
      title: 'Import household inventory backup',
      properties: ['openFile' as const],
      filters: [{ name: 'Zip archives', extensions: ['zip'] }],
    };
    const chosen = win
      ? await dialog.showOpenDialog(win, openOpts)
      : await dialog.showOpenDialog(openOpts);
    if (chosen.canceled || chosen.filePaths.length === 0) {
      throw new IpcError('cancelled', 'Backup import cancelled.');
    }
    const zipPath = chosen.filePaths[0];
    if (zipPath === undefined) {
      throw new IpcError('cancelled', 'Backup import cancelled.');
    }

    let zipBytes: Buffer;
    try {
      zipBytes = fs.readFileSync(zipPath);
    } catch (err) {
      throw new IpcError('io', `Could not read backup file: ${(err as Error).message}`);
    }
    let extracted;
    try {
      extracted = extractBackupArchive(zipBytes);
    } catch (err) {
      throw new IpcError('invalid_backup', err instanceof Error ? err.message : String(err));
    }

    const userDataDir = getUserDataDir();
    const dbPath = getDatabasePath(userDataDir);

    // Rollback first: consistent DB snapshot + attachment files.
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const rollbackDir = path.join(userDataDir, `rollback-${stamp}`);
    try {
      fs.mkdirSync(rollbackDir, { recursive: true });
      snapshotDatabaseToFile(db, path.join(rollbackDir, DB_FILE_NAME));
      fs.cpSync(attachmentsDir(), path.join(rollbackDir, ATTACHMENTS_DIR_NAME), {
        recursive: true,
      });
    } catch (err) {
      throw new IpcError('io', `Could not create rollback copy: ${(err as Error).message}`);
    }

    closeDatabase(db);
    try {
      const stageDir = fs.mkdtempSync(path.join(os.tmpdir(), 'hi-import-'));
      try {
        restoreBackupToDir(extracted, stageDir);
        for (const suffix of ['', '-wal', '-shm', '-journal']) {
          fs.rmSync(`${dbPath}${suffix}`, { force: true });
        }
        fs.renameSync(path.join(stageDir, DB_FILE_NAME), dbPath);
        fs.rmSync(attachmentsDir(), { recursive: true, force: true });
        fs.cpSync(path.join(stageDir, ATTACHMENTS_DIR_NAME), attachmentsDir(), {
          recursive: true,
        });
      } finally {
        fs.rmSync(stageDir, { recursive: true, force: true });
      }
      db = openDatabase(userDataDir);
      const itemCount = records.countItems(db);
      if (itemCount !== extracted.manifest.itemCount) {
        throw new IpcError(
          'internal',
          `Import verification failed: backup lists ${extracted.manifest.itemCount} items, database has ${itemCount}. Rollback copy is at ${rollbackDir}.`,
        );
      }
      return ok({
        filePath: zipPath,
        itemCount,
        attachmentCount: records.countAttachments(db),
      });
    } catch (err) {
      // Best effort: bring the previous database back online so the app is
      // not left without one. The original error is what gets reported.
      try {
        for (const suffix of ['', '-wal', '-shm', '-journal']) {
          fs.rmSync(`${dbPath}${suffix}`, { force: true });
        }
        fs.copyFileSync(path.join(rollbackDir, DB_FILE_NAME), dbPath);
        db = openDatabase(userDataDir);
      } catch {
        // Rollback itself failed; the manual copy at rollbackDir remains.
      }
      throw err;
    }
  });
}
