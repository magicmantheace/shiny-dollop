/**
 * Regression tests for Codex finding (PR #5): partial customer/job updates
 * must preserve omitted fields while still allowing explicit nulls.
 *
 * The update SQL passed presence flags as 1/0 but tested them with
 * `CASE WHEN ? IS NOT NULL`, which is always true for 1/0 — so a name-only
 * customer update nulled the address and negotiated pricing, and a
 * status-only job update nulled the PO, distance and notes.
 */
import { afterEach, describe, expect, it } from 'vitest';
import type { DatabaseSync } from 'node:sqlite';
import { makeTestDb } from '../helpers';
import { addCustomer, getCustomer, updateCustomer } from '../../electron/main/db/customers';
import { addJob, getJob, updateJob } from '../../electron/main/db/jobs';

let db: DatabaseSync;
afterEach(() => {
  try {
    db?.close();
  } catch {
    // ignore
  }
});

function addFullCustomer() {
  return addCustomer(db, {
    name: 'Original Name',
    contactName: 'Original Contact',
    phone: '555-0100',
    email: 'orig@example.com',
    address: '123 Original Road',
    taxExempt: true,
    concreteRateCentsPerM3: 19000,
    smallLoadChargeCents: 14000,
    deliveryFeeMode: 'flat',
    deliveryFlatCents: 8000,
    deliveryPerKmCents: 250,
    notes: 'original notes',
  });
}

describe('partial customer updates', () => {
  it('a name-only update preserves every omitted field', () => {
    db = makeTestDb();
    const before = addFullCustomer();
    const after = updateCustomer(db, { id: before.id, name: 'Renamed' });
    expect(after?.name).toBe('Renamed');
    expect(after?.contactName).toBe(before.contactName);
    expect(after?.phone).toBe(before.phone);
    expect(after?.email).toBe(before.email);
    expect(after?.address).toBe(before.address);
    expect(after?.taxExempt).toBe(before.taxExempt);
    expect(after?.concreteRateCentsPerM3).toBe(before.concreteRateCentsPerM3);
    expect(after?.smallLoadChargeCents).toBe(before.smallLoadChargeCents);
    expect(after?.deliveryFeeMode).toBe(before.deliveryFeeMode);
    expect(after?.deliveryFlatCents).toBe(before.deliveryFlatCents);
    expect(after?.deliveryPerKmCents).toBe(before.deliveryPerKmCents);
    expect(after?.notes).toBe(before.notes);
    // And it is persisted, not just returned.
    expect(getCustomer(db, before.id)).toEqual(after);
  });

  it('an explicit null clears only that field', () => {
    db = makeTestDb();
    const before = addFullCustomer();
    const after = updateCustomer(db, { id: before.id, address: null, concreteRateCentsPerM3: null });
    expect(after?.address).toBeNull();
    expect(after?.concreteRateCentsPerM3).toBeNull();
    expect(after?.name).toBe(before.name);
    expect(after?.phone).toBe(before.phone);
    expect(after?.smallLoadChargeCents).toBe(before.smallLoadChargeCents);
    expect(after?.notes).toBe(before.notes);
  });

  it('an explicit value updates only that field', () => {
    db = makeTestDb();
    const before = addFullCustomer();
    const after = updateCustomer(db, { id: before.id, address: '456 New Road' });
    expect(after?.address).toBe('456 New Road');
    expect(after?.name).toBe(before.name);
    expect(after?.concreteRateCentsPerM3).toBe(before.concreteRateCentsPerM3);
  });
});

describe('partial job updates', () => {
  function addFullJob() {
    const customer = addFullCustomer();
    return addJob(db, {
      customerId: customer.id,
      jobDate: '2026-10-23',
      deliveryLocation: '1234 Test Road, Lethbridge AB',
      poNumber: 'PO-TEST-001',
      distanceTenthsKm: 185,
      status: 'scheduled',
      notes: 'job notes',
    });
  }

  it('a status-only update preserves the PO, distance and notes', () => {
    db = makeTestDb();
    const before = addFullJob();
    const after = updateJob(db, { id: before.id, status: 'completed' });
    expect(after?.status).toBe('completed');
    expect(after?.poNumber).toBe(before.poNumber);
    expect(after?.distanceTenthsKm).toBe(before.distanceTenthsKm);
    expect(after?.notes).toBe(before.notes);
    expect(after?.deliveryLocation).toBe(before.deliveryLocation);
    expect(getJob(db, before.id)).toEqual(after);
  });

  it('an explicit null clears only that field', () => {
    db = makeTestDb();
    const before = addFullJob();
    const after = updateJob(db, { id: before.id, poNumber: null });
    expect(after?.poNumber).toBeNull();
    expect(after?.distanceTenthsKm).toBe(before.distanceTenthsKm);
    expect(after?.notes).toBe(before.notes);
    expect(after?.status).toBe(before.status);
  });

  it('an explicit value updates only that field', () => {
    db = makeTestDb();
    const before = addFullJob();
    const after = updateJob(db, { id: before.id, distanceTenthsKm: 200 });
    expect(after?.distanceTenthsKm).toBe(200);
    expect(after?.poNumber).toBe(before.poNumber);
    expect(after?.notes).toBe(before.notes);
  });
});
