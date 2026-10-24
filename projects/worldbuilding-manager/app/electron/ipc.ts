/**
 * IPC handlers: validate payloads with zod, delegate to the engine,
 * and always answer with an IpcResult envelope (never throw across IPC).
 */
import { ipcMain } from 'electron';
import { AppError, ErrorCodes } from '../shared/errors';
import {
  entityInputSchema, entityPatchSchema, idSchema, importSchema, linkAddSchema, listSchema, searchSchema,
} from '../shared/schemas';
import { WbmChannels } from '../shared/types';
import type { EntityInput, EntityPatch, IpcResult } from '../shared/types';
import type { WorldStore } from '../db/world';

function stripUndefined(obj: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) if (v !== undefined) out[k] = v;
  return out;
}

function wrap<T>(fn: () => T): IpcResult<T> {
  try {
    return { ok: true, data: fn() };
  } catch (err) {
    if (err instanceof AppError) return { ok: false, error: { code: err.code, message: err.message } };
    if (err instanceof Error && err.name === 'ZodError') {
      return { ok: false, error: { code: ErrorCodes.Validation, message: `Invalid request: ${err.message}` } };
    }
    return { ok: false, error: { code: 'INTERNAL_ERROR', message: err instanceof Error ? err.message : String(err) } };
  }
}

export function registerIpc(store: WorldStore): void {
  const on = (channel: string, fn: (payload: unknown) => unknown): void => {
    ipcMain.handle(channel, (_event, payload) => wrap(() => fn(payload)));
  };

  on(WbmChannels.entitiesCreate, (p) => store.createEntity(stripUndefined(entityInputSchema.parse(p)) as unknown as EntityInput));
  on(WbmChannels.entitiesGet, (p) => store.getEntity(idSchema.parse(p).id));
  on(WbmChannels.entitiesList, (p) => store.listEntities(listSchema.parse(p)?.type));
  on(WbmChannels.entitiesUpdate, (p) => {
    const { id, patch } = p as { id?: unknown; patch?: unknown };
    const parsedId = idSchema.parse({ id });
    const clean = stripUndefined(entityPatchSchema.parse(patch ?? {})) as EntityPatch;
    return store.updateEntity(parsedId.id, clean);
  });
  on(WbmChannels.entitiesRemove, (p) => store.deleteEntity(idSchema.parse(p).id));
  on(WbmChannels.linksAdd, (p) => {
    const v = linkAddSchema.parse(p);
    return store.addLink(v.sourceId, v.targetId, v.label ?? '');
  });
  on(WbmChannels.linksRemove, (p) => store.removeLink(idSchema.parse(p).id));
  on(WbmChannels.linksForEntity, (p) => store.linksForEntity(idSchema.parse(p).id));
  on(WbmChannels.revisionsList, (p) => store.listRevisions(idSchema.parse(p).id));
  on(WbmChannels.timelineList, () => store.timeline());
  on(WbmChannels.continuityWarnings, () => store.continuityWarnings());
  on(WbmChannels.searchQuery, (p) => {
    const v = searchSchema.parse(p);
    return store.search(v.text, v.type);
  });
  on(WbmChannels.backupExportJson, () => store.exportBundle());
  on(WbmChannels.backupImportJson, (p) => store.importBundle(importSchema.parse(p).json));
  on(WbmChannels.backupExportMarkdown, () => store.exportMarkdown());
}
