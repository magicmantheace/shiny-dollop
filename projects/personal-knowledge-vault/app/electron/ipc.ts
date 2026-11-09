/**
 * IPC handlers. Every payload is validated with zod before anything touches
 * the database. Responses use the uniform IpcResult envelope:
 * { ok: true, data } or { ok: false, error: { code, message } }.
 * The preload unwraps the envelope and throws Error on failure, so the
 * renderer sees exactly the typed `window.pkv` contract.
 *
 * The renderer is untrusted: it can only invoke these narrow channels, never
 * raw filesystem or SQL access.
 */
import { BrowserWindow, dialog, ipcMain } from 'electron';
import type { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { ZodError } from 'zod';
import { PkvChannels } from '../shared/types';
import { PkvError } from '../shared/errors';
import {
  approveNoteSchema,
  backupImportSchema,
  createNoteSchema,
  listNotesSchema,
  noteIdSchema,
  rejectNoteSchema,
  revisionsListSchema,
  searchNotesSchema,
  updateNoteSchema,
} from '../shared/schemas';
import type { IpcResult } from '../shared/types';
import { exportBackup, importBackup } from '../db/backup';
import { createNote, deleteNote, getNote, listNotes, listRevisions, searchNotes, updateNote } from '../db/notes';
import { approveNote, rejectNote } from '../db/review';

export interface HandlerDeps {
  db: DatabaseSync;
  getMainWindow: () => BrowserWindow | null;
}

type InvokeFn = (event: Electron.IpcMainInvokeEvent, payload: unknown) => Promise<unknown>;

function toErrorResult(err: unknown): IpcResult<never> {
  if (err instanceof ZodError) {
    const first = err.issues[0];
    const where = first?.path.length ? ` (${first.path.join('.')})` : '';
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: `Invalid request${where}: ${first?.message ?? 'validation failed'}.`,
      },
    };
  }
  if (err instanceof PkvError) {
    return { ok: false, error: { code: err.code, message: err.message } };
  }
  return {
    ok: false,
    error: {
      code: 'INTERNAL_ERROR',
      message: err instanceof Error ? err.message : 'Unexpected error.',
    },
  };
}

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

export function registerPkvIpc({ db, getMainWindow }: HandlerDeps): void {
  ipcMain.handle(
    PkvChannels.notesCreate,
    wrap((payload) => {
      const input = createNoteSchema.parse(payload);
      return createNote(db, {
        title: input.title,
        body: input.body,
        tags: input.tags,
        source: input.source ?? null,
        links: input.links,
      });
    }),
  );

  ipcMain.handle(
    PkvChannels.notesGet,
    wrap((payload) => getNote(db, noteIdSchema.parse(payload).id)),
  );

  ipcMain.handle(
    PkvChannels.notesList,
    wrap((payload) => {
      const filters = payload === undefined ? {} : listNotesSchema.parse(payload);
      return listNotes(db, filters);
    }),
  );

  ipcMain.handle(
    PkvChannels.notesUpdate,
    wrap((payload) => {
      const raw = payload as { id?: unknown } & Record<string, unknown>;
      const { id } = noteIdSchema.parse({ id: raw.id });
      const input = updateNoteSchema.parse(raw);
      return updateNote(db, id, {
        title: input.title,
        body: input.body,
        tags: input.tags,
        links: input.links,
        changeSummary: input.changeSummary,
      });
    }),
  );

  ipcMain.handle(
    PkvChannels.notesDelete,
    wrap((payload) => deleteNote(db, noteIdSchema.parse(payload).id)),
  );

  ipcMain.handle(
    PkvChannels.notesSearch,
    wrap((payload) => {
      const raw = payload as { query?: unknown } & Record<string, unknown>;
      const parsed = searchNotesSchema.parse(raw);
      return searchNotes(db, parsed.query, { status: parsed.status, tag: parsed.tag });
    }),
  );

  ipcMain.handle(
    PkvChannels.reviewApprove,
    wrap((payload) => approveNote(db, approveNoteSchema.parse(payload).id)),
  );

  ipcMain.handle(
    PkvChannels.reviewReject,
    wrap((payload) => {
      const parsed = rejectNoteSchema.parse(payload);
      return rejectNote(db, parsed.id, parsed.reason);
    }),
  );

  ipcMain.handle(
    PkvChannels.revisionsList,
    wrap((payload) => listRevisions(db, revisionsListSchema.parse(payload).noteId)),
  );

  ipcMain.handle(
    PkvChannels.backupExport,
    wrap(async () => {
      const payload = exportBackup(db);
      const win = getMainWindow();
      if (win) {
        const { canceled, filePath } = await dialog.showSaveDialog(win, {
          title: 'Export Knowledge Vault backup',
          defaultPath: `knowledge-vault-backup-${new Date().toISOString().slice(0, 10)}.json`,
          filters: [{ name: 'JSON', extensions: ['json'] }],
        });
        if (!canceled && filePath) {
          fs.writeFileSync(filePath, payload, 'utf8');
        }
      }
      return payload;
    }),
  );

  ipcMain.handle(
    PkvChannels.backupImport,
    wrap((payload) => importBackup(db, backupImportSchema.parse(payload).json)),
  );
}
