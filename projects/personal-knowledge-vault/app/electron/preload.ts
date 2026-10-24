/**
 * Preload script. Runs in a sandboxed context with access to ipcRenderer.
 * Exposes ONLY the narrow typed `window.pkv` API — no raw ipcRenderer,
 * no Node APIs, no arbitrary channel access.
 */
import { contextBridge, ipcRenderer } from 'electron';
import { PkvChannels } from '../shared/types';
import type { BackupImportResult, IpcResult, Note, NoteFilters, PkvApi, Revision, SearchFilters } from '../shared/types';

function invoke<T>(channel: string, payload?: unknown): Promise<T> {
  return ipcRenderer.invoke(channel, payload).then((result: unknown) => {
    const envelope = result as IpcResult<T>;
    if (!envelope || typeof envelope !== 'object' || !('ok' in envelope)) {
      throw new Error('Malformed IPC response.');
    }
    if (!envelope.ok) {
      const err = new Error(envelope.error.message) as Error & { code: string };
      err.code = envelope.error.code;
      throw err;
    }
    return envelope.data;
  });
}

const api: PkvApi = {
  notes: {
    create: (input) => invoke<Note>(PkvChannels.notesCreate, input),
    get: (id) => invoke<Note | null>(PkvChannels.notesGet, { id }),
    list: (filters?: NoteFilters) => invoke<Note[]>(PkvChannels.notesList, filters ?? {}),
    update: (id, input) => invoke<Note>(PkvChannels.notesUpdate, { id, ...input }),
    delete: (id) => invoke<boolean>(PkvChannels.notesDelete, { id }),
    search: (query, filters?: SearchFilters) =>
      invoke<Note[]>(PkvChannels.notesSearch, { query, ...(filters ?? {}) }),
  },
  review: {
    approve: (id) => invoke<Note>(PkvChannels.reviewApprove, { id }),
    reject: (id, reason) => invoke<Note>(PkvChannels.reviewReject, { id, reason }),
  },
  revisions: {
    list: (noteId) => invoke<Revision[]>(PkvChannels.revisionsList, { noteId }),
  },
  backup: {
    export: () => invoke<string>(PkvChannels.backupExport, {}),
    import: (json) => invoke<BackupImportResult>(PkvChannels.backupImport, { json }),
  },
};

contextBridge.exposeInMainWorld('pkv', api);

declare global {
  interface Window {
    pkv: PkvApi;
  }
}
