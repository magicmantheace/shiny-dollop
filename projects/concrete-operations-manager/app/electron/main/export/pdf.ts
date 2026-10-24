/**
 * Invoice PDF generation with pdfkit (pure JS, no native builds).
 * Every charge appears as its own line; each tax as its own line.
 */
import PDFDocument from 'pdfkit';
import type { DatabaseSync } from 'node:sqlite';
import type { Customer, Invoice, Job } from '../../../shared/types';
import { formatCents, formatLiters } from '../../../shared/pricing';
import { getCustomer } from '../db/customers';
import { getJob } from '../db/jobs';
import { listPoursByJob } from '../db/pours';
import { getSetting } from '../db/settings';
import { OpsError, OpsErrorCodes } from '../errors';

export interface InvoicePdfContext {
  invoice: Invoice;
  customer: Customer;
  job: Job;
}

export function getInvoicePdfContext(db: DatabaseSync, invoiceId: number): InvoicePdfContext {
  const row = db.prepare('SELECT * FROM invoices WHERE id = ?').get(invoiceId) as
    | Record<string, unknown>
    | undefined;
  if (!row) throw new OpsError(OpsErrorCodes.NOT_FOUND, `Invoice #${invoiceId} does not exist.`);
  const invoice: Invoice = {
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
  const quote = db.prepare('SELECT job_id FROM quotes WHERE id = ?').get(invoice.quoteId) as
    | { job_id: number }
    | undefined;
  if (!quote) throw new OpsError(OpsErrorCodes.INTERNAL_ERROR, 'Invoice quote is missing.');
  const job = getJob(db, quote.job_id);
  const customer = job ? getCustomer(db, job.customerId) : null;
  if (!job || !customer) throw new OpsError(OpsErrorCodes.INTERNAL_ERROR, 'Invoice job/customer missing.');
  return { invoice, customer, job };
}

function fmtDate(iso: string): string {
  return iso.slice(0, 10);
}

/** Render the invoice PDF to a Buffer. Pure except for pdfkit streaming. */
export async function renderInvoicePdf(
  db: DatabaseSync,
  invoiceId: number,
): Promise<{ buffer: Buffer; fileName: string }> {
  const { invoice, customer, job } = getInvoicePdfContext(db, invoiceId);
  const companyName = getSetting(db, 'company_name');
  const companyAddress = getSetting(db, 'company_address');
  const pours = listPoursByJob(db, job.id);

  const doc = new PDFDocument({ size: 'LETTER', margin: 50 });
  const chunks: Buffer[] = [];
  doc.on('data', (c: Buffer) => chunks.push(c));
  const done = new Promise<Buffer>((resolve, reject) => {
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);
  });

  // Header
  doc.fontSize(20).text(companyName, { align: 'left' });
  if (companyAddress) doc.fontSize(10).fillColor('#444').text(companyAddress);
  doc.fillColor('#000').fontSize(20).text('INVOICE', { align: 'right' });
  doc.moveDown(0.5);
  doc.fontSize(11).text(`Invoice: ${invoice.invoiceNumber}`, { align: 'right' });
  doc.text(`Date: ${fmtDate(invoice.createdAt)}`, { align: 'right' });
  doc.text(`Status: ${invoice.status.toUpperCase()}`, { align: 'right' });
  doc.moveDown();

  // Bill-to / job
  doc.fontSize(12).text('Bill to:', { underline: true });
  doc.fontSize(11).text(customer.name);
  if (customer.address) doc.fontSize(10).fillColor('#444').text(customer.address);
  if (customer.contactName) doc.text(`Attn: ${customer.contactName}`);
  doc.fillColor('#000');
  doc.moveDown(0.5);
  doc.fontSize(12).text('Job:', { underline: true });
  doc.fontSize(10).text(`Delivery date: ${job.jobDate}`);
  doc.text(`Location: ${job.deliveryLocation}`);
  if (job.poNumber) doc.text(`PO: ${job.poNumber}`);
  const deliveredTotal = pours.reduce((s, p) => s + (p.deliveredLiters ?? 0), 0);
  doc.text(`Delivered total: ${formatLiters(deliveredTotal)} (measured)`);
  doc.moveDown();

  // Line items — each charge on its own line.
  doc.fontSize(12).text('Charges:', { underline: true });
  doc.moveDown(0.25);
  const colX = 50;
  const amtX = 480;
  doc.fontSize(10).fillColor('#555').text('Description', colX, doc.y, { continued: true });
  doc.text('Amount', amtX, doc.y, { align: 'right' });
  doc.fillColor('#000');
  doc.moveDown(0.25);
  doc.moveTo(colX, doc.y).lineTo(562, doc.y).stroke();
  doc.moveDown(0.25);
  for (const line of invoice.lines) {
    const y = doc.y;
    doc.fontSize(10).text(line.label, colX, y, { width: 400 });
    if (line.detail) {
      doc.fontSize(9).fillColor('#555').text(line.detail, colX, doc.y, { width: 400 });
      doc.fillColor('#000');
    }
    // The amount is drawn back at the row's top (y), which resets doc.y to
    // the bottom of the single-line amount — above the bottom of a
    // multi-line description. Restore the taller of the two before
    // advancing, or the next charge starts inside this row's detail text.
    const descriptionBottom = doc.y;
    doc.fontSize(10).text(formatCents(line.amountCents), amtX, y, { width: 82, align: 'right' });
    doc.y = Math.max(descriptionBottom, doc.y);
    doc.moveDown(0.35);
  }
  doc.moveTo(colX, doc.y).lineTo(562, doc.y).stroke();
  doc.moveDown(0.25);
  doc.fontSize(10).text('Subtotal', colX, doc.y, { continued: true });
  doc.text(formatCents(invoice.subtotalCents), amtX, doc.y, { width: 82, align: 'right' });
  doc.moveDown(0.25);
  for (const t of invoice.taxLines) {
    const label = invoice.taxExemptApplied
      ? `${t.name} (${(t.rateBps / 100).toFixed(2)}%) — exempt`
      : `${t.name} (${(t.rateBps / 100).toFixed(2)}%)`;
    doc.text(label, colX, doc.y, { continued: true });
    doc.text(formatCents(t.taxCents), amtX, doc.y, { width: 82, align: 'right' });
    doc.moveDown(0.25);
  }
  doc.fontSize(13).text('Total (CAD)', colX, doc.y, { continued: true });
  doc.text(formatCents(invoice.totalCents), amtX, doc.y, { width: 82, align: 'right' });

  // Footer notes
  doc.moveDown(1.5);
  doc.fontSize(9).fillColor('#555').text(
    'Mix design IDs are nominal design identifiers only — not verified structural performance. ' +
      'Volumes billed are calibrated/measured delivered volumes, not estimates.',
  );
  if (invoice.status === 'voided') {
    doc.moveDown();
    doc.fontSize(14).fillColor('#a00').text('VOID', { align: 'center' });
  }

  doc.end();
  const buffer = await done;
  return { buffer, fileName: `${invoice.invoiceNumber}.pdf` };
}
