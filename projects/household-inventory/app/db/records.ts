/**
 * CRUD helpers over node:sqlite for items, attachments and maintenance
 * events. All functions take the open DatabaseSync explicitly so they stay
 * testable without the Electron runtime (no 'electron' import here).
 *
 * Row mapping: snake_case columns <-> camelCase shared types.
 */
import type { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import type {
  Attachment,
  Item,
  ItemDetail,
  MaintenanceEvent,
} from '../shared/types';
import type { ItemInput, ItemFilterInput, MaintenanceInput } from '../shared/schemas';
import { matchesSearch } from '../engine/inventory';

interface ItemRow {
  id: string;
  name: string;
  category: string;
  location: string;
  purchase_price_cents: number | null;
  purchase_date: string | null;
  serial_number: string | null;
  notes: string;
  warranty_start: string | null;
  warranty_end: string | null;
  created_at: string;
  updated_at: string;
}

interface AttachmentRow {
  id: string;
  item_id: string;
  original_name: string;
  stored_name: string;
  mime: string;
  size_bytes: number;
  sha256: string;
  kind: string;
  created_at: string;
}

interface MaintenanceRow {
  id: string;
  item_id: string;
  event_date: string;
  description: string;
  cost_cents: number | null;
  created_at: string;
}

function mapItem(row: ItemRow): Item {
  return {
    id: row.id,
    name: row.name,
    category: row.category,
    location: row.location,
    purchasePriceCents: row.purchase_price_cents,
    purchaseDate: row.purchase_date,
    serialNumber: row.serial_number,
    notes: row.notes,
    warrantyStart: row.warranty_start,
    warrantyEnd: row.warranty_end,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

function mapAttachment(row: AttachmentRow): Attachment {
  return {
    id: row.id,
    itemId: row.item_id,
    originalName: row.original_name,
    storedName: row.stored_name,
    mime: row.mime,
    sizeBytes: row.size_bytes,
    sha256: row.sha256,
    kind: row.kind as Attachment['kind'],
    createdAt: row.created_at,
  };
}

function mapMaintenance(row: MaintenanceRow): MaintenanceEvent {
  return {
    id: row.id,
    itemId: row.item_id,
    eventDate: row.event_date,
    description: row.description,
    costCents: row.cost_cents,
    createdAt: row.created_at,
  };
}

function nowIso(): string {
  return new Date().toISOString();
}

/** List items, optionally filtered by category/location and a free-text search. */
export function listItems(db: DatabaseSync, filter?: ItemFilterInput): Item[] {
  const where: string[] = [];
  const params: (string | null)[] = [];
  if (filter?.category) {
    where.push('category = ?');
    params.push(filter.category);
  }
  if (filter?.location) {
    where.push('location = ?');
    params.push(filter.location);
  }
  const sql = `SELECT * FROM items${where.length > 0 ? ` WHERE ${where.join(' AND ')}` : ''} ORDER BY name ASC, id ASC`;
  const rows = db.prepare(sql).all(...params) as unknown as ItemRow[];
  let items = rows.map(mapItem);
  if (filter?.search) {
    items = items.filter((item) => matchesSearch(item, filter.search as string));
  }
  return items;
}

/** Distinct category names, sorted. */
export function listCategories(db: DatabaseSync): string[] {
  const rows = db
    .prepare('SELECT DISTINCT category FROM items ORDER BY category ASC')
    .all() as { category: string }[];
  return rows.map((r) => r.category);
}

export function getItem(db: DatabaseSync, id: string): Item | null {
  const row = db.prepare('SELECT * FROM items WHERE id = ?').get(id) as unknown as ItemRow | undefined;
  return row ? mapItem(row) : null;
}

export function getItemDetail(db: DatabaseSync, id: string): ItemDetail | null {
  const item = getItem(db, id);
  if (!item) return null;
  return {
    item,
    attachments: listAttachments(db, id),
    maintenance: listMaintenanceEvents(db, id),
  };
}

export function createItem(db: DatabaseSync, input: ItemInput): Item {
  const id = randomUUID();
  const now = nowIso();
  db.prepare(
    `INSERT INTO items
      (id, name, category, location, purchase_price_cents, purchase_date,
       serial_number, notes, warranty_start, warranty_end, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    id,
    input.name,
    input.category,
    input.location,
    input.purchasePriceCents,
    input.purchaseDate,
    input.serialNumber,
    input.notes,
    input.warrantyStart,
    input.warrantyEnd,
    now,
    now,
  );
  const created = getItem(db, id);
  if (!created) throw new Error('createItem: row missing after insert');
  return created;
}

export function updateItem(db: DatabaseSync, id: string, input: ItemInput): Item | null {
  const existing = getItem(db, id);
  if (!existing) return null;
  db.prepare(
    `UPDATE items SET
       name = ?, category = ?, location = ?, purchase_price_cents = ?,
       purchase_date = ?, serial_number = ?, notes = ?,
       warranty_start = ?, warranty_end = ?, updated_at = ?
     WHERE id = ?`,
  ).run(
    input.name,
    input.category,
    input.location,
    input.purchasePriceCents,
    input.purchaseDate,
    input.serialNumber,
    input.notes,
    input.warrantyStart,
    input.warrantyEnd,
    nowIso(),
    id,
  );
  return getItem(db, id);
}

/**
 * Delete an item. Attachment/maintenance rows cascade via FK.
 * Returns the attachment rows so the caller can delete their files first.
 */
export function deleteItem(db: DatabaseSync, id: string): { deleted: boolean; attachments: Attachment[] } {
  const attachments = listAttachments(db, id);
  const result = db.prepare('DELETE FROM items WHERE id = ?').run(id);
  return { deleted: Number(result.changes) > 0, attachments };
}

export interface NewAttachmentRow {
  itemId: string;
  originalName: string;
  storedName: string;
  mime: string;
  sizeBytes: number;
  sha256: string;
  kind: Attachment['kind'];
}

export function addAttachment(db: DatabaseSync, row: NewAttachmentRow): Attachment {
  const id = randomUUID();
  const createdAt = nowIso();
  db.prepare(
    `INSERT INTO attachments
       (id, item_id, original_name, stored_name, mime, size_bytes, sha256, kind, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(id, row.itemId, row.originalName, row.storedName, row.mime, row.sizeBytes, row.sha256, row.kind, createdAt);
  const created = getAttachment(db, id);
  if (!created) throw new Error('addAttachment: row missing after insert');
  return created;
}

export function getAttachment(db: DatabaseSync, id: string): Attachment | null {
  const row = db.prepare('SELECT * FROM attachments WHERE id = ?').get(id) as unknown as
    | AttachmentRow
    | undefined;
  return row ? mapAttachment(row) : null;
}

export function listAttachments(db: DatabaseSync, itemId: string): Attachment[] {
  const rows = db
    .prepare('SELECT * FROM attachments WHERE item_id = ? ORDER BY created_at ASC, id ASC')
    .all(itemId) as unknown as AttachmentRow[];
  return rows.map(mapAttachment);
}

/** Returns the deleted row (for file cleanup) or null when missing. */
export function deleteAttachment(db: DatabaseSync, id: string): Attachment | null {
  const row = getAttachment(db, id);
  if (!row) return null;
  db.prepare('DELETE FROM attachments WHERE id = ?').run(id);
  return row;
}

export function countAttachments(db: DatabaseSync): number {
  const row = db.prepare('SELECT COUNT(*) AS n FROM attachments').get() as unknown as { n: number };
  return row.n;
}

export function countItems(db: DatabaseSync): number {
  const row = db.prepare('SELECT COUNT(*) AS n FROM items').get() as unknown as { n: number };
  return row.n;
}

export function addMaintenanceEvent(
  db: DatabaseSync,
  itemId: string,
  input: MaintenanceInput,
): MaintenanceEvent {
  const id = randomUUID();
  const createdAt = nowIso();
  db.prepare(
    `INSERT INTO maintenance_events (id, item_id, event_date, description, cost_cents, created_at)
     VALUES (?, ?, ?, ?, ?, ?)`,
  ).run(id, itemId, input.eventDate, input.description, input.costCents, createdAt);
  const row = db.prepare('SELECT * FROM maintenance_events WHERE id = ?').get(id) as unknown as MaintenanceRow | undefined;
  if (!row) throw new Error('addMaintenanceEvent: row missing after insert');
  return mapMaintenance(row);
}

export function listMaintenanceEvents(db: DatabaseSync, itemId: string): MaintenanceEvent[] {
  const rows = db
    .prepare(
      'SELECT * FROM maintenance_events WHERE item_id = ? ORDER BY event_date DESC, created_at DESC, id ASC',
    )
    .all(itemId) as unknown as MaintenanceRow[];
  return rows.map(mapMaintenance);
}

/** Returns true when a row was deleted. */
export function deleteMaintenanceEvent(db: DatabaseSync, id: string): boolean {
  const result = db.prepare('DELETE FROM maintenance_events WHERE id = ?').run(id);
  return Number(result.changes) > 0;
}
