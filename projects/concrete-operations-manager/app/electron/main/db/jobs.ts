/** Job CRUD. */
import type { DatabaseSync } from 'node:sqlite';
import type { Job } from '../../../shared/types';
import type { JobAddInput, JobUpdateInput } from '../../../shared/schemas';
import { getCustomer } from './customers';
import { OpsError, OpsErrorCodes } from '../errors';
import { writeAudit } from './audit';

function mapJob(row: Record<string, unknown>): Job {
  return {
    id: row['id'] as number,
    customerId: row['customer_id'] as number,
    jobDate: row['job_date'] as string,
    deliveryLocation: row['delivery_location'] as string,
    poNumber: row['po_number'] as string | null,
    distanceTenthsKm: row['distance_tenths_km'] as number | null,
    status: row['status'] as Job['status'],
    notes: row['notes'] as string | null,
    createdAt: row['created_at'] as string,
  };
}

export function listJobs(db: DatabaseSync, customerId?: number): Job[] {
  const rows =
    customerId === undefined
      ? (db.prepare('SELECT * FROM jobs ORDER BY job_date DESC, id DESC').all() as Record<string, unknown>[])
      : (db.prepare('SELECT * FROM jobs WHERE customer_id = ? ORDER BY job_date DESC, id DESC').all(customerId) as Record<string, unknown>[]);
  return rows.map(mapJob);
}

export function getJob(db: DatabaseSync, id: number): Job | null {
  const row = db.prepare('SELECT * FROM jobs WHERE id = ?').get(id) as
    | Record<string, unknown>
    | undefined;
  return row ? mapJob(row) : null;
}

export function addJob(db: DatabaseSync, input: JobAddInput): Job {
  if (!getCustomer(db, input.customerId)) {
    throw new OpsError(OpsErrorCodes.NOT_FOUND, `Customer #${input.customerId} does not exist.`);
  }
  const now = new Date().toISOString();
  const result = db
    .prepare(
      `INSERT INTO jobs (customer_id, job_date, delivery_location, po_number, distance_tenths_km, status, notes, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    )
    .run(
      input.customerId,
      input.jobDate,
      input.deliveryLocation,
      input.poNumber ?? null,
      input.distanceTenthsKm ?? null,
      input.status ?? 'scheduled',
      input.notes ?? null,
      now,
    );
  const id = Number(result.lastInsertRowid);
  const job = getJob(db, id) as Job;
  writeAudit(db, { entityType: 'job', entityId: id, action: 'created', after: job });
  return job;
}

export function updateJob(db: DatabaseSync, input: JobUpdateInput): Job | null {
  const before = getJob(db, input.id);
  if (!before) return null;
  if (input.customerId !== undefined && !getCustomer(db, input.customerId)) {
    throw new OpsError(OpsErrorCodes.NOT_FOUND, `Customer #${input.customerId} does not exist.`);
  }
  // Nullable fields: same presence-flag pattern as db/customers.ts — the
  // flag is 1 only when the field was provided (explicit null included) and
  // the SQL tests the flag's VALUE, so omitted fields are preserved.
  db.prepare(
    `UPDATE jobs SET
       customer_id = COALESCE(?, customer_id),
       job_date = COALESCE(?, job_date),
       delivery_location = COALESCE(?, delivery_location),
       po_number = CASE WHEN ? THEN ? ELSE po_number END,
       distance_tenths_km = CASE WHEN ? THEN ? ELSE distance_tenths_km END,
       status = COALESCE(?, status),
       notes = CASE WHEN ? THEN ? ELSE notes END
     WHERE id = ?`,
  ).run(
    input.customerId ?? null,
    input.jobDate ?? null,
    input.deliveryLocation ?? null,
    input.poNumber === undefined ? 0 : 1, input.poNumber ?? null,
    input.distanceTenthsKm === undefined ? 0 : 1, input.distanceTenthsKm ?? null,
    input.status ?? null,
    input.notes === undefined ? 0 : 1, input.notes ?? null,
    input.id,
  );
  const after = getJob(db, input.id) as Job;
  writeAudit(db, { entityType: 'job', entityId: input.id, action: 'updated', before, after });
  return after;
}

/** Jobs with quotes/invoices cannot be deleted (issued history must survive). */
export function removeJob(db: DatabaseSync, id: number): boolean {
  const job = getJob(db, id);
  if (!job) return false;
  const quoteCount = db.prepare('SELECT COUNT(*) AS c FROM quotes WHERE job_id = ?').get(id) as {
    c: number;
  };
  if (quoteCount.c > 0) {
    throw new OpsError(
      OpsErrorCodes.REFERENCED,
      `Job #${id} has ${quoteCount.c} quote(s) on record and cannot be deleted. History is preserved.`,
    );
  }
  db.prepare('DELETE FROM jobs WHERE id = ?').run(id);
  writeAudit(db, { entityType: 'job', entityId: id, action: 'deleted', before: job });
  return true;
}
