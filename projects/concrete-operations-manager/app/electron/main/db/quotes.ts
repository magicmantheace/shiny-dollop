/**
 * Quotes. State machine: draft → issued → superseded.
 *
 * Issued quotes are immutable: they are never updated in place. A revision
 * creates a NEW quote row (version + 1) as a draft; issuing that draft
 * marks the previous issued quote superseded. Every transition is audited.
 *
 * Quotes are computed from the pours' QUOTED (estimate) volumes.
 */
import type { DatabaseSync } from 'node:sqlite';
import type { Customer, Job, Quote, QuoteParamsSnapshot } from '../../../shared/types';
import type { PricingParams, PricingVolume } from '../../../shared/pricing';
import { computeTotals, snapshotParams } from '../../../shared/pricing';
import { getCustomer } from './customers';
import { getJob } from './jobs';
import { listPoursByJob } from './pours';
import { getIntSetting, getSetting } from './settings';
import { listEnabledTaxRates } from './taxrates';
import { OpsError, OpsErrorCodes } from '../errors';
import { writeAudit } from './audit';

export interface PricingOverrides {
  rateOverrideCentsPerM3?: number | null;
  smallLoadChargeOverrideCents?: number | null;
}

function mapQuote(row: Record<string, unknown>): Quote {
  return {
    id: row['id'] as number,
    jobId: row['job_id'] as number,
    version: row['version'] as number,
    status: row['status'] as Quote['status'],
    lines: JSON.parse(row['lines_json'] as string),
    subtotalCents: row['subtotal_cents'] as number,
    taxLines: JSON.parse(row['tax_lines_json'] as string),
    totalCents: row['total_cents'] as number,
    taxExemptApplied: (row['tax_exempt_applied'] as number) === 1,
    params: JSON.parse(row['params_json'] as string) as QuoteParamsSnapshot,
    notes: row['notes'] as string | null,
    createdAt: row['created_at'] as string,
    issuedAt: row['issued_at'] as string | null,
  };
}

/** Resolve effective pricing: manual overrides → customer defaults → app settings. */
export function resolvePricingParams(
  db: DatabaseSync,
  customer: Customer,
  job: Job,
  overrides: PricingOverrides = {},
): PricingParams {
  const rate = overrides.rateOverrideCentsPerM3 ?? customer.concreteRateCentsPerM3;
  const smallLoadCharge =
    overrides.smallLoadChargeOverrideCents ?? customer.smallLoadChargeCents;
  const deliveryMode =
    customer.deliveryFeeMode ?? (getSetting(db, 'default_delivery_mode') as 'flat' | 'mileage');
  return {
    concreteRateCentsPerM3: rate ?? getIntSetting(db, 'default_concrete_rate_cents_per_m3'),
    smallLoadThresholdLiters: getIntSetting(db, 'small_load_threshold_liters'),
    smallLoadChargeCents: smallLoadCharge ?? getIntSetting(db, 'default_small_load_charge_cents'),
    smallLoadApplied: true,
    deliveryMode,
    deliveryFlatCents: customer.deliveryFlatCents ?? getIntSetting(db, 'default_delivery_flat_cents'),
    deliveryPerKmCents:
      customer.deliveryPerKmCents ?? getIntSetting(db, 'default_delivery_per_km_cents'),
    distanceTenthsKm: job.distanceTenthsKm,
    taxes: listEnabledTaxRates(db).map((t) => ({ name: t.name, rateBps: t.rateBps })),
    taxExempt: customer.taxExempt,
  };
}

function insertQuote(
  db: DatabaseSync,
  jobId: number,
  version: number,
  volumes: PricingVolume[],
  params: PricingParams,
  notes: string | null,
): Quote {
  const totals = computeTotals(volumes, params);
  const snapshot = snapshotParams(volumes, params, false);
  const now = new Date().toISOString();
  const result = db
    .prepare(
      `INSERT INTO quotes
         (job_id, version, status, lines_json, subtotal_cents, tax_lines_json,
          total_cents, tax_exempt_applied, params_json, notes, created_at, issued_at)
       VALUES (?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, NULL)`,
    )
    .run(
      jobId,
      version,
      JSON.stringify(totals.lines),
      totals.subtotalCents,
      JSON.stringify(totals.taxLines),
      totals.totalCents,
      totals.taxExemptApplied ? 1 : 0,
      JSON.stringify(snapshot),
      notes,
      now,
    );
  const id = Number(result.lastInsertRowid);
  return getQuote(db, id) as Quote;
}

function nextVersion(db: DatabaseSync, jobId: number): number {
  const row = db.prepare('SELECT COALESCE(MAX(version), 0) AS v FROM quotes WHERE job_id = ?').get(jobId) as {
    v: number;
  };
  return row.v + 1;
}

export function listQuotesByJob(db: DatabaseSync, jobId: number): Quote[] {
  const rows = db.prepare('SELECT * FROM quotes WHERE job_id = ? ORDER BY version').all(jobId) as Record<
    string,
    unknown
  >[];
  return rows.map(mapQuote);
}

export function getQuote(db: DatabaseSync, id: number): Quote | null {
  const row = db.prepare('SELECT * FROM quotes WHERE id = ?').get(id) as
    | Record<string, unknown>
    | undefined;
  return row ? mapQuote(row) : null;
}

function requireJobAndCustomer(db: DatabaseSync, jobId: number): { job: Job; customer: Customer } {
  const job = getJob(db, jobId);
  if (!job) throw new OpsError(OpsErrorCodes.NOT_FOUND, `Job #${jobId} does not exist.`);
  const customer = getCustomer(db, job.customerId);
  if (!customer) throw new OpsError(OpsErrorCodes.NOT_FOUND, `Customer #${job.customerId} does not exist.`);
  return { job, customer };
}

/** Create a draft quote from the pours' quoted (estimate) volumes. */
export function createQuote(db: DatabaseSync, jobId: number, notes: string | null): Quote {
  const { job, customer } = requireJobAndCustomer(db, jobId);
  const pours = listPoursByJob(db, jobId);
  if (pours.length === 0) {
    throw new OpsError(OpsErrorCodes.INVALID_STATE, `Job #${jobId} has no pours; add a pour before quoting.`);
  }
  const volumes: PricingVolume[] = pours.map((p) => ({
    pourId: p.id,
    mixDesignId: p.mixDesignId,
    liters: p.quotedLiters,
  }));
  const params = resolvePricingParams(db, customer, job);
  const quote = insertQuote(db, jobId, nextVersion(db, jobId), volumes, params, notes);
  writeAudit(db, { entityType: 'quote', entityId: quote.id, action: 'draft_created', after: quote });
  return quote;
}

/**
 * Update a DRAFT quote: notes and/or manual price overrides. Recomputes the
 * totals from the current quoted volumes. Overrides are audited with
 * before → after values.
 */
export function updateDraft(
  db: DatabaseSync,
  id: number,
  patch: { notes?: string | null; rateOverrideCentsPerM3?: number | null; smallLoadChargeOverrideCents?: number | null },
): Quote {
  const before = getQuote(db, id);
  if (!before) throw new OpsError(OpsErrorCodes.NOT_FOUND, `Quote #${id} does not exist.`);
  if (before.status !== 'draft') {
    throw new OpsError(
      OpsErrorCodes.INVALID_STATE,
      `Quote #${id} is ${before.status}; only drafts can be changed. Revise it to create a new draft.`,
    );
  }
  const { job, customer } = requireJobAndCustomer(db, before.jobId);
  const pours = listPoursByJob(db, before.jobId);
  const volumes: PricingVolume[] = pours.map((p) => ({
    pourId: p.id,
    mixDesignId: p.mixDesignId,
    liters: p.quotedLiters,
  }));
  const params = resolvePricingParams(db, customer, job, {
    rateOverrideCentsPerM3: patch.rateOverrideCentsPerM3 ?? null,
    smallLoadChargeOverrideCents: patch.smallLoadChargeOverrideCents ?? null,
  });
  const totals = computeTotals(volumes, params);
  const snapshot = snapshotParams(volumes, params, false);
  const notesChanged = patch.notes !== undefined;
  db.prepare(
    `UPDATE quotes SET
       lines_json = ?, subtotal_cents = ?, tax_lines_json = ?, total_cents = ?,
       tax_exempt_applied = ?, params_json = ?,
       notes = CASE WHEN ? THEN ? ELSE notes END
     WHERE id = ?`,
  ).run(
    JSON.stringify(totals.lines),
    totals.subtotalCents,
    JSON.stringify(totals.taxLines),
    totals.totalCents,
    totals.taxExemptApplied ? 1 : 0,
    JSON.stringify(snapshot),
    notesChanged ? 1 : 0,
    patch.notes ?? null,
    id,
  );
  const after = getQuote(db, id) as Quote;
  writeAudit(db, {
    entityType: 'quote',
    entityId: id,
    action:
      patch.rateOverrideCentsPerM3 !== undefined || patch.smallLoadChargeOverrideCents !== undefined
        ? 'draft_price_overridden'
        : 'draft_updated',
    before: { params: before.params, notes: before.notes },
    after: { params: after.params, notes: after.notes },
  });
  return after;
}

/** Issue a draft. The previously issued quote for the job becomes superseded. */
export function issueQuote(db: DatabaseSync, id: number): Quote {
  const quote = getQuote(db, id);
  if (!quote) throw new OpsError(OpsErrorCodes.NOT_FOUND, `Quote #${id} does not exist.`);
  if (quote.status !== 'draft') {
    throw new OpsError(OpsErrorCodes.INVALID_STATE, `Quote #${id} is ${quote.status}; only drafts can be issued.`);
  }
  const now = new Date().toISOString();
  db.prepare(`UPDATE quotes SET status = 'superseded' WHERE job_id = ? AND status = 'issued'`).run(quote.jobId);
  db.prepare(`UPDATE quotes SET status = 'issued', issued_at = ? WHERE id = ?`).run(now, id);
  const after = getQuote(db, id) as Quote;
  writeAudit(db, { entityType: 'quote', entityId: id, action: 'issued', before: { status: 'draft' }, after });
  return after;
}

/**
 * Start a revision of an issued quote: creates a NEW draft (version + 1)
 * carrying the issued quote's pricing basis. The issued quote is untouched
 * until the new draft is issued.
 */
export function reviseQuote(db: DatabaseSync, id: number): Quote {
  const source = getQuote(db, id);
  if (!source) throw new OpsError(OpsErrorCodes.NOT_FOUND, `Quote #${id} does not exist.`);
  if (source.status !== 'issued') {
    throw new OpsError(
      OpsErrorCodes.INVALID_STATE,
      `Quote #${id} is ${source.status}; only an issued quote can be revised.`,
    );
  }
  const { job, customer } = requireJobAndCustomer(db, source.jobId);
  const pours = listPoursByJob(db, source.jobId);
  const volumes: PricingVolume[] = pours.map((p) => ({
    pourId: p.id,
    mixDesignId: p.mixDesignId,
    liters: p.quotedLiters,
  }));
  // Carry the issued quote's pricing basis forward; recompute from live pours.
  const params: PricingParams = {
    concreteRateCentsPerM3: source.params.concreteRateCentsPerM3,
    smallLoadThresholdLiters: source.params.smallLoadThresholdLiters,
    smallLoadChargeCents: source.params.smallLoadChargeCents,
    smallLoadApplied: source.params.smallLoadApplied,
    deliveryMode: source.params.deliveryMode,
    deliveryFlatCents: source.params.deliveryFlatCents,
    deliveryPerKmCents: source.params.deliveryPerKmCents,
    distanceTenthsKm: job.distanceTenthsKm,
    taxes: source.params.taxes,
    taxExempt: customer.taxExempt,
  };
  const draft = insertQuote(db, source.jobId, nextVersion(db, source.jobId), volumes, params, source.notes);
  writeAudit(db, {
    entityType: 'quote',
    entityId: draft.id,
    action: 'revision_started',
    before: { sourceQuoteId: source.id, sourceVersion: source.version },
    after: draft,
  });
  return draft;
}

/** Delete a draft quote. Issued/superseded quotes are never deleted. */
export function deleteDraft(db: DatabaseSync, id: number): boolean {
  const quote = getQuote(db, id);
  if (!quote) return false;
  if (quote.status !== 'draft') {
    throw new OpsError(
      OpsErrorCodes.INVALID_STATE,
      `Quote #${id} is ${quote.status}; issued history cannot be deleted.`,
    );
  }
  db.prepare('DELETE FROM quotes WHERE id = ?').run(id);
  writeAudit(db, { entityType: 'quote', entityId: id, action: 'draft_deleted', before: quote });
  return true;
}
