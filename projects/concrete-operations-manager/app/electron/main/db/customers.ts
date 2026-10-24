/** Customer CRUD. Pricing overrides are audited on update. */
import type { DatabaseSync } from 'node:sqlite';
import type { Customer } from '../../../shared/types';
import type { CustomerAddInput, CustomerUpdateInput } from '../../../shared/schemas';
import { OpsError, OpsErrorCodes } from '../errors';
import { writeAudit } from './audit';

const PRICING_FIELDS = [
  'concreteRateCentsPerM3',
  'smallLoadChargeCents',
  'deliveryFeeMode',
  'deliveryFlatCents',
  'deliveryPerKmCents',
  'taxExempt',
] as const;

function mapCustomer(row: Record<string, unknown>): Customer {
  return {
    id: row['id'] as number,
    name: row['name'] as string,
    contactName: row['contact_name'] as string | null,
    phone: row['phone'] as string | null,
    email: row['email'] as string | null,
    address: row['address'] as string | null,
    taxExempt: (row['tax_exempt'] as number) === 1,
    concreteRateCentsPerM3: row['concrete_rate_cents_per_m3'] as number | null,
    smallLoadChargeCents: row['small_load_charge_cents'] as number | null,
    deliveryFeeMode: row['delivery_fee_mode'] as 'flat' | 'mileage' | null,
    deliveryFlatCents: row['delivery_flat_cents'] as number | null,
    deliveryPerKmCents: row['delivery_per_km_cents'] as number | null,
    notes: row['notes'] as string | null,
    createdAt: row['created_at'] as string,
    updatedAt: row['updated_at'] as string,
  };
}

export function listCustomers(db: DatabaseSync): Customer[] {
  const rows = db.prepare('SELECT * FROM customers ORDER BY name COLLATE NOCASE').all() as Record<
    string,
    unknown
  >[];
  return rows.map(mapCustomer);
}

export function getCustomer(db: DatabaseSync, id: number): Customer | null {
  const row = db.prepare('SELECT * FROM customers WHERE id = ?').get(id) as
    | Record<string, unknown>
    | undefined;
  return row ? mapCustomer(row) : null;
}

export function addCustomer(db: DatabaseSync, input: CustomerAddInput): Customer {
  const now = new Date().toISOString();
  const result = db
    .prepare(
      `INSERT INTO customers
         (name, contact_name, phone, email, address, tax_exempt,
          concrete_rate_cents_per_m3, small_load_charge_cents, delivery_fee_mode,
          delivery_flat_cents, delivery_per_km_cents, notes, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    )
    .run(
      input.name,
      input.contactName ?? null,
      input.phone ?? null,
      input.email ?? null,
      input.address ?? null,
      input.taxExempt ? 1 : 0,
      input.concreteRateCentsPerM3 ?? null,
      input.smallLoadChargeCents ?? null,
      input.deliveryFeeMode ?? null,
      input.deliveryFlatCents ?? null,
      input.deliveryPerKmCents ?? null,
      input.notes ?? null,
      now,
      now,
    );
  const id = Number(result.lastInsertRowid);
  const customer = getCustomer(db, id) as Customer;
  writeAudit(db, { entityType: 'customer', entityId: id, action: 'created', after: customer });
  return customer;
}

export function updateCustomer(db: DatabaseSync, input: CustomerUpdateInput): Customer | null {
  const before = getCustomer(db, input.id);
  if (!before) return null;
  const now = new Date().toISOString();
  db.prepare(
    `UPDATE customers SET
       name = COALESCE(?, name),
       contact_name = CASE WHEN ? IS NOT NULL THEN ? ELSE contact_name END,
       phone = CASE WHEN ? IS NOT NULL THEN ? ELSE phone END,
       email = CASE WHEN ? IS NOT NULL THEN ? ELSE email END,
       address = CASE WHEN ? IS NOT NULL THEN ? ELSE address END,
       tax_exempt = COALESCE(?, tax_exempt),
       concrete_rate_cents_per_m3 = CASE WHEN ? IS NOT NULL THEN ? ELSE concrete_rate_cents_per_m3 END,
       small_load_charge_cents = CASE WHEN ? IS NOT NULL THEN ? ELSE small_load_charge_cents END,
       delivery_fee_mode = CASE WHEN ? IS NOT NULL THEN ? ELSE delivery_fee_mode END,
       delivery_flat_cents = CASE WHEN ? IS NOT NULL THEN ? ELSE delivery_flat_cents END,
       delivery_per_km_cents = CASE WHEN ? IS NOT NULL THEN ? ELSE delivery_per_km_cents END,
       notes = CASE WHEN ? IS NOT NULL THEN ? ELSE notes END,
       updated_at = ?
     WHERE id = ?`,
  ).run(
    input.name ?? null,
    input.contactName === undefined ? 1 : 0, input.contactName ?? null,
    input.phone === undefined ? 1 : 0, input.phone ?? null,
    input.email === undefined ? 1 : 0, input.email ?? null,
    input.address === undefined ? 1 : 0, input.address ?? null,
    input.taxExempt === undefined ? null : input.taxExempt ? 1 : 0,
    input.concreteRateCentsPerM3 === undefined ? 1 : 0, input.concreteRateCentsPerM3 ?? null,
    input.smallLoadChargeCents === undefined ? 1 : 0, input.smallLoadChargeCents ?? null,
    input.deliveryFeeMode === undefined ? 1 : 0, input.deliveryFeeMode ?? null,
    input.deliveryFlatCents === undefined ? 1 : 0, input.deliveryFlatCents ?? null,
    input.deliveryPerKmCents === undefined ? 1 : 0, input.deliveryPerKmCents ?? null,
    input.notes === undefined ? 1 : 0, input.notes ?? null,
    now,
    input.id,
  );
  const after = getCustomer(db, input.id) as Customer;
  const pricingChanged = PRICING_FIELDS.some(
    (f) => input[f] !== undefined && JSON.stringify(input[f]) !== JSON.stringify(before[f]),
  );
  writeAudit(db, {
    entityType: 'customer',
    entityId: input.id,
    action: pricingChanged ? 'pricing_updated' : 'updated',
    before,
    after,
  });
  return after;
}

/** Customers with jobs cannot be deleted (history must survive). */
export function removeCustomer(db: DatabaseSync, id: number): boolean {
  const customer = getCustomer(db, id);
  if (!customer) return false;
  const jobCount = db.prepare('SELECT COUNT(*) AS c FROM jobs WHERE customer_id = ?').get(id) as {
    c: number;
  };
  if (jobCount.c > 0) {
    throw new OpsError(
      OpsErrorCodes.REFERENCED,
      `Customer #${id} has ${jobCount.c} job(s) on record and cannot be deleted. History is preserved.`,
    );
  }
  db.prepare('DELETE FROM customers WHERE id = ?').run(id);
  writeAudit(db, { entityType: 'customer', entityId: id, action: 'deleted', before: customer });
  return true;
}
