/**
 * Preload: exposes ONLY the narrow typed `window.wbm` API.
 * Self-contained at runtime — channel names are literals here and all
 * shared imports are type-only, because Electron's sandboxed preload
 * loader cannot require sibling modules.
 */
import { contextBridge, ipcRenderer } from 'electron';
import type {
  ContinuityWarning, Entity, EntityInput, EntityPatch, EntityType, ImportResult, IpcResult, Link, LinkedEntity, Revision, WbmApi,
} from '../shared/types';

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

const api: WbmApi = {
  entities: {
    create: (input: EntityInput) => invoke<Entity>('wbm:entities.create', input),
    get: (id: string) => invoke<Entity | null>('wbm:entities.get', { id }),
    list: (type?: EntityType) => invoke<Entity[]>('wbm:entities.list', type ? { type } : {}),
    update: (id: string, patch: EntityPatch) => invoke<Entity>('wbm:entities.update', { id, patch }),
    remove: (id: string) => invoke<boolean>('wbm:entities.remove', { id }),
  },
  links: {
    add: (sourceId: string, targetId: string, label?: string) =>
      invoke<Link>('wbm:links.add', { sourceId, targetId, label: label ?? '' }),
    remove: (linkId: string) => invoke<boolean>('wbm:links.remove', { id: linkId }),
    forEntity: (entityId: string) => invoke<LinkedEntity[]>('wbm:links.forEntity', { id: entityId }),
  },
  revisions: {
    list: (entityId: string) => invoke<Revision[]>('wbm:revisions.list', { id: entityId }),
  },
  timeline: {
    list: () => invoke<Entity[]>('wbm:timeline.list'),
  },
  continuity: {
    warnings: () => invoke<ContinuityWarning[]>('wbm:continuity.warnings'),
  },
  search: {
    query: (text: string, type?: EntityType) =>
      invoke<Entity[]>('wbm:search.query', type ? { text, type } : { text }),
  },
  backup: {
    exportJson: () => invoke<string>('wbm:backup.exportJson'),
    importJson: (json: string) => invoke<ImportResult>('wbm:backup.importJson', { json }),
    exportMarkdown: () => invoke<string>('wbm:backup.exportMarkdown'),
  },
};

contextBridge.exposeInMainWorld('wbm', api);
