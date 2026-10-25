import { afterEach, describe, expect, it } from 'vitest';
import { makeTestDb, addTestCustomer, addTestJob, addTestPour } from '../helpers';
import type { DatabaseSync } from 'node:sqlite';
import {
  addConsumption,
  addMaterial,
  addReceipt,
  getStock,
  listConsumption,
  listReceipts,
} from '../../electron/main/db/inventory';
import { OpsError } from '../../electron/main/errors';

let db: DatabaseSync;
afterEach(() => {
  try {
    db?.close();
  } catch {
    // ignore
  }
});

describe('inventory receipt/consumption consistency', () => {
  it('tracks stock on hand as receipts minus consumption', () => {
    db = makeTestDb();
    const cement = db.prepare("SELECT id FROM inventory_materials WHERE name = 'Portland cement'").get() as { id: number };
    addReceipt(db, { materialId: cement.id, supplier: 'Synthetic Supplies', receivedDate: '2026-10-23', qtyKg: 2000, costCents: 24000, notes: null });
    const customer = addTestCustomer(db);
    const job = addTestJob(db, customer.id);
    const pour = addTestPour(db, job.id);
    addConsumption(db, { pourId: pour.id, materialId: cement.id, qtyKg: 800 });

    const stock = getStock(db).find((s) => s.materialId === cement.id);
    expect(stock).toMatchObject({ receivedKg: 2000, consumedKg: 800, onHandKg: 1200 });
  });

  it('blocks consumption that would drive stock negative', () => {
    db = makeTestDb();
    const sand = db.prepare("SELECT id FROM inventory_materials WHERE name = 'Sand'").get() as { id: number };
    addReceipt(db, { materialId: sand.id, supplier: 'Synthetic Supplies', receivedDate: '2026-10-23', qtyKg: 500, costCents: 1000, notes: null });
    const customer = addTestCustomer(db);
    const job = addTestJob(db, customer.id);
    const pour = addTestPour(db, job.id);
    expect(() => addConsumption(db, { pourId: pour.id, materialId: sand.id, qtyKg: 501 })).toThrow(OpsError);
    // Exact-stock consumption is allowed.
    addConsumption(db, { pourId: pour.id, materialId: sand.id, qtyKg: 500 });
    expect(getStock(db).find((s) => s.materialId === sand.id)?.onHandKg).toBe(0);
  });

  it('lists receipts and consumption with their links', () => {
    db = makeTestDb();
    const gravel = db.prepare("SELECT id FROM inventory_materials WHERE name = 'Gravel (20mm)'").get() as { id: number };
    const r = addReceipt(db, { materialId: gravel.id, supplier: 'Synthetic Supplies', receivedDate: '2026-10-23', qtyKg: 3000, costCents: 9000, notes: null });
    const customer = addTestCustomer(db);
    const job = addTestJob(db, customer.id);
    const pour = addTestPour(db, job.id);
    const c = addConsumption(db, { pourId: pour.id, materialId: gravel.id, qtyKg: 1500 });
    expect(listReceipts(db, gravel.id)).toHaveLength(1);
    expect(listReceipts(db, gravel.id)[0]?.id).toBe(r.id);
    expect(listConsumption(db, pour.id)).toHaveLength(1);
    expect(listConsumption(db, pour.id)[0]?.id).toBe(c.id);
  });

  it('supports adding a new material', () => {
    db = makeTestDb();
    const m = addMaterial(db, 'Fly ash', 'kg');
    expect(m.name).toBe('Fly ash');
    expect(getStock(db).some((s) => s.materialId === m.id)).toBe(true);
  });
});
