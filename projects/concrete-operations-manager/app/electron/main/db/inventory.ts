/**
 * Inventory: bulk materials, supplier receipts and per-pour consumption.
 *
 * Consistency rule: cumulative consumption of a material can never exceed
 * cumulative receipts. stock-on-hand = received − consumed, per material.
 */
import type { DatabaseSync } from 'node:sqlite';
import type {
  InventoryConsumption,
  InventoryMaterial,
  InventoryReceipt,
  StockEntry,
} from '../../../shared/types';
import { getPour } from './pours';
import { OpsError, OpsErrorCodes } from '../errors';
import { writeAudit } from './audit';

function mapMaterial(row: Record<string, unknown>): InventoryMaterial {
  return { id: row['id'] as number, name: row['name'] as string, unit: row['unit'] as string };
}

function mapReceipt(row: Record<string, unknown>): InventoryReceipt {
  return {
    id: row['id'] as number,
    materialId: row['material_id'] as number,
    supplier: row['supplier'] as string,
    receivedDate: row['received_date'] as string,
    qtyKg: row['qty_kg'] as number,
    costCents: row['cost_cents'] as number,
    notes: row['notes'] as string | null,
    createdAt: row['created_at'] as string,
  };
}

function mapConsumption(row: Record<string, unknown>): InventoryConsumption {
  return {
    id: row['id'] as number,
    pourId: row['pour_id'] as number,
    materialId: row['material_id'] as number,
    qtyKg: row['qty_kg'] as number,
    createdAt: row['created_at'] as string,
  };
}

export function listMaterials(db: DatabaseSync): InventoryMaterial[] {
  const rows = db.prepare('SELECT * FROM inventory_materials ORDER BY name').all() as Record<string, unknown>[];
  return rows.map(mapMaterial);
}

export function addMaterial(db: DatabaseSync, name: string, unit: string): InventoryMaterial {
  const result = db.prepare('INSERT INTO inventory_materials (name, unit) VALUES (?, ?)').run(name, unit);
  const id = Number(result.lastInsertRowid);
  const row = db.prepare('SELECT * FROM inventory_materials WHERE id = ?').get(id) as Record<string, unknown>;
  const material = mapMaterial(row);
  writeAudit(db, { entityType: 'inventory_material', entityId: id, action: 'created', after: material });
  return material;
}

export function listReceipts(db: DatabaseSync, materialId?: number): InventoryReceipt[] {
  const rows =
    materialId === undefined
      ? (db.prepare('SELECT * FROM inventory_receipts ORDER BY received_date DESC, id DESC').all() as Record<string, unknown>[])
      : (db.prepare('SELECT * FROM inventory_receipts WHERE material_id = ? ORDER BY received_date DESC, id DESC').all(materialId) as Record<string, unknown>[]);
  return rows.map(mapReceipt);
}

export function addReceipt(
  db: DatabaseSync,
  input: { materialId: number; supplier: string; receivedDate: string; qtyKg: number; costCents: number; notes: string | null },
): InventoryReceipt {
  const now = new Date().toISOString();
  const result = db
    .prepare(
      `INSERT INTO inventory_receipts (material_id, supplier, received_date, qty_kg, cost_cents, notes, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
    )
    .run(input.materialId, input.supplier, input.receivedDate, input.qtyKg, input.costCents, input.notes, now);
  const id = Number(result.lastInsertRowid);
  const row = db.prepare('SELECT * FROM inventory_receipts WHERE id = ?').get(id) as Record<string, unknown>;
  const receipt = mapReceipt(row);
  writeAudit(db, { entityType: 'inventory_receipt', entityId: id, action: 'received', after: receipt });
  return receipt;
}

export function listConsumption(db: DatabaseSync, pourId?: number): InventoryConsumption[] {
  const rows =
    pourId === undefined
      ? (db.prepare('SELECT * FROM inventory_consumption ORDER BY id DESC').all() as Record<string, unknown>[])
      : (db.prepare('SELECT * FROM inventory_consumption WHERE pour_id = ? ORDER BY id').all(pourId) as Record<string, unknown>[]);
  return rows.map(mapConsumption);
}

/**
 * Record material consumed by a pour. Rejected when it would drive
 * stock-on-hand negative — receipt ↔ consumption consistency is enforced.
 */
export function addConsumption(
  db: DatabaseSync,
  input: { pourId: number; materialId: number; qtyKg: number },
): InventoryConsumption {
  const pour = getPour(db, input.pourId);
  if (!pour) throw new OpsError(OpsErrorCodes.NOT_FOUND, `Pour #${input.pourId} does not exist.`);
  const stock = getStock(db).find((s) => s.materialId === input.materialId);
  if (!stock) throw new OpsError(OpsErrorCodes.NOT_FOUND, `Material #${input.materialId} does not exist.`);
  if (input.qtyKg > stock.onHandKg) {
    throw new OpsError(
      OpsErrorCodes.INSUFFICIENT_STOCK,
      `Cannot consume ${input.qtyKg} ${stock.unit} of ${stock.name}: only ${stock.onHandKg} ${stock.unit} on hand. Record a receipt first.`,
    );
  }
  const now = new Date().toISOString();
  const result = db
    .prepare(
      `INSERT INTO inventory_consumption (pour_id, material_id, qty_kg, created_at)
       VALUES (?, ?, ?, ?)`,
    )
    .run(input.pourId, input.materialId, input.qtyKg, now);
  const id = Number(result.lastInsertRowid);
  const row = db.prepare('SELECT * FROM inventory_consumption WHERE id = ?').get(id) as Record<string, unknown>;
  const consumption = mapConsumption(row);
  writeAudit(db, { entityType: 'inventory_consumption', entityId: id, action: 'consumed', after: consumption });
  return consumption;
}

/** Current stock-on-hand for every material. */
export function getStock(db: DatabaseSync): StockEntry[] {
  const rows = db
    .prepare(
      `SELECT m.id AS material_id, m.name, m.unit,
              COALESCE((SELECT SUM(qty_kg) FROM inventory_receipts r WHERE r.material_id = m.id), 0) AS received_kg,
              COALESCE((SELECT SUM(qty_kg) FROM inventory_consumption c WHERE c.material_id = m.id), 0) AS consumed_kg
       FROM inventory_materials m
       ORDER BY m.name`,
    )
    .all() as Record<string, unknown>[];
  return rows.map((r) => ({
    materialId: r['material_id'] as number,
    name: r['name'] as string,
    unit: r['unit'] as string,
    receivedKg: r['received_kg'] as number,
    consumedKg: r['consumed_kg'] as number,
    onHandKg: (r['received_kg'] as number) - (r['consumed_kg'] as number),
  }));
}
