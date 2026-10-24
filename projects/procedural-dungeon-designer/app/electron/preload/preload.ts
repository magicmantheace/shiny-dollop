// Sandboxed preload: self-contained at runtime.
// Only the Electron bridge API is imported at runtime; the PddApi import
// is type-only and erased at compile time. Channel strings are literals
// in this file (mirroring electron/main/channels.ts) because a sandboxed
// preload cannot load project modules at runtime.
import { contextBridge, ipcRenderer } from 'electron';
import type { PddApi } from '../../shared/types.js';

// IPC results arrive as a structured envelope (shared/ipc-envelope.ts):
// the main process RETURNS failures as { ok: false, error } response
// data instead of throwing, because Electron serializes errors thrown
// through ipcMain.handle down to their message and the error code
// (e.g. BUDGET_EXCEEDED) would be lost. This unwrap logic is an inline
// copy of unwrapIpcEnvelope from shared/ipc-envelope.ts — a sandboxed
// preload cannot import that module at runtime, and a backend test
// guards that this copy exists. Keep the two in step.
interface IpcEnvelopeShape {
  ok: boolean;
  value?: unknown;
  error?: { code: string; message: string };
}

async function unwrapEnvelope<T>(channel: string, ...args: unknown[]): Promise<T> {
  const envelope = (await ipcRenderer.invoke(channel, ...args)) as IpcEnvelopeShape;
  if (envelope && typeof envelope === 'object' && typeof envelope.ok === 'boolean') {
    if (envelope.ok) return envelope.value as T;
    if (envelope.error) throw envelope.error;
    throw { code: 'ERROR', message: `IPC call ${channel} failed without an error detail.` };
  }
  // Not an envelope (should not happen with the current main process):
  // pass the raw result through rather than inventing a failure.
  return envelope as T;
}

const pdd: PddApi = {
  themesList: () => unwrapEnvelope('pdd:themes-list'),
  generate: (params) => unwrapEnvelope('pdd:generate', params),
  validateMap: (map) => unwrapEnvelope('pdd:validate-map', map),
  dungeonsSave: (input) => unwrapEnvelope('pdd:dungeons-save', input),
  dungeonsList: () => unwrapEnvelope('pdd:dungeons-list'),
  dungeonsGet: (id) => unwrapEnvelope('pdd:dungeons-get', id),
  dungeonsDelete: (id) => unwrapEnvelope('pdd:dungeons-delete', id),
  placementsAdd: (dungeonId, op) => unwrapEnvelope('pdd:placements-add', dungeonId, op),
  placementsRemove: (dungeonId, placementId) =>
    unwrapEnvelope('pdd:placements-remove', dungeonId, placementId),
  placementsMove: (dungeonId, placementId, toRoomId) =>
    unwrapEnvelope('pdd:placements-move', dungeonId, placementId, toRoomId),
  exportJson: (dungeonId) => unwrapEnvelope('pdd:export-json', dungeonId),
  exportMarkdown: (dungeonId) => unwrapEnvelope('pdd:export-markdown', dungeonId),
  importJson: (text) => unwrapEnvelope('pdd:import-json', text),
};

contextBridge.exposeInMainWorld('pdd', pdd);
