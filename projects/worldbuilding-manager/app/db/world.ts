/**
 * Worldbuilding engine: SQLite-backed store for story entities, links,
 * revisions, timeline ordering, continuity checks, search and backups.
 *
 * Pure Node (node:sqlite) — no Electron imports — so it is testable and
 * runnable headlessly. All validation is explicit and raises AppError
 * with a named code; nothing fails silently.
 */
import { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { AppError, ErrorCodes } from '../shared/errors';
import { ENTITY_TYPES } from '../shared/types';
import type {
  ContinuityWarning,
  Entity,
  EntityInput,
  EntityPatch,
  EntityType,
  ImportResult,
  Link,
  LinkedEntity,
  Revision,
} from '../shared/types';

export const BACKUP_FORMAT = 'worldbuilding-manager.project';
export const BACKUP_FORMAT_VERSION = '1.0.0';
export const MAX_BACKUP_BYTES = 10 * 1024 * 1024;

const MAX_NAME = 200;
const MAX_LABEL = 80;
const MAX_DESCRIPTION = 50_000;
const MAX_BODY = 200_000;
const MAX_TAGS = 20;
const MAX_TAG_LENGTH = 40;

const SCHEMA = `
CREATE TABLE IF NOT EXISTS entities (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  story_date TEXT,
  order_key INTEGER,
  born_order INTEGER,
  died_order INTEGER,
  tags TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS links (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  target_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  label TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  UNIQUE(source_id, target_id, label)
);
CREATE TABLE IF NOT EXISTS revisions (
  entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  rev_no INTEGER NOT NULL,
  snapshot TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (entity_id, rev_no)
);
CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
  name, description, body, tags,
  content='entities', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN
  INSERT INTO entities_fts(rowid, name, description, body, tags)
  VALUES (new.rowid, new.name, new.description, new.body, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities BEGIN
  INSERT INTO entities_fts(entities_fts, rowid, name, description, body, tags)
  VALUES ('delete', old.rowid, old.name, old.description, old.body, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities BEGIN
  INSERT INTO entities_fts(entities_fts, rowid, name, description, body, tags)
  VALUES ('delete', old.rowid, old.name, old.description, old.body, old.tags);
  INSERT INTO entities_fts(rowid, name, description, body, tags)
  VALUES (new.rowid, new.name, new.description, new.body, new.tags);
END;
`;

interface EntityRow {
  id: string;
  type: string;
  name: string;
  role: string;
  description: string;
  body: string;
  story_date: string | null;
  order_key: number | null;
  born_order: number | null;
  died_order: number | null;
  tags: string;
  created_at: string;
  updated_at: string;
}

interface LinkRow {
  id: string;
  source_id: string;
  target_id: string;
  label: string;
  created_at: string;
}

function fail(code: string, message: string): never {
  throw new AppError(code, message);
}

function isEntityType(v: unknown): v is EntityType {
  return typeof v === 'string' && (ENTITY_TYPES as readonly string[]).includes(v);
}

function checkText(field: string, value: unknown, max: number, required: boolean): string {
  if (value === undefined || value === null) {
    if (required) return fail(ErrorCodes.Validation, `${field} is required.`);
    return '';
  }
  if (typeof value !== 'string') return fail(ErrorCodes.Validation, `${field} must be text.`);
  const v = value.trim();
  if (required && v.length === 0) return fail(ErrorCodes.Validation, `${field} must not be empty.`);
  if (v.length > max) return fail(ErrorCodes.Validation, `${field} is too long (max ${max} characters).`);
  return v;
}

function checkOrder(field: string, value: unknown): number | null {
  if (value === undefined || value === null) return null;
  if (typeof value !== 'number' || !Number.isFinite(value) || !Number.isInteger(value)) {
    return fail(ErrorCodes.Validation, `${field} must be a whole number or empty.`);
  }
  return value;
}

function checkTags(value: unknown): string[] {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) return fail(ErrorCodes.Validation, 'tags must be a list.');
  if (value.length > MAX_TAGS) return fail(ErrorCodes.Validation, `At most ${MAX_TAGS} tags are allowed.`);
  const out: string[] = [];
  for (const t of value) {
    if (typeof t !== 'string') return fail(ErrorCodes.Validation, 'Each tag must be text.');
    const tag = t.trim();
    if (tag.length === 0) continue;
    if (tag.length > MAX_TAG_LENGTH) return fail(ErrorCodes.Validation, `Tags are limited to ${MAX_TAG_LENGTH} characters.`);
    if (!out.includes(tag)) out.push(tag);
  }
  return out;
}

function rowToEntity(r: EntityRow): Entity {
  let tags: string[] = [];
  try {
    const parsed: unknown = JSON.parse(r.tags);
    if (Array.isArray(parsed)) tags = parsed.filter((t): t is string => typeof t === 'string');
  } catch {
    tags = [];
  }
  return {
    id: r.id,
    type: r.type as EntityType,
    name: r.name,
    role: r.role,
    description: r.description,
    body: r.body,
    storyDate: r.story_date,
    orderKey: r.order_key,
    bornOrder: r.born_order,
    diedOrder: r.died_order,
    tags,
    createdAt: r.created_at,
    updatedAt: r.updated_at,
  };
}

function rowToLink(r: LinkRow): Link {
  return { id: r.id, sourceId: r.source_id, targetId: r.target_id, label: r.label, createdAt: r.created_at };
}

function byTypeNameId(a: Entity, b: Entity): number {
  return a.type.localeCompare(b.type) || a.name.localeCompare(b.name) || a.id.localeCompare(b.id);
}

export class WorldStore {
  private readonly db: DatabaseSync;

  constructor(dbPath: string) {
    if (dbPath !== ':memory:') mkdirSync(dirname(dbPath), { recursive: true });
    this.db = new DatabaseSync(dbPath);
    this.db.exec('PRAGMA foreign_keys = ON;');
    this.db.exec(SCHEMA);
  }

  close(): void {
    this.db.close();
  }

  // ---------- entities ----------

  createEntity(input: EntityInput): Entity {
    if (!input || typeof input !== 'object') fail(ErrorCodes.Validation, 'Entity data is required.');
    if (!isEntityType(input.type)) fail(ErrorCodes.Validation, `Unknown entity type: ${String(input.type)}`);
    const now = new Date().toISOString();
    const entity: Entity = {
      id: randomUUID(),
      type: input.type,
      name: checkText('name', input.name, MAX_NAME, true),
      role: checkText('role', input.role, MAX_LABEL, false),
      description: checkText('description', input.description, MAX_DESCRIPTION, false),
      body: checkText('body', input.body, MAX_BODY, false),
      storyDate: input.storyDate === undefined || input.storyDate === null
        ? null
        : checkText('storyDate', input.storyDate, MAX_LABEL, false) || null,
      orderKey: checkOrder('orderKey', input.orderKey),
      bornOrder: checkOrder('bornOrder', input.bornOrder),
      diedOrder: checkOrder('diedOrder', input.diedOrder),
      tags: checkTags(input.tags),
      createdAt: now,
      updatedAt: now,
    };
    this.insertEntity(entity);
    this.appendRevision(entity);
    return entity;
  }

  getEntity(id: string): Entity | null {
    const row = this.db.prepare('SELECT * FROM entities WHERE id = ?').get(id) as EntityRow | undefined;
    return row ? rowToEntity(row) : null;
  }

  listEntities(type?: EntityType): Entity[] {
    const rows = (type
      ? this.db.prepare('SELECT * FROM entities WHERE type = ?').all(type)
      : this.db.prepare('SELECT * FROM entities').all()) as unknown as EntityRow[];
    return rows.map(rowToEntity).sort(byTypeNameId);
  }

  updateEntity(id: string, patch: EntityPatch): Entity {
    const current = this.getEntity(id);
    if (!current) fail(ErrorCodes.NotFound, `No entity with id ${id}.`);
    const next: Entity = {
      ...current,
      name: patch.name === undefined ? current.name : checkText('name', patch.name, MAX_NAME, true),
      role: patch.role === undefined ? current.role : checkText('role', patch.role, MAX_LABEL, false),
      description: patch.description === undefined
        ? current.description
        : checkText('description', patch.description, MAX_DESCRIPTION, false),
      body: patch.body === undefined ? current.body : checkText('body', patch.body, MAX_BODY, false),
      storyDate: patch.storyDate === undefined
        ? current.storyDate
        : patch.storyDate === null
          ? null
          : checkText('storyDate', patch.storyDate, MAX_LABEL, false) || null,
      orderKey: patch.orderKey === undefined ? current.orderKey : checkOrder('orderKey', patch.orderKey),
      bornOrder: patch.bornOrder === undefined ? current.bornOrder : checkOrder('bornOrder', patch.bornOrder),
      diedOrder: patch.diedOrder === undefined ? current.diedOrder : checkOrder('diedOrder', patch.diedOrder),
      tags: patch.tags === undefined ? current.tags : checkTags(patch.tags),
      updatedAt: new Date().toISOString(),
    };
    this.db.prepare(
      `UPDATE entities SET name=?, role=?, description=?, body=?, story_date=?, order_key=?,
       born_order=?, died_order=?, tags=?, updated_at=? WHERE id=?`,
    ).run(next.name, next.role, next.description, next.body, next.storyDate, next.orderKey,
      next.bornOrder, next.diedOrder, JSON.stringify(next.tags), next.updatedAt, next.id);
    this.appendRevision(next);
    return next;
  }

  deleteEntity(id: string): boolean {
    const info = this.db.prepare('DELETE FROM entities WHERE id = ?').run(id);
    return info.changes > 0;
  }

  // ---------- revisions (append-only) ----------

  listRevisions(entityId: string): Revision[] {
    const rows = this.db.prepare(
      'SELECT rev_no, snapshot, created_at FROM revisions WHERE entity_id = ? ORDER BY rev_no ASC',
    ).all(entityId) as unknown as { rev_no: number; snapshot: string; created_at: string }[];
    return rows.map((r) => ({
      entityId,
      revNo: r.rev_no,
      snapshot: JSON.parse(r.snapshot) as Entity,
      createdAt: r.created_at,
    }));
  }

  private appendRevision(entity: Entity): void {
    const row = this.db.prepare(
      'SELECT COALESCE(MAX(rev_no), 0) AS m FROM revisions WHERE entity_id = ?',
    ).get(entity.id) as { m: number };
    this.db.prepare('INSERT INTO revisions (entity_id, rev_no, snapshot, created_at) VALUES (?, ?, ?, ?)')
      .run(entity.id, row.m + 1, JSON.stringify(entity), entity.updatedAt);
  }

  private insertEntity(e: Entity): void {
    this.db.prepare(
      `INSERT INTO entities (id, type, name, role, description, body, story_date, order_key,
       born_order, died_order, tags, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(e.id, e.type, e.name, e.role, e.description, e.body, e.storyDate, e.orderKey,
      e.bornOrder, e.diedOrder, JSON.stringify(e.tags), e.createdAt, e.updatedAt);
  }

  // ---------- links ----------

  addLink(sourceId: string, targetId: string, label = ''): Link {
    if (sourceId === targetId) fail(ErrorCodes.SelfLink, 'An entity cannot be linked to itself.');
    const source = this.getEntity(sourceId);
    if (!source) fail(ErrorCodes.NotFound, `No entity with id ${sourceId}.`);
    const target = this.getEntity(targetId);
    if (!target) fail(ErrorCodes.NotFound, `No entity with id ${targetId}.`);
    const cleanLabel = checkText('label', label, MAX_LABEL, false);
    const existing = this.db.prepare(
      'SELECT * FROM links WHERE source_id = ? AND target_id = ? AND label = ?',
    ).get(sourceId, targetId, cleanLabel) as LinkRow | undefined;
    if (existing) return rowToLink(existing);
    const link: Link = {
      id: randomUUID(), sourceId, targetId, label: cleanLabel, createdAt: new Date().toISOString(),
    };
    this.db.prepare('INSERT INTO links (id, source_id, target_id, label, created_at) VALUES (?, ?, ?, ?, ?)')
      .run(link.id, link.sourceId, link.targetId, link.label, link.createdAt);
    return link;
  }

  removeLink(linkId: string): boolean {
    return this.db.prepare('DELETE FROM links WHERE id = ?').run(linkId).changes > 0;
  }

  listLinks(): Link[] {
    const rows = this.db.prepare('SELECT * FROM links').all() as unknown as LinkRow[];
    return rows.map(rowToLink)
      .sort((a, b) => a.sourceId.localeCompare(b.sourceId) || a.targetId.localeCompare(b.targetId) || a.label.localeCompare(b.label));
  }

  /** Bidirectional view: every link touching the entity, with the other end resolved. */
  linksForEntity(entityId: string): LinkedEntity[] {
    const rows = this.db.prepare(
      'SELECT * FROM links WHERE source_id = ? OR target_id = ?',
    ).all(entityId, entityId) as unknown as LinkRow[];
    const out: LinkedEntity[] = [];
    for (const r of rows) {
      const outgoing = r.source_id === entityId;
      const other = this.getEntity(outgoing ? r.target_id : r.source_id);
      if (!other) continue; // FK cascade makes this unreachable; stay defensive.
      out.push({ linkId: r.id, label: r.label, direction: outgoing ? 'outgoing' : 'incoming', entity: other });
    }
    return out.sort((a, b) => a.entity.name.localeCompare(b.entity.name) || a.label.localeCompare(b.label));
  }

  // ---------- timeline & continuity ----------

  timeline(): Entity[] {
    const events = this.listEntities('event');
    return events.sort((a, b) => {
      if (a.orderKey === null && b.orderKey !== null) return 1;
      if (a.orderKey !== null && b.orderKey === null) return -1;
      if (a.orderKey !== null && b.orderKey !== null && a.orderKey !== b.orderKey) return a.orderKey - b.orderKey;
      return (a.storyDate ?? '').localeCompare(b.storyDate ?? '') || a.name.localeCompare(b.name);
    });
  }

  /**
   * The one continuity rule set (deterministic, no guessing):
   * for each timeline event linked to a character —
   *  - event.orderKey > character.diedOrder (when both set)  -> EVENT_AFTER_DEATH
   *  - event.orderKey < character.bornOrder (when both set)  -> EVENT_BEFORE_BIRTH
   * Events without an order key, and characters without recorded birth/death
   * order keys, never produce warnings.
   */
  continuityWarnings(): ContinuityWarning[] {
    const warnings: ContinuityWarning[] = [];
    for (const event of this.timeline()) {
      if (event.orderKey === null) continue;
      for (const linked of this.linksForEntity(event.id)) {
        const c = linked.entity;
        if (c.type !== 'character') continue;
        if (c.diedOrder !== null && event.orderKey > c.diedOrder) {
          warnings.push({
            code: 'EVENT_AFTER_DEATH',
            eventId: event.id,
            eventName: event.name,
            characterId: c.id,
            characterName: c.name,
            message: `"${event.name}" (order ${event.orderKey}) is linked to ${c.name}, whose death is recorded at order ${c.diedOrder}.`,
          });
        }
        if (c.bornOrder !== null && event.orderKey < c.bornOrder) {
          warnings.push({
            code: 'EVENT_BEFORE_BIRTH',
            eventId: event.id,
            eventName: event.name,
            characterId: c.id,
            characterName: c.name,
            message: `"${event.name}" (order ${event.orderKey}) is linked to ${c.name}, whose birth is recorded at order ${c.bornOrder}.`,
          });
        }
      }
    }
    return warnings;
  }

  // ---------- search ----------

  search(text: string, type?: EntityType): Entity[] {
    const terms = (text.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []).slice(0, 10);
    if (terms.length === 0) return [];
    const match = terms.map((t) => `"${t}"*`).join(' AND ');
    try {
      const rows = this.db.prepare(
        `SELECT e.* FROM entities_fts f JOIN entities e ON e.rowid = f.rowid
         WHERE entities_fts MATCH ? ${type ? 'AND e.type = ?' : ''}
         ORDER BY rank LIMIT 200`,
      ).all(...(type ? [match, type] : [match])) as unknown as EntityRow[];
      return rows.map(rowToEntity);
    } catch {
      // Fall back to a plain substring scan if the FTS query is rejected.
      const like = `%${terms[0]}%`;
      const rows = this.db.prepare(
        `SELECT * FROM entities WHERE (name LIKE ? OR description LIKE ? OR body LIKE ?)
         ${type ? 'AND type = ?' : ''} LIMIT 200`,
      ).all(...(type ? [like, like, like, type] : [like, like, like])) as unknown as EntityRow[];
      return rows.map(rowToEntity).sort(byTypeNameId);
    }
  }

  // ---------- backup / export ----------

  exportBundle(): string {
    const entities = this.listEntities();
    const links = this.listLinks();
    const revisions: Revision[] = [];
    for (const e of entities) revisions.push(...this.listRevisions(e.id));
    revisions.sort((a, b) => a.entityId.localeCompare(b.entityId) || a.revNo - b.revNo);
    return JSON.stringify({
      format: BACKUP_FORMAT,
      formatVersion: BACKUP_FORMAT_VERSION,
      entities,
      links,
      revisions: revisions.map((r) => ({ entityId: r.entityId, revNo: r.revNo, snapshot: r.snapshot, createdAt: r.createdAt })),
    }, null, 2);
  }

  importBundle(json: string): ImportResult {
    if (typeof json !== 'string' || json.length === 0) fail(ErrorCodes.ImportInvalid, 'Backup data is empty.');
    if (Buffer.byteLength(json, 'utf8') > MAX_BACKUP_BYTES) {
      fail(ErrorCodes.ImportTooLarge, `Backup exceeds the ${MAX_BACKUP_BYTES} byte limit.`);
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(json);
    } catch {
      fail(ErrorCodes.ImportInvalid, 'Backup is not valid JSON.');
    }
    const bundle = parsed as {
      format?: unknown; formatVersion?: unknown;
      entities?: unknown; links?: unknown; revisions?: unknown;
    };
    if (!bundle || typeof bundle !== 'object' || bundle.format !== BACKUP_FORMAT) {
      fail(ErrorCodes.ImportInvalid, 'This file is not a Worldbuilding Manager project backup.');
    }
    const version = typeof bundle.formatVersion === 'string' ? bundle.formatVersion : '';
    const major = Number(version.split('.')[0]);
    if (!Number.isInteger(major)) fail(ErrorCodes.ImportInvalid, 'Backup has no readable format version.');
    if (major !== 1) {
      fail(ErrorCodes.ImportVersionUnsupported, `Backup format ${version} is not supported by this version of the app.`);
    }
    if (!Array.isArray(bundle.entities) || !Array.isArray(bundle.links) || !Array.isArray(bundle.revisions)) {
      fail(ErrorCodes.ImportInvalid, 'Backup is missing its entities, links or revisions lists.');
    }
    const entities: Entity[] = [];
    const seen = new Set<string>();
    for (const raw of bundle.entities) {
      entities.push(this.validateBundleEntity(raw, seen));
    }
    const links: Link[] = [];
    for (const raw of bundle.links) {
      const l = raw as Link;
      if (!l || typeof l.id !== 'string' || typeof l.sourceId !== 'string' || typeof l.targetId !== 'string'
        || typeof l.label !== 'string' || typeof l.createdAt !== 'string'
        || !seen.has(l.sourceId) || !seen.has(l.targetId) || l.sourceId === l.targetId) {
        fail(ErrorCodes.ImportInvalid, 'Backup contains a malformed or dangling link.');
      }
      links.push({ id: l.id, sourceId: l.sourceId, targetId: l.targetId, label: l.label, createdAt: l.createdAt });
    }
    const revisions: Revision[] = [];
    for (const raw of bundle.revisions) {
      const r = raw as Revision;
      if (!r || typeof r.entityId !== 'string' || !seen.has(r.entityId)
        || !Number.isInteger(r.revNo) || !r.snapshot || typeof r.snapshot !== 'object'
        || (r.snapshot as Entity).id !== r.entityId || typeof r.createdAt !== 'string') {
        fail(ErrorCodes.ImportInvalid, 'Backup contains a malformed revision.');
      }
      revisions.push({ entityId: r.entityId, revNo: r.revNo, snapshot: r.snapshot, createdAt: r.createdAt });
    }
    // Restore semantics: replace the whole project atomically.
    this.db.exec('BEGIN');
    try {
      this.db.exec('DELETE FROM revisions; DELETE FROM links; DELETE FROM entities;');
      for (const e of entities) this.insertEntity(e);
      for (const l of links) {
        this.db.prepare('INSERT INTO links (id, source_id, target_id, label, created_at) VALUES (?, ?, ?, ?, ?)')
          .run(l.id, l.sourceId, l.targetId, l.label, l.createdAt);
      }
      for (const r of revisions) {
        this.db.prepare('INSERT INTO revisions (entity_id, rev_no, snapshot, created_at) VALUES (?, ?, ?, ?)')
          .run(r.entityId, r.revNo, JSON.stringify(r.snapshot), r.createdAt);
      }
      this.db.exec('COMMIT');
    } catch (err) {
      this.db.exec('ROLLBACK');
      throw err;
    }
    return { entities: entities.length, links: links.length, revisions: revisions.length };
  }

  private validateBundleEntity(raw: unknown, seen: Set<string>): Entity {
    const e = raw as Entity;
    if (!e || typeof e !== 'object' || typeof e.id !== 'string' || e.id.length === 0 || seen.has(e.id)
      || !isEntityType(e.type) || typeof e.name !== 'string' || e.name.trim().length === 0
      || typeof e.role !== 'string' || typeof e.description !== 'string' || typeof e.body !== 'string'
      || !(e.storyDate === null || typeof e.storyDate === 'string')
      || !(e.orderKey === null || Number.isInteger(e.orderKey))
      || !(e.bornOrder === null || Number.isInteger(e.bornOrder))
      || !(e.diedOrder === null || Number.isInteger(e.diedOrder))
      || !Array.isArray(e.tags) || !e.tags.every((t) => typeof t === 'string')
      || typeof e.createdAt !== 'string' || typeof e.updatedAt !== 'string') {
      fail(ErrorCodes.ImportInvalid, 'Backup contains a malformed entity.');
    }
    seen.add(e.id);
    return {
      id: e.id, type: e.type, name: e.name, role: e.role, description: e.description, body: e.body,
      storyDate: e.storyDate, orderKey: e.orderKey, bornOrder: e.bornOrder, diedOrder: e.diedOrder,
      tags: [...e.tags], createdAt: e.createdAt, updatedAt: e.updatedAt,
    };
  }

  /** Human-readable single-document Markdown export, deterministically ordered. */
  exportMarkdown(): string {
    const lines: string[] = ['# Worldbuilding project export', ''];
    const names = new Map(this.listEntities().map((e) => [e.id, e.name]));
    for (const type of ENTITY_TYPES) {
      const items = this.listEntities(type);
      if (items.length === 0) continue;
      lines.push(`## ${type.charAt(0).toUpperCase()}${type.slice(1)}s`, '');
      for (const e of items) {
        lines.push(`### ${e.name}`, '');
        if (e.role) lines.push(`- Role: ${e.role}`);
        if (e.storyDate) lines.push(`- Story date: ${e.storyDate}`);
        if (e.orderKey !== null) lines.push(`- Timeline order: ${e.orderKey}`);
        if (e.tags.length > 0) lines.push(`- Tags: ${e.tags.join(', ')}`);
        if (e.description) lines.push('', e.description);
        if (e.body) lines.push('', e.body);
        const linked = this.linksForEntity(e.id);
        if (linked.length > 0) {
          lines.push('', 'Links:');
          for (const l of linked) {
            lines.push(`- ${l.label ? `${l.label}: ` : ''}${names.get(l.entity.id) ?? l.entity.name}`);
          }
        }
        lines.push('');
      }
    }
    const warnings = this.continuityWarnings();
    if (warnings.length > 0) {
      lines.push('## Continuity warnings', '');
      for (const w of warnings) lines.push(`- ${w.message}`);
      lines.push('');
    }
    return lines.join('\n');
  }
}
