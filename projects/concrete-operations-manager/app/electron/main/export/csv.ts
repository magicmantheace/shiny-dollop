/**
 * CSV exports. Written by the main process after the renderer asks for a
 * destination folder (save dialog). Pure string builders are exported for
 * testing; file writing happens in the IPC handler.
 */
import type { DatabaseSync } from 'node:sqlite';
import { listCustomers } from '../db/customers';
import { listJobs } from '../db/jobs';
import { listInvoices } from '../db/invoices';
import { listPoursByJob } from '../db/pours';
import { getStock, listConsumption, listReceipts } from '../db/inventory';
import { formatCents, formatLiters } from '../../../shared/pricing';

function csvCell(value: string | number | null | undefined): string {
  const s = value === null || value === undefined ? '' : String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function toCsv(headers: string[], rows: (string | number | null | undefined)[][]): string {
  const lines = [headers.map(csvCell).join(',')];
  for (const r of rows) lines.push(r.map(csvCell).join(','));
  return lines.join('\r\n') + '\r\n';
}

export function customersCsv(db: DatabaseSync): string {
  const rows = listCustomers(db).map((c) => [
    c.id, c.name, c.contactName, c.phone, c.email, c.address,
    c.taxExempt ? 'yes' : 'no',
    c.concreteRateCentsPerM3 === null ? '' : formatCents(c.concreteRateCentsPerM3),
    c.smallLoadChargeCents === null ? '' : formatCents(c.smallLoadChargeCents),
    c.deliveryFeeMode ?? '',
    c.createdAt,
  ]);
  return toCsv(
    ['id', 'name', 'contact_name', 'phone', 'email', 'address', 'tax_exempt', 'concrete_rate_per_m3', 'small_load_charge', 'delivery_fee_mode', 'created_at'],
    rows,
  );
}

export function jobsCsv(db: DatabaseSync): string {
  const rows = listJobs(db).map((j) => [
    j.id, j.customerId, j.jobDate, j.deliveryLocation, j.poNumber,
    j.distanceTenthsKm === null ? '' : (j.distanceTenthsKm / 10).toFixed(1),
    j.status, j.createdAt,
  ]);
  return toCsv(
    ['id', 'customer_id', 'job_date', 'delivery_location', 'po_number', 'distance_km', 'status', 'created_at'],
    rows,
  );
}

export function invoicesCsv(db: DatabaseSync): string {
  const invoices = listInvoices(db);
  const rows = invoices.map((i) => [
    i.invoiceNumber, i.id, i.quoteId, i.status,
    formatCents(i.subtotalCents),
    ...i.taxLines.map((t) => `${t.name} ${((t.rateBps / 100).toFixed(2))}%: ${formatCents(t.taxCents)}`),
    formatCents(i.totalCents),
    i.taxExemptApplied ? 'yes' : 'no',
    i.createdAt, i.paidAt ?? '', i.voidedAt ?? '',
  ]);
  const taxCount = Math.max(0, ...invoices.map((i) => i.taxLines.length));
  const headers = ['invoice_number', 'id', 'quote_id', 'status', 'subtotal',
    ...Array.from({ length: taxCount }, (_, k) => `tax_${k + 1}`),
    'total', 'tax_exempt', 'created_at', 'paid_at', 'voided_at'];
  return toCsv(headers, rows);
}

export function inventoryCsv(db: DatabaseSync): string {
  const stock = getStock(db);
  const lines: string[] = [];
  lines.push('# stock on hand');
  lines.push(
    toCsv(
      ['material_id', 'material', 'unit', 'received', 'consumed', 'on_hand'],
      stock.map((s) => [s.materialId, s.name, s.unit, s.receivedKg, s.consumedKg, s.onHandKg]),
    ).trimEnd(),
  );
  lines.push('');
  lines.push('# receipts');
  lines.push(
    toCsv(
      ['id', 'material_id', 'supplier', 'received_date', 'qty_kg', 'cost', 'notes'],
      listReceipts(db).map((r) => [
        r.id, r.materialId, r.supplier, r.receivedDate, r.qtyKg, formatCents(r.costCents), r.notes,
      ]),
    ).trimEnd(),
  );
  lines.push('');
  lines.push('# consumption');
  lines.push(
    toCsv(
      ['id', 'pour_id', 'material_id', 'qty_kg', 'created_at'],
      listConsumption(db).map((c) => [c.id, c.pourId, c.materialId, c.qtyKg, c.createdAt]),
    ).trimEnd(),
  );
  return lines.join('\r\n') + '\r\n';
}

export function poursCsv(db: DatabaseSync, jobId: number): string {
  const rows = listPoursByJob(db, jobId).map((p) => [
    p.id, p.jobId, p.mixDesignId,
    formatLiters(p.quotedLiters),
    p.deliveredLiters === null ? '' : formatLiters(p.deliveredLiters),
    p.createdAt,
  ]);
  return toCsv(
    ['id', 'job_id', 'mix_design_id_nominal', 'quoted_m3', 'delivered_m3', 'created_at'],
    rows,
  );
}
