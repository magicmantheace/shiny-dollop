import { DatabaseSync } from 'node:sqlite';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { runMigrations } from '../../db/migrations';
import * as records from '../../db/records';
import type { ItemInput } from '../../shared/schemas';

let db: DatabaseSync;

function itemInput(overrides: Partial<ItemInput> = {}): ItemInput {
  return {
    name: 'Test Fridge',
    category: 'Appliances',
    location: 'Kitchen',
    purchasePriceCents: 129900,
    purchaseDate: '2024-02-29',
    serialNumber: 'SN-123',
    notes: 'synthetic fixture',
    warrantyStart: '2024-02-29',
    warrantyEnd: '2027-02-28',
    ...overrides,
  };
}

beforeEach(() => {
  db = new DatabaseSync(':memory:');
  runMigrations(db); // also enables PRAGMA foreign_keys = ON
});

afterEach(() => {
  db.close();
});

describe('item CRUD round-trip', () => {
  it('creates, reads, updates and deletes an item with all fields preserved', () => {
    const created = records.createItem(db, itemInput());
    expect(created.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(created.createdAt).toBeTruthy();

    const fetched = records.getItem(db, created.id);
    expect(fetched).toMatchObject({
      name: 'Test Fridge',
      category: 'Appliances',
      location: 'Kitchen',
      purchasePriceCents: 129900,
      purchaseDate: '2024-02-29',
      serialNumber: 'SN-123',
      notes: 'synthetic fixture',
      warrantyStart: '2024-02-29',
      warrantyEnd: '2027-02-28',
    });

    const updated = records.updateItem(db, created.id, itemInput({ name: 'Renamed', notes: '' }));
    expect(updated?.name).toBe('Renamed');
    expect(updated?.notes).toBe('');

    const { deleted } = records.deleteItem(db, created.id);
    expect(deleted).toBe(true);
    expect(records.getItem(db, created.id)).toBeNull();
  });

  it('stores nulls for optional fields', () => {
    const created = records.createItem(
      db,
      itemInput({
        purchasePriceCents: null,
        purchaseDate: null,
        serialNumber: null,
        warrantyStart: null,
        warrantyEnd: null,
      }),
    );
    const fetched = records.getItem(db, created.id);
    expect(fetched?.purchasePriceCents).toBeNull();
    expect(fetched?.purchaseDate).toBeNull();
    expect(fetched?.serialNumber).toBeNull();
    expect(fetched?.warrantyEnd).toBeNull();
  });

  it('returns null/false for missing ids', () => {
    const missing = '11111111-2222-4333-8444-555555555555';
    expect(records.getItem(db, missing)).toBeNull();
    expect(records.getItemDetail(db, missing)).toBeNull();
    expect(records.updateItem(db, missing, itemInput())).toBeNull();
    expect(records.deleteItem(db, missing).deleted).toBe(false);
  });
});

describe('listItems filters', () => {
  beforeEach(() => {
    records.createItem(db, itemInput({ name: 'Kitchen Fridge', category: 'Appliances', location: 'Kitchen' }));
    records.createItem(db, itemInput({ name: 'Garage Fridge', category: 'Appliances', location: 'Garage' }));
    records.createItem(db, itemInput({ name: 'Desk Lamp', category: 'Lighting', location: 'Office' }));
  });

  it('filters by category and location', () => {
    expect(records.listItems(db, { category: 'Appliances' })).toHaveLength(2);
    expect(records.listItems(db, { location: 'Garage' })).toHaveLength(1);
    expect(records.listItems(db, { category: 'Lighting', location: 'Office' })[0].name).toBe('Desk Lamp');
  });

  it('searches case-insensitively across name, category, location, serial and notes', () => {
    expect(records.listItems(db, { search: 'fridge' })).toHaveLength(2);
    expect(records.listItems(db, { search: 'FRIDGE' })).toHaveLength(2);
    expect(records.listItems(db, { search: 'garage' })).toHaveLength(1);
    expect(records.listItems(db, { search: 'SN-123' })).toHaveLength(3);
    expect(records.listItems(db, { search: 'synthetic fixture' })).toHaveLength(3);
    expect(records.listItems(db, { search: 'no-such-thing' })).toHaveLength(0);
  });

  it('lists distinct categories sorted', () => {
    expect(records.listCategories(db)).toEqual(['Appliances', 'Lighting']);
  });
});

describe('item detail and cascading deletes', () => {
  it('bundles attachments + maintenance, and deletes them with the item', () => {
    const item = records.createItem(db, itemInput());
    const att = records.addAttachment(db, {
      itemId: item.id,
      originalName: 'receipt.png',
      storedName: 'uuid-1.png',
      mime: 'image/png',
      sizeBytes: 10,
      sha256: 'abc',
      kind: 'receipt',
    });
    const evt = records.addMaintenanceEvent(db, item.id, {
      eventDate: '2026-10-01',
      description: 'Cleaned coils',
      costCents: 0,
    });

    const detail = records.getItemDetail(db, item.id);
    expect(detail?.attachments.map((a) => a.id)).toEqual([att.id]);
    expect(detail?.maintenance.map((m) => m.id)).toEqual([evt.id]);

    const { deleted, attachments } = records.deleteItem(db, item.id);
    expect(deleted).toBe(true);
    expect(attachments).toHaveLength(1);
    expect(records.getAttachment(db, att.id)).toBeNull();
    expect(records.listMaintenanceEvents(db, item.id)).toEqual([]);
  });
});

describe('attachment rows', () => {
  it('adds, lists and deletes attachment rows', () => {
    const item = records.createItem(db, itemInput());
    const a1 = records.addAttachment(db, {
      itemId: item.id,
      originalName: 'a.png',
      storedName: 's1.png',
      mime: 'image/png',
      sizeBytes: 5,
      sha256: 'h1',
      kind: 'photo',
    });
    records.addAttachment(db, {
      itemId: item.id,
      originalName: 'b.pdf',
      storedName: 's2.pdf',
      mime: 'application/pdf',
      sizeBytes: 7,
      sha256: 'h2',
      kind: 'manual',
    });
    expect(records.listAttachments(db, item.id)).toHaveLength(2);

    const removed = records.deleteAttachment(db, a1.id);
    expect(removed?.storedName).toBe('s1.png');
    expect(records.getAttachment(db, a1.id)).toBeNull();
    expect(records.deleteAttachment(db, a1.id)).toBeNull();
  });
});

describe('maintenance events', () => {
  it('adds, lists newest-first, and deletes events', () => {
    const item = records.createItem(db, itemInput());
    const e1 = records.addMaintenanceEvent(db, item.id, {
      eventDate: '2026-09-01',
      description: 'First service',
      costCents: null,
    });
    const e2 = records.addMaintenanceEvent(db, item.id, {
      eventDate: '2026-10-01',
      description: 'Second service',
      costCents: 2500,
    });
    const listed = records.listMaintenanceEvents(db, item.id);
    expect(listed.map((e) => e.id)).toEqual([e2.id, e1.id]); // newest first
    expect(listed[0].costCents).toBe(2500);

    expect(records.deleteMaintenanceEvent(db, e1.id)).toBe(true);
    expect(records.deleteMaintenanceEvent(db, e1.id)).toBe(false);
    expect(records.listMaintenanceEvents(db, item.id)).toHaveLength(1);
  });
});
