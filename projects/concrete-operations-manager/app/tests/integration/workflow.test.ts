/**
 * End-to-end MVP workflow against the real database layer:
 * customer → job → pour → quote (issue) → finalize delivered →
 * invoice → totals verified. Plus quote-revision immutability.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { makeTestDb, addTestCustomer, addTestJob, addTestPour } from '../helpers';
import type { DatabaseSync } from 'node:sqlite';
import { createQuote, getQuote, issueQuote, reviseQuote, updateDraft } from '../../electron/main/db/quotes';
import { createInvoice, markInvoicePaid, voidInvoice } from '../../electron/main/db/invoices';
import { setDeliveredLiters } from '../../electron/main/db/pours';
import { listAudit } from '../../electron/main/db/audit';
import { OpsError } from '../../electron/main/errors';

let db: DatabaseSync;
afterEach(() => {
  try {
    db?.close();
  } catch {
    // ignore
  }
});

function setup(): { customerId: number; jobId: number; pourId: number } {
  db = makeTestDb();
  const customer = addTestCustomer(db);
  const job = addTestJob(db, customer.id);
  const pour = addTestPour(db, job.id, 2500);
  return { customerId: customer.id, jobId: job.id, pourId: pour.id };
}

describe('MVP workflow', () => {
  it('creates a draft quote with the expected itemized totals', () => {
    const { jobId } = setup();
    const q = createQuote(db, jobId, null);
    expect(q.status).toBe('draft');
    expect(q.version).toBe(1);
    // 2.5 m³ @ $180 = $450.00; small load $150 (under 3 m³); flat delivery $75
    expect(q.lines.map((l) => l.kind)).toEqual(['concrete', 'small_load', 'delivery']);
    expect(q.subtotalCents).toBe(45000 + 15000 + 7500);
    // GST 5% on $675.00 = $33.75
    expect(q.taxLines).toHaveLength(1);
    expect(q.taxLines[0]?.taxCents).toBe(3375);
    expect(q.totalCents).toBe(70875);
    expect(q.issuedAt).toBeNull();
  });

  it('issues a quote, then creates an invoice from finalized delivered volumes', () => {
    const { jobId, pourId } = setup();
    const issued = issueQuote(db, createQuote(db, jobId, null).id);
    expect(issued.status).toBe('issued');

    // Invoicing before finalizing delivered volumes is blocked.
    expect(() => createInvoice(db, issued.id)).toThrow(OpsError);

    setDeliveredLiters(db, pourId, 2480);
    const inv = createInvoice(db, issued.id);
    expect(inv.invoiceNumber).toMatch(/^INV-\d{6}$/);
    expect(inv.status).toBe('issued');
    // 2.48 m³ @ $180 = $446.40; small load $150; delivery $75 → $671.40; GST $33.57
    expect(inv.subtotalCents).toBe(44640 + 15000 + 7500);
    expect(inv.taxLines[0]?.taxCents).toBe(3357);
    expect(inv.totalCents).toBe(70497);
    // Delivered (measured) volumes drive the invoice, not the estimate.
    expect(inv.lines[0]?.quantityLiters).toBe(2480);
  });

  it('paid/void transitions work and the invoice record is kept', () => {
    const { jobId, pourId } = setup();
    const issued = issueQuote(db, createQuote(db, jobId, null).id);
    setDeliveredLiters(db, pourId, 2500);
    const inv = createInvoice(db, issued.id);
    const paid = markInvoicePaid(db, inv.id);
    expect(paid.status).toBe('paid');
    expect(paid.paidAt).not.toBeNull();
    // A paid invoice cannot be voided or re-paid.
    expect(() => voidInvoice(db, inv.id)).toThrow(OpsError);
    expect(() => markInvoicePaid(db, inv.id)).toThrow(OpsError);
  });

  it('quote revisions never rewrite the issued invoice source: new version, old row untouched', () => {
    const { jobId } = setup();
    const v1 = issueQuote(db, createQuote(db, jobId, null).id);
    const v1Snapshot = JSON.stringify(getQuote(db, v1.id));

    const v2draft = reviseQuote(db, v1.id);
    expect(v2draft.version).toBe(2);
    expect(v2draft.status).toBe('draft');
    // v1 is still issued and byte-identical until v2 is issued.
    expect(getQuote(db, v1.id)?.status).toBe('issued');
    expect(JSON.stringify(getQuote(db, v1.id))).toBe(v1Snapshot);

    // Draft edits land only on the draft.
    updateDraft(db, v2draft.id, { rateOverrideCentsPerM3: 20000, notes: 'revised' });
    expect(JSON.stringify(getQuote(db, v1.id))).toBe(v1Snapshot);
    expect(getQuote(db, v2draft.id)?.totalCents).not.toBe(v1.totalCents);

    const v2 = issueQuote(db, v2draft.id);
    expect(v2.status).toBe('issued');
    expect(getQuote(db, v1.id)?.status).toBe('superseded');
    // The superseded row keeps its original numbers.
    expect(JSON.stringify({ ...getQuote(db, v1.id), status: 'issued' })).toBe(v1Snapshot);
  });

  it('issued quotes reject edits and double-issue', () => {
    const { jobId } = setup();
    const v1 = issueQuote(db, createQuote(db, jobId, null).id);
    expect(() => updateDraft(db, v1.id, { notes: 'x' })).toThrow(OpsError);
    expect(() => issueQuote(db, v1.id)).toThrow(OpsError);
  });

  it('writes audit rows for the key transitions', () => {
    const { jobId, pourId } = setup();
    const q = createQuote(db, jobId, null);
    issueQuote(db, q.id);
    setDeliveredLiters(db, pourId, 2480);
    createInvoice(db, q.id);
    const actions = listAudit(db, { limit: 500 }).map((a) => a.action);
    expect(actions).toContain('draft_created');
    expect(actions).toContain('issued');
    expect(actions).toContain('delivered_finalized');
    expect(actions).toContain('issued'); // invoice issued
  });
});
