/**
 * Invoices. State machine: issued → paid / voided.
 *
 * An invoice is IMMUTABLE once issued and is always computed from the
 * pours' FINALIZED delivered (measured) volumes — never from estimates.
 * Corrections are new documents (void + re-invoice), never edits.
 */
import type { DatabaseSync } from 'node:sqlite';
import type { Invoice } from '../../../shared/types';
import { computeTotals } from '../../../shared/pricing';
import type { PricingParams, PricingVolume } from '../../../shared/pricing';
import { getQuote } from './quotes';
import { listPoursByJob } from './pours';
import { OpsError, OpsErrorCodes } from '../errors';
import { writeAudit } from './audit';

function mapInvoice(row: Record<string, unknown>): Invoice {
  return {
    id: row['id'] as number,
    quoteId: row['quote_id'] as number,
    invoiceNumber: row['invoice_number'] as string,
    status: row['status'] as Invoice['status'],
    lines: JSON.parse(row['lines_json'] as string),
    subtotalCents: row['subtotal_cents'] as number,
    taxLines: JSON.parse(row['tax_lines_json'] as string),
    totalCents: row['total_cents'] as number,
    taxExemptApplied: (row['tax_exempt_applied'] as number) === 1,
    createdAt: row['created_at'] as string,
    paidAt: row['paid_at'] as string | null,
    voidedAt: row['voided_at'] as string | null,
  };
}

export function listInvoices(db: DatabaseSync): Invoice[] {
  const rows = db.prepare('SELECT * FROM invoices ORDER BY id DESC').all() as Record<string, unknown>[];
  return rows.map(mapInvoice);
}

export function getInvoice(db: DatabaseSync, id: number): Invoice | null {
  const row = db.prepare('SELECT * FROM invoices WHERE id = ?').get(id) as
    | Record<string, unknown>
    | undefined;
  return row ? mapInvoice(row) : null;
}

/**
 * Generate an invoice from an issued quote. Requires every pour on the job
 * to have its delivered (measured) volume finalized.
 */
export function createInvoice(db: DatabaseSync, quoteId: number): Invoice {
  const quote = getQuote(db, quoteId);
  if (!quote) throw new OpsError(OpsErrorCodes.NOT_FOUND, `Quote #${quoteId} does not exist.`);
  if (quote.status !== 'issued') {
    throw new OpsError(
      OpsErrorCodes.INVALID_STATE,
      `Quote #${quoteId} is ${quote.status}; only an issued quote can be invoiced.`,
    );
  }
  const existing = db.prepare('SELECT id FROM invoices WHERE quote_id = ?').get(quoteId) as
    | { id: number }
    | undefined;
  if (existing) {
    throw new OpsError(
      OpsErrorCodes.INVALID_STATE,
      `Quote #${quoteId} already has invoice #${existing.id}; issued invoices are never regenerated.`,
    );
  }
  const pours = listPoursByJob(db, quote.jobId);
  const unfinalized = pours.filter((p) => p.deliveredLiters === null);
  if (pours.length === 0) {
    throw new OpsError(OpsErrorCodes.INVALID_STATE, `Job #${quote.jobId} has no pours to invoice.`);
  }
  if (unfinalized.length > 0) {
    throw new OpsError(
      OpsErrorCodes.INVALID_STATE,
      `${unfinalized.length} pour(s) have no finalized delivered volume. Finalize every pour before invoicing.`,
    );
  }
  const volumes: PricingVolume[] = pours.map((p) => ({
    pourId: p.id,
    mixDesignId: p.mixDesignId,
    liters: p.deliveredLiters as number,
  }));
  const qp = quote.params;
  const params: PricingParams = {
    concreteRateCentsPerM3: qp.concreteRateCentsPerM3,
    smallLoadThresholdLiters: qp.smallLoadThresholdLiters,
    smallLoadChargeCents: qp.smallLoadChargeCents,
    smallLoadApplied: qp.smallLoadApplied,
    deliveryMode: qp.deliveryMode,
    deliveryFlatCents: qp.deliveryFlatCents,
    deliveryPerKmCents: qp.deliveryPerKmCents,
    distanceTenthsKm: qp.distanceTenthsKm,
    taxes: qp.taxes,
    taxExempt: qp.taxExempt,
  };
  const totals = computeTotals(volumes, params);
  const now = new Date().toISOString();
  const result = db
    .prepare(
      `INSERT INTO invoices
         (quote_id, invoice_number, status, lines_json, subtotal_cents,
          tax_lines_json, total_cents, tax_exempt_applied, created_at, paid_at, voided_at)
       VALUES (?, ?, 'issued', ?, ?, ?, ?, ?, ?, NULL, NULL)`,
    )
    .run(
      quoteId,
      'TEMP',
      JSON.stringify(totals.lines),
      totals.subtotalCents,
      JSON.stringify(totals.taxLines),
      totals.totalCents,
      totals.taxExemptApplied ? 1 : 0,
      now,
    );
  const id = Number(result.lastInsertRowid);
  const invoiceNumber = `INV-${String(id).padStart(6, '0')}`;
  db.prepare('UPDATE invoices SET invoice_number = ? WHERE id = ?').run(invoiceNumber, id);
  const invoice = getInvoice(db, id) as Invoice;
  writeAudit(db, {
    entityType: 'invoice',
    entityId: id,
    action: 'issued',
    before: { quoteId },
    after: invoice,
  });
  return invoice;
}

export function markInvoicePaid(db: DatabaseSync, id: number): Invoice {
  const invoice = getInvoice(db, id);
  if (!invoice) throw new OpsError(OpsErrorCodes.NOT_FOUND, `Invoice #${id} does not exist.`);
  if (invoice.status !== 'issued') {
    throw new OpsError(OpsErrorCodes.INVALID_STATE, `Invoice ${invoice.invoiceNumber} is ${invoice.status}; only issued invoices can be marked paid.`);
  }
  const now = new Date().toISOString();
  db.prepare(`UPDATE invoices SET status = 'paid', paid_at = ? WHERE id = ?`).run(now, id);
  const after = getInvoice(db, id) as Invoice;
  writeAudit(db, { entityType: 'invoice', entityId: id, action: 'marked_paid', before: { status: 'issued' }, after });
  return after;
}

/** Void keeps the row (immutable history); corrections are new documents. */
export function voidInvoice(db: DatabaseSync, id: number): Invoice {
  const invoice = getInvoice(db, id);
  if (!invoice) throw new OpsError(OpsErrorCodes.NOT_FOUND, `Invoice #${id} does not exist.`);
  if (invoice.status !== 'issued') {
    throw new OpsError(OpsErrorCodes.INVALID_STATE, `Invoice ${invoice.invoiceNumber} is ${invoice.status}; only issued invoices can be voided.`);
  }
  const now = new Date().toISOString();
  db.prepare(`UPDATE invoices SET status = 'voided', voided_at = ? WHERE id = ?`).run(now, id);
  const after = getInvoice(db, id) as Invoice;
  writeAudit(db, { entityType: 'invoice', entityId: id, action: 'voided', before: { status: 'issued' }, after });
  return after;
}
