import { afterEach, describe, expect, it } from 'vitest';
import { makeTestDb, addTestCustomer, addTestJob, addTestPour } from '../helpers';
import type { DatabaseSync } from 'node:sqlite';
import { renderInvoicePdf } from '../../electron/main/export/pdf';
import { createQuote, issueQuote } from '../../electron/main/db/quotes';
import { createInvoice } from '../../electron/main/db/invoices';
import { setDeliveredLiters } from '../../electron/main/db/pours';

let db: DatabaseSync;
afterEach(() => {
  try {
    db?.close();
  } catch {
    // ignore
  }
});

describe('invoice PDF export', () => {
  it('renders a non-empty PDF for an issued invoice', async () => {
    db = makeTestDb();
    const customer = addTestCustomer(db, 'PDF Test Customer');
    const job = addTestJob(db, customer.id);
    const pour = addTestPour(db, job.id, 2500);
    const quote = issueQuote(db, createQuote(db, job.id, null).id);
    setDeliveredLiters(db, pour.id, 2480);
    const invoice = createInvoice(db, quote.id);

    const { buffer, fileName } = await renderInvoicePdf(db, invoice.id);
    expect(fileName).toBe(`${invoice.invoiceNumber}.pdf`);
    expect(buffer.length).toBeGreaterThan(1000);
    // PDF magic bytes.
    expect(buffer.subarray(0, 5).toString('ascii')).toBe('%PDF-');
  });

  it('fails clearly for a missing invoice', async () => {
    db = makeTestDb();
    await expect(renderInvoicePdf(db, 9999)).rejects.toThrow(/does not exist/);
  });
});
