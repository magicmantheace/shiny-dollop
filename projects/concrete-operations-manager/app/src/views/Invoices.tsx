import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { api, unwrap } from '../api';
import { friendlyError } from '../errorMessages';
import { DocumentTotalsView } from '../components/DocumentTotals';
import { formatCents, formatDateTime } from '../format';
import type { Invoice } from '../../shared/types';

export function Invoices() {
  const { invoices, go } = useStore();
  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Invoices</h2>
      <div className="card">
        {invoices.length === 0 ? (
          <div className="empty">No invoices yet. Create one from a job's issued quote.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Invoice</th>
                <th>Status</th>
                <th className="num">Total</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((i) => (
                <tr key={i.id} className="clickable" onClick={() => go({ name: 'invoice', invoiceId: i.id })}>
                  <td>{i.invoiceNumber}</td>
                  <td>
                    <span className={`badge ${i.status}`}>{i.status}</span>
                  </td>
                  <td className="num">{formatCents(i.totalCents)}</td>
                  <td className="muted small-text">{formatDateTime(i.createdAt)}</td>
                  <td className="num">
                    <button className="small" onClick={(e) => { e.stopPropagation(); go({ name: 'invoice', invoiceId: i.id }); }}>
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export function InvoiceDetail({ invoiceId }: { invoiceId: number }) {
  const { invoices, refresh, toast, go } = useStore();
  const [invoice, setInvoice] = useState<Invoice | null>(invoices.find((i) => i.id === invoiceId) ?? null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const found = invoices.find((i) => i.id === invoiceId) ?? null;
    setInvoice(found);
  }, [invoices, invoiceId]);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    try {
      await fn();
      await refresh();
    } catch (err) {
      toast('error', friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  if (!invoice) {
    return (
      <div className="card">
        <div className="empty">Invoice not found.</div>
        <button onClick={() => go({ name: 'invoices' })}>Back to invoices</button>
      </div>
    );
  }

  return (
    <div>
      <button className="small" onClick={() => go({ name: 'invoices' })} style={{ marginBottom: 12 }}>
        ← Invoices
      </button>
      <div className="card">
        <div className="row spread">
          <h2 style={{ margin: 0 }}>Invoice {invoice.invoiceNumber}</h2>
          <span className={`badge ${invoice.status}`}>{invoice.status}</span>
        </div>
        <p className="muted small-text">
          Created {formatDateTime(invoice.createdAt)}
          {invoice.paidAt && ` · paid ${formatDateTime(invoice.paidAt)}`}
          {invoice.voidedAt && ` · voided ${formatDateTime(invoice.voidedAt)}`}
        </p>
        <DocumentTotalsView
          totals={{
            lines: invoice.lines,
            subtotalCents: invoice.subtotalCents,
            taxLines: invoice.taxLines,
            totalCents: invoice.totalCents,
            taxExemptApplied: invoice.taxExemptApplied,
          }}
        />
        <p className="muted small-text">
          Computed from finalized delivered (measured) volumes. Issued invoices are immutable —
          corrections are new documents, never edits.
        </p>
        <div className="row" style={{ marginTop: 12 }}>
          <button
            className="primary"
            disabled={busy}
            onClick={() => run(async () => {
              const r = await api().exports.invoicePdf({ id: invoice.id }).then(unwrap);
              if (r.written) toast('success', `PDF saved to ${r.written}`);
            })}
          >
            {busy ? '…' : 'Export PDF'}
          </button>
          {invoice.status === 'issued' && (
            <>
              <button
                disabled={busy}
                onClick={() => run(async () => {
                  await api().invoices.markPaid({ id: invoice.id }).then(unwrap);
                  toast('success', `Invoice ${invoice.invoiceNumber} marked paid.`);
                })}
              >
                Mark paid
              </button>
              <button
                className="danger"
                disabled={busy}
                onClick={() => {
                  if (window.confirm(`Void invoice ${invoice.invoiceNumber}? The voided record is kept.`)) {
                    void run(async () => {
                      await api().invoices.void({ id: invoice.id }).then(unwrap);
                      toast('success', `Invoice ${invoice.invoiceNumber} voided (record kept).`);
                    });
                  }
                }}
              >
                Void
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
