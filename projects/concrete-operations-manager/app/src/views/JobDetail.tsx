import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { api, unwrap } from '../api';
import { friendlyError } from '../errorMessages';
import { Dialog } from '../components/Dialog';
import { DocumentTotalsView } from '../components/DocumentTotals';
import { formatCents, formatDate, formatDateTime, formatKm, formatM3, parseM3ToLiters } from '../format';
import type { Invoice, Pour, Quote } from '../../shared/types';

function PourDialog({
  jobId,
  initial,
  onClose,
  onSaved,
}: {
  jobId: number;
  initial: Pour | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { toast } = useStore();
  const [mixDesignId, setMixDesignId] = useState(initial?.mixDesignId ?? '');
  const [quotedM3, setQuotedM3] = useState(
    initial ? (initial.quotedLiters / 1000).toFixed(3) : '',
  );
  const [saving, setSaving] = useState(false);

  async function save() {
    const liters = parseM3ToLiters(quotedM3);
    if (mixDesignId.trim() === '') {
      toast('error', 'Mix design ID is required.');
      return;
    }
    if (liters === null) {
      toast('error', 'Quoted volume must look like 2.500 (m³, up to 3 decimals).');
      return;
    }
    setSaving(true);
    try {
      if (initial) {
        await api().pours.update({ id: initial.id, mixDesignId: mixDesignId.trim(), quotedLiters: liters }).then(unwrap);
        toast('success', 'Pour estimate updated (audited).');
      } else {
        await api().pours.add({ jobId, mixDesignId: mixDesignId.trim(), quotedLiters: liters }).then(unwrap);
        toast('success', 'Pour recorded.');
      }
      onSaved();
      onClose();
    } catch (err) {
      toast('error', friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={initial ? `Edit pour #${initial.id}` : 'Record pour'} onClose={onClose}>
      <div className="form-grid">
        <label className="field">
          Mix design ID *
          <input
            value={mixDesignId}
            onChange={(e) => setMixDesignId(e.target.value)}
            maxLength={40}
            placeholder="e.g. C25/30"
          />
        </label>
        <label className="field">
          Quoted volume (m³, estimate) *
          <input value={quotedM3} onChange={(e) => setQuotedM3(e.target.value)} placeholder="e.g. 2.500" />
        </label>
      </div>
      <p className="muted small-text">
        The mix design ID is a nominal design identifier only — never a verified structural
        performance claim. The quoted volume is the estimate given to the customer; the
        measured delivered volume is finalized separately after the pour.
      </p>
      <div className="row">
        <button className="primary" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : initial ? 'Save changes' : 'Record pour'}
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}

function FinalizeDialog({ pour, onClose, onSaved }: { pour: Pour; onClose: () => void; onSaved: () => void }) {
  const { toast } = useStore();
  const [deliveredM3, setDeliveredM3] = useState(
    pour.deliveredLiters != null ? (pour.deliveredLiters / 1000).toFixed(3) : '',
  );
  const [saving, setSaving] = useState(false);

  async function save() {
    const liters = parseM3ToLiters(deliveredM3);
    if (liters === null) {
      toast('error', 'Delivered volume must look like 2.480 (m³, up to 3 decimals).');
      return;
    }
    setSaving(true);
    try {
      await api().pours.setDelivered({ id: pour.id, deliveredLiters: liters }).then(unwrap);
      toast('success', `Pour #${pour.id}: delivered volume finalized at ${formatM3(liters)} (audited).`);
      onSaved();
      onClose();
    } catch (err) {
      toast('error', friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={`Finalize delivered volume — pour #${pour.id}`} onClose={onClose}>
      <div className="form-grid">
        <label className="field">
          Quoted (estimate)
          <input value={formatM3(pour.quotedLiters)} disabled />
        </label>
        <label className="field">
          Delivered (measured, m³) *
          <input value={deliveredM3} onChange={(e) => setDeliveredM3(e.target.value)} placeholder="e.g. 2.480" />
        </label>
      </div>
      <p className="muted small-text">
        Enter the calibrated/measured volume from the truck. Invoices are always computed from
        this measured value, never from the estimate.
      </p>
      <div className="row">
        <button className="primary" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Finalize'}
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}

function QuoteOverridesDialog({ quote, onClose, onSaved }: { quote: Quote; onClose: () => void; onSaved: () => void }) {
  const { toast } = useStore();
  const [notes, setNotes] = useState(quote.notes ?? '');
  const [rate, setRate] = useState(
    quote.params.concreteRateCentsPerM3 != null ? (quote.params.concreteRateCentsPerM3 / 100).toFixed(2) : '',
  );
  const [smallLoad, setSmallLoad] = useState(
    quote.params.smallLoadChargeCents != null ? (quote.params.smallLoadChargeCents / 100).toFixed(2) : '',
  );
  const [saving, setSaving] = useState(false);

  async function save() {
    const parse = (v: string): number | null | 'invalid' => {
      const t = v.trim();
      if (t === '') return null;
      if (!/^\d+(\.\d{1,2})?$/.test(t)) return 'invalid';
      return Math.round(parseFloat(t) * 100);
    };
    const r = parse(rate);
    const s = parse(smallLoad);
    if (r === 'invalid' || s === 'invalid') {
      toast('error', 'Override fields must look like 180.00 or be left blank.');
      return;
    }
    setSaving(true);
    try {
      await api().quotes.updateDraft({
        id: quote.id,
        notes: notes.trim() === '' ? null : notes.trim(),
        rateOverrideCentsPerM3: r,
        smallLoadChargeOverrideCents: s,
      }).then(unwrap);
      toast('success', 'Draft updated. Overrides were written to the audit trail.');
      onSaved();
      onClose();
    } catch (err) {
      toast('error', friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={`Edit draft quote v${quote.version}`} onClose={onClose}>
      <div className="form-grid">
        <label className="field">
          Concrete rate override ($/m³, blank = pricing default)
          <input value={rate} onChange={(e) => setRate(e.target.value)} />
        </label>
        <label className="field">
          Small-load charge override ($, blank = pricing default)
          <input value={smallLoad} onChange={(e) => setSmallLoad(e.target.value)} />
        </label>
        <label className="field" style={{ gridColumn: '1 / -1' }}>
          Notes
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} maxLength={2000} />
        </label>
      </div>
      <div className="row">
        <button className="primary" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save draft'}
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}

export function JobDetail({ jobId }: { jobId: number }) {
  const { jobs, customers, refresh, toast, go } = useStore();
  const [pours, setPours] = useState<Pour[]>([]);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [pourDialog, setPourDialog] = useState<{ open: boolean; initial: Pour | null }>({ open: false, initial: null });
  const [finalizePour, setFinalizePour] = useState<Pour | null>(null);
  const [overrideQuote, setOverrideQuote] = useState<Quote | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const job = jobs.find((j) => j.id === jobId);
  const customer = job ? customers.find((c) => c.id === job.customerId) : undefined;

  const reload = async () => {
    try {
      const [p, q] = await Promise.all([
        api().pours.listByJob({ jobId }).then(unwrap),
        api().quotes.listByJob({ jobId }).then(unwrap),
      ]);
      setPours(p);
      setQuotes(q);
      const inv = await api().invoices.list().then(unwrap);
      setInvoices(inv.filter((i) => q.some((qq) => qq.id === i.quoteId)));
    } catch (err) {
      toast('error', friendlyError(err));
    }
  };

  useEffect(() => {
    void reload();
  }, [jobId]);

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label);
    try {
      await fn();
      await reload();
      await refresh('audit');
    } catch (err) {
      toast('error', friendlyError(err));
    } finally {
      setBusy(null);
    }
  }

  if (!job) {
    return (
      <div className="card">
        <div className="empty">Job #{jobId} not found.</div>
        <button onClick={() => go({ name: 'jobs' })}>Back to jobs</button>
      </div>
    );
  }

  const latestQuote = quotes[quotes.length - 1];
  const issuedQuote = quotes.find((q) => q.status === 'issued');
  const allFinalized = pours.length > 0 && pours.every((p) => p.deliveredLiters !== null);

  return (
    <div>
      <button className="small" onClick={() => go({ name: 'jobs' })} style={{ marginBottom: 12 }}>
        ← Jobs
      </button>
      <div className="card">
        <div className="row spread">
          <h2 style={{ margin: 0 }}>Job #{job.id} — {customer?.name ?? '…'}</h2>
          <span className={`badge ${job.status === 'completed' ? 'issued' : job.status === 'cancelled' ? 'voided' : 'draft'}`}>
            {job.status.replace('_', ' ')}
          </span>
        </div>
        <dl className="kv" style={{ marginTop: 12 }}>
          <dt>Date</dt>
          <dd>{formatDate(job.jobDate)}</dd>
          <dt>Delivery location</dt>
          <dd>{job.deliveryLocation}</dd>
          <dt>PO number</dt>
          <dd>{job.poNumber ?? '—'}</dd>
          <dt>Distance</dt>
          <dd>{formatKm(job.distanceTenthsKm)}</dd>
          {job.notes && (
            <>
              <dt>Notes</dt>
              <dd>{job.notes}</dd>
            </>
          )}
        </dl>
      </div>

      <div className="card">
        <div className="row spread">
          <h2 style={{ margin: 0 }}>Pours</h2>
          <button className="small primary" onClick={() => setPourDialog({ open: true, initial: null })}>
            + Record pour
          </button>
        </div>
        {pours.length === 0 ? (
          <div className="empty">No pours recorded yet.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Pour</th>
                <th>Mix design ID</th>
                <th className="num">Quoted (estimate)</th>
                <th className="num">Delivered (measured)</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {pours.map((p) => (
                <tr key={p.id}>
                  <td>#{p.id}</td>
                  <td>
                    {p.mixDesignId}{' '}
                    <span className="muted small-text" title="Nominal design identifier only — not verified structural performance">
                      (nominal)
                    </span>
                  </td>
                  <td className="num">
                    {formatM3(p.quotedLiters)} <span className="estimate-tag">estimate</span>
                  </td>
                  <td className="num">
                    {p.deliveredLiters !== null ? (
                      <>
                        {formatM3(p.deliveredLiters)} <span className="measured-tag">measured</span>
                      </>
                    ) : (
                      <span className="muted">not finalized</span>
                    )}
                  </td>
                  <td className="num" style={{ whiteSpace: 'nowrap' }}>
                    <button className="small" onClick={() => setFinalizePour(p)}>
                      {p.deliveredLiters === null ? 'Finalize delivered' : 'Revise delivered'}
                    </button>{' '}
                    <button className="small" onClick={() => setPourDialog({ open: true, initial: p })}>
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <div className="row spread">
          <h2 style={{ margin: 0 }}>Quotes</h2>
          <button
            className="small primary"
            disabled={busy !== null || pours.length === 0}
            onClick={() => run('quote-create', async () => {
              const q = await api().quotes.create({ jobId }).then(unwrap);
              toast('success', `Draft quote v${q.version} created from quoted volumes.`);
            })}
          >
            {busy === 'quote-create' ? '…' : '+ New quote (from estimates)'}
          </button>
        </div>
        {quotes.length === 0 ? (
          <div className="empty">No quotes yet. Quotes are computed from the pours' quoted (estimate) volumes.</div>
        ) : (
          quotes.map((q) => (
            <div key={q.id} className="card" style={{ background: 'var(--bg)' }}>
              <div className="row spread">
                <div>
                  <strong>Quote v{q.version}</strong>{' '}
                  <span className={`badge ${q.status}`}>{q.status}</span>{' '}
                  <span className="muted small-text">
                    created {formatDateTime(q.createdAt)}
                    {q.issuedAt && ` · issued ${formatDateTime(q.issuedAt)}`}
                  </span>
                </div>
                <div className="row">
                  {q.status === 'draft' && (
                    <>
                      <button className="small" onClick={() => setOverrideQuote(q)}>
                        Edit / overrides
                      </button>
                      <button
                        className="small primary"
                        disabled={busy !== null}
                        onClick={() => run(`issue-${q.id}`, async () => {
                          await api().quotes.issue({ id: q.id }).then(unwrap);
                          toast('success', `Quote v${q.version} issued. It is now immutable.`);
                        })}
                      >
                        {busy === `issue-${q.id}` ? '…' : 'Issue'}
                      </button>
                      <button
                        className="small danger"
                        disabled={busy !== null}
                        onClick={() => {
                          if (window.confirm(`Delete draft quote v${q.version}?`)) {
                            void run(`del-${q.id}`, async () => {
                              await api().quotes.deleteDraft({ id: q.id }).then(unwrap);
                              toast('success', 'Draft deleted.');
                            });
                          }
                        }}
                      >
                        Delete
                      </button>
                    </>
                  )}
                  {q.status === 'issued' && (
                    <button
                      className="small"
                      disabled={busy !== null}
                      onClick={() => run(`revise-${q.id}`, async () => {
                        const d = await api().quotes.revise({ id: q.id }).then(unwrap);
                        toast('success', `Revision started as draft v${d.version}. The issued v${q.version} is untouched.`);
                      })}
                    >
                      {busy === `revise-${q.id}` ? '…' : 'Revise (new draft)'}
                    </button>
                  )}
                </div>
              </div>
              <div style={{ marginTop: 10 }}>
                <DocumentTotalsView
                  totals={{
                    lines: q.lines,
                    subtotalCents: q.subtotalCents,
                    taxLines: q.taxLines,
                    totalCents: q.totalCents,
                    taxExemptApplied: q.taxExemptApplied,
                  }}
                />
              </div>
              <div className="muted small-text" style={{ marginTop: 8 }}>
                Computed from {q.params.fromDelivered ? 'delivered (measured)' : 'quoted (estimate)'} volumes ·{' '}
                rate {formatCents(q.params.concreteRateCentsPerM3)}/m³ · taxes:{' '}
                {q.params.taxes.length === 0 ? 'none' : q.params.taxes.map((t) => `${t.name} ${(t.rateBps / 100).toFixed(2)}%`).join(', ')}
                {q.params.taxExempt && ' (customer exempt)'}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="card">
        <div className="row spread">
          <h2 style={{ margin: 0 }}>Invoices</h2>
          <button
            className="small primary"
            disabled={busy !== null || !issuedQuote}
            title={!issuedQuote ? 'Issue a quote first' : !allFinalized ? 'Finalize every pour first' : 'Create invoice'}
            onClick={() => {
              if (!issuedQuote) return;
              if (!allFinalized) {
                toast('error', 'Finalize the delivered volume of every pour before invoicing.');
                return;
              }
              void run('invoice-create', async () => {
                const inv = await api().invoices.create({ quoteId: issuedQuote.id }).then(unwrap);
                toast('success', `Invoice ${inv.invoiceNumber} created from measured volumes.`);
              });
            }}
          >
            {busy === 'invoice-create' ? '…' : '+ Invoice from issued quote'}
          </button>
        </div>
        {invoices.length === 0 ? (
          <div className="empty">
            No invoices yet. Invoices are generated from the issued quote using finalized delivered (measured) volumes.
          </div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Invoice</th>
                <th>Status</th>
                <th className="num">Total</th>
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
        {latestQuote && (
          <p className="muted small-text" style={{ marginBottom: 0 }}>
            Latest quote: v{latestQuote.version} ({latestQuote.status}).
          </p>
        )}
      </div>

      {pourDialog.open && (
        <PourDialog
          jobId={jobId}
          initial={pourDialog.initial}
          onClose={() => setPourDialog({ open: false, initial: null })}
          onSaved={() => { void reload(); void refresh('audit'); }}
        />
      )}
      {finalizePour && (
        <FinalizeDialog
          pour={finalizePour}
          onClose={() => setFinalizePour(null)}
          onSaved={() => { void reload(); void refresh('audit'); }}
        />
      )}
      {overrideQuote && (
        <QuoteOverridesDialog
          quote={overrideQuote}
          onClose={() => setOverrideQuote(null)}
          onSaved={() => { void reload(); void refresh('audit'); }}
        />
      )}
    </div>
  );
}
