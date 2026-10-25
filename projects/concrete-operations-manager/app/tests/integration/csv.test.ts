import { afterEach, describe, expect, it } from 'vitest';
import { makeTestDb, addTestCustomer, addTestJob, addTestPour } from '../helpers';
import type { DatabaseSync } from 'node:sqlite';
import { customersCsv, invoicesCsv, jobsCsv, inventoryCsv } from '../../electron/main/export/csv';
import { addReceipt } from '../../electron/main/db/inventory';
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

describe('CSV exports', () => {
  it('exports customers, jobs, invoices and inventory with synthetic data', () => {
    db = makeTestDb();
    const customer = addTestCustomer(db, 'CSV Test Customer');
    const job = addTestJob(db, customer.id);
    const pour = addTestPour(db, job.id, 2500);
    const quote = issueQuote(db, createQuote(db, job.id, null).id);
    setDeliveredLiters(db, pour.id, 2500);
    createInvoice(db, quote.id);
    const cement = db.prepare("SELECT id FROM inventory_materials WHERE name = 'Portland cement'").get() as { id: number };
    addReceipt(db, { materialId: cement.id, supplier: 'Synthetic Supplies', receivedDate: '2026-10-23', qtyKg: 1000, costCents: 12000, notes: null });

    const customers = customersCsv(db);
    expect(customers).toContain('CSV Test Customer');
    expect(customers.split('\r\n')[0]).toContain('name');

    const jobs = jobsCsv(db);
    expect(jobs).toContain('1234 Test Road');

    const invoices = invoicesCsv(db);
    expect(invoices).toContain('INV-');
    expect(invoices).toContain('GST');

    const inventory = inventoryCsv(db);
    expect(inventory).toContain('Portland cement');
    expect(inventory).toContain('Synthetic Supplies');
  });

  it('escapes commas and quotes in CSV cells', () => {
    db = makeTestDb();
    addTestCustomer(db, 'Tricky, "Quoted" Customer');
    expect(customersCsv(db)).toContain('"Tricky, ""Quoted"" Customer"');
  });
});
