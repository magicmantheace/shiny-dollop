/**
 * Shared domain + IPC contract for the Novel and Worldbuilding Manager.
 * Types are compile-time only in the preload (it must stay self-contained
 * at runtime); channel constants are used by the main process.
 */

export const ENTITY_TYPES = ['character', 'location', 'faction', 'event', 'note'] as const;
export type EntityType = (typeof ENTITY_TYPES)[number];

export interface Entity {
  id: string;
  type: EntityType;
  /** Display name / title. */
  name: string;
  /** Characters only: role in the story (protagonist, mentor, ...). '' otherwise. */
  role: string;
  /** Short description / summary. */
  description: string;
  /** Long-form markdown-friendly text (notes, lore, chapter text). */
  body: string;
  /** Events only: free-text story date label (custom calendars welcome). */
  storyDate: string | null;
  /** Events only: numeric ordering key used for timeline sorting and continuity checks. */
  orderKey: number | null;
  /** Characters only: order key of the character's birth, when recorded. */
  bornOrder: number | null;
  /** Characters only: order key of the character's death, when recorded. */
  diedOrder: number | null;
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

export interface EntityInput {
  type: EntityType;
  name: string;
  role?: string;
  description?: string;
  body?: string;
  storyDate?: string | null;
  orderKey?: number | null;
  bornOrder?: number | null;
  diedOrder?: number | null;
  tags?: string[];
}

export type EntityPatch = Partial<Omit<EntityInput, 'type'>>;

export interface Link {
  id: string;
  sourceId: string;
  targetId: string;
  /** Relationship / association label, e.g. "ally", "rival", "located-in". '' = plain link. */
  label: string;
  createdAt: string;
}

/** A link as seen from one entity: the other end plus direction. */
export interface LinkedEntity {
  linkId: string;
  label: string;
  direction: 'outgoing' | 'incoming';
  entity: Entity;
}

export interface Revision {
  entityId: string;
  revNo: number;
  /** Full JSON snapshot of the entity at that revision. */
  snapshot: Entity;
  createdAt: string;
}

export type ContinuityWarningCode = 'EVENT_AFTER_DEATH' | 'EVENT_BEFORE_BIRTH';

export interface ContinuityWarning {
  code: ContinuityWarningCode;
  eventId: string;
  eventName: string;
  characterId: string;
  characterName: string;
  message: string;
}

export interface ImportResult {
  entities: number;
  links: number;
  revisions: number;
}

export type IpcResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string } };

/** The narrow API exposed to the renderer as `window.wbm`. */
export interface WbmApi {
  entities: {
    create(input: EntityInput): Promise<Entity>;
    get(id: string): Promise<Entity | null>;
    list(type?: EntityType): Promise<Entity[]>;
    update(id: string, patch: EntityPatch): Promise<Entity>;
    remove(id: string): Promise<boolean>;
  };
  links: {
    add(sourceId: string, targetId: string, label?: string): Promise<Link>;
    remove(linkId: string): Promise<boolean>;
    forEntity(entityId: string): Promise<LinkedEntity[]>;
  };
  revisions: {
    list(entityId: string): Promise<Revision[]>;
  };
  timeline: {
    list(): Promise<Entity[]>;
  };
  continuity: {
    warnings(): Promise<ContinuityWarning[]>;
  };
  search: {
    query(text: string, type?: EntityType): Promise<Entity[]>;
  };
  backup: {
    exportJson(): Promise<string>;
    importJson(json: string): Promise<ImportResult>;
    exportMarkdown(): Promise<string>;
  };
}

export const WbmChannels = {
  entitiesCreate: 'wbm:entities.create',
  entitiesGet: 'wbm:entities.get',
  entitiesList: 'wbm:entities.list',
  entitiesUpdate: 'wbm:entities.update',
  entitiesRemove: 'wbm:entities.remove',
  linksAdd: 'wbm:links.add',
  linksRemove: 'wbm:links.remove',
  linksForEntity: 'wbm:links.forEntity',
  revisionsList: 'wbm:revisions.list',
  timelineList: 'wbm:timeline.list',
  continuityWarnings: 'wbm:continuity.warnings',
  searchQuery: 'wbm:search.query',
  backupExportJson: 'wbm:backup.exportJson',
  backupImportJson: 'wbm:backup.importJson',
  backupExportMarkdown: 'wbm:backup.exportMarkdown',
} as const;
