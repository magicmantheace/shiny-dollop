/**
 * IPC handlers for every `dtf:` channel. Each handler validates its
 * payload with zod, then delegates to the store / export pipeline.
 * DtfError codes are preserved so the renderer can react to them.
 */
import { BrowserWindow, dialog, ipcMain } from 'electron';
import type { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs/promises';
import { IpcChannels } from '../../../shared/ipc-channels';
import {
  documentsCreateSchema,
  documentsDeleteSchema,
  documentsGetSchema,
  documentsUpdateFieldSchema,
  documentsUpdateTokensSchema,
  exportGenerateSchema,
  exportSaveSchema,
  templatesGetSchema,
  templatesImportSchema,
} from '../../../shared/schemas';
import { generateExport } from '../export';
import {
  createDocument,
  deleteDocument,
  getDocument,
  getTemplate,
  importTemplate,
  listDocuments,
  listTemplates,
  updateDocumentField,
  updateDocumentTokens,
} from '../store';

export interface HandlerDeps {
  db: DatabaseSync;
  getMainWindow: () => BrowserWindow | null;
}

function handle<T>(
  channel: string,
  fn: (payload: unknown) => Promise<T> | T,
): void {
  ipcMain.handle(channel, async (_event, payload) => {
    try {
      return await fn(payload);
    } catch (err) {
      // Preserve DtfError codes/messages for the renderer.
      if (err instanceof Error) throw err;
      throw new Error('Unknown IPC failure');
    }
  });
}

export function registerIpcHandlers(deps: HandlerDeps): void {
  const { db, getMainWindow } = deps;

  handle(IpcChannels.templatesList, () => listTemplates(db));

  handle(IpcChannels.templatesGet, (payload) => {
    const { templateId } = templatesGetSchema.parse(payload);
    return getTemplate(db, templateId).manifest;
  });

  handle(IpcChannels.templatesImport, (payload) => {
    const { bundleJson } = templatesImportSchema.parse(payload);
    return importTemplate(db, bundleJson);
  });

  handle(IpcChannels.documentsList, () => listDocuments(db));

  handle(IpcChannels.documentsCreate, (payload) => {
    const { templateId } = documentsCreateSchema.parse(payload);
    return createDocument(db, templateId);
  });

  handle(IpcChannels.documentsGet, (payload) => {
    const { id } = documentsGetSchema.parse(payload);
    return getDocument(db, id);
  });

  handle(IpcChannels.documentsUpdateField, (payload) => {
    const { id, key, value } = documentsUpdateFieldSchema.parse(payload);
    return updateDocumentField(db, id, key, value);
  });

  handle(IpcChannels.documentsUpdateTokens, (payload) => {
    const { id, tokens } = documentsUpdateTokensSchema.parse(payload);
    return updateDocumentTokens(db, id, tokens);
  });

  handle(IpcChannels.documentsDelete, (payload) => {
    const { id } = documentsDeleteSchema.parse(payload);
    return { deleted: deleteDocument(db, id) };
  });

  handle(IpcChannels.exportGenerate, (payload) => {
    const { id, format } = exportGenerateSchema.parse(payload);
    const document = getDocument(db, id);
    const { manifest } = getTemplate(db, document.templateId);
    return generateExport({ document, manifest, format });
  });

  handle(IpcChannels.exportSave, async (payload) => {
    const { html, suggestedName } = exportSaveSchema.parse(payload);
    const window = getMainWindow();
    const saveOptions = {
      title: 'Save exported template',
      defaultPath: suggestedName,
      filters: [
        { name: 'HTML files', extensions: ['html', 'htm'] },
        { name: 'All files', extensions: ['*'] },
      ],
    };
    const result = window
      ? await dialog.showSaveDialog(window, saveOptions)
      : await dialog.showSaveDialog(saveOptions);
    if (result.canceled || !result.filePath) {
      return { canceled: true };
    }
    await fs.writeFile(result.filePath, html, 'utf8');
    return { canceled: false, filePath: result.filePath };
  });
}
