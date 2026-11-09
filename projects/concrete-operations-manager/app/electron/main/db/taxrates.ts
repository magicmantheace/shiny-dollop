/** Tax-rate CRUD (Canadian GST 5% seeded by default; Alberta). */
import type { DatabaseSync } from 'node:sqlite';
import type { TaxRate } from '../../../shared/types';
import { writeAudit } from './audit';

function mapTaxRate(row: Record<string, unknown>): TaxRate {
  return {
    id: row['id'] as number,
    name: row['name'] as string,
    rateBps: row['rate_bps'] as number,
    enabled: (row['enabled'] as number) === 1,
  };
}

export function listTaxRates(db: DatabaseSync): TaxRate[] {
  const rows = db.prepare('SELECT * FROM tax_rates ORDER BY name').all() as Record<string, unknown>[];
  return rows.map(mapTaxRate);
}

export function listEnabledTaxRates(db: DatabaseSync): TaxRate[] {
  return listTaxRates(db).filter((t) => t.enabled);
}

export function addTaxRate(db: DatabaseSync, name: string, rateBps: number, enabled: boolean): TaxRate {
  const result = db
    .prepare('INSERT INTO tax_rates (name, rate_bps, enabled) VALUES (?, ?, ?)')
    .run(name, rateBps, enabled ? 1 : 0);
  const id = Number(result.lastInsertRowid);
  const row = db.prepare('SELECT * FROM tax_rates WHERE id = ?').get(id) as Record<string, unknown>;
  const rate = mapTaxRate(row);
  writeAudit(db, { entityType: 'tax_rate', entityId: id, action: 'created', after: rate });
  return rate;
}

export function updateTaxRate(
  db: DatabaseSync,
  id: number,
  patch: { name?: string; rateBps?: number; enabled?: boolean },
): TaxRate | null {
  const before = db.prepare('SELECT * FROM tax_rates WHERE id = ?').get(id) as
    | Record<string, unknown>
    | undefined;
  if (!before) return null;
  db.prepare(
    `UPDATE tax_rates SET
       name = COALESCE(?, name),
       rate_bps = COALESCE(?, rate_bps),
       enabled = COALESCE(?, enabled)
     WHERE id = ?`,
  ).run(
    patch.name ?? null,
    patch.rateBps ?? null,
    patch.enabled === undefined ? null : patch.enabled ? 1 : 0,
    id,
  );
  const after = db.prepare('SELECT * FROM tax_rates WHERE id = ?').get(id) as Record<string, unknown>;
  const rate = mapTaxRate(after);
  writeAudit(db, { entityType: 'tax_rate', entityId: id, action: 'updated', before: mapTaxRate(before), after: rate });
  return rate;
}

export function removeTaxRate(db: DatabaseSync, id: number): boolean {
  const before = db.prepare('SELECT * FROM tax_rates WHERE id = ?').get(id) as
    | Record<string, unknown>
    | undefined;
  if (!before) return false;
  // Issued quotes snapshot their tax lines, so history is safe.
  db.prepare('DELETE FROM tax_rates WHERE id = ?').run(id);
  writeAudit(db, { entityType: 'tax_rate', entityId: id, action: 'deleted', before: mapTaxRate(before) });
  return true;
}
