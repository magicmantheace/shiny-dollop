import { useState } from 'react';
import { useStore } from '../store';
import { api, unwrap } from '../api';
import { friendlyError } from '../errorMessages';
import { Dialog } from '../components/Dialog';
import { formatDate, formatKm, parseKmToTenths } from '../format';
import type { Job } from '../../shared/types';
import type { JobAddInput } from '../../shared/schemas';

function JobDialog({
  initial,
  onClose,
  onSaved,
}: {
  initial: Job | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { customers, toast } = useStore();
  const [customerId, setCustomerId] = useState(String(initial?.customerId ?? customers[0]?.id ?? ''));
  const [jobDate, setJobDate] = useState(initial?.jobDate ?? new Date().toISOString().slice(0, 10));
  const [deliveryLocation, setDeliveryLocation] = useState(initial?.deliveryLocation ?? '');
  const [poNumber, setPoNumber] = useState(initial?.poNumber ?? '');
  const [distanceKm, setDistanceKm] = useState(
    initial?.distanceTenthsKm != null ? (initial.distanceTenthsKm / 10).toFixed(1) : '',
  );
  const [status, setStatus] = useState<Job['status']>(initial?.status ?? 'scheduled');
  const [notes, setNotes] = useState(initial?.notes ?? '');
  const [saving, setSaving] = useState(false);

  async function save() {
    if (!customerId) {
      toast('error', 'Pick a customer first (create one under Customers).');
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(jobDate)) {
      toast('error', 'Job date must be YYYY-MM-DD.');
      return;
    }
    if (deliveryLocation.trim() === '') {
      toast('error', 'Delivery location is required.');
      return;
    }
    const tenths = parseKmToTenths(distanceKm);
    if (tenths === null && distanceKm.trim() !== '') {
      toast('error', 'Distance must look like 12.5 (km, one decimal).');
      return;
    }
    setSaving(true);
    try {
      const payload: JobAddInput = {
        customerId: Number(customerId),
        jobDate,
        deliveryLocation: deliveryLocation.trim(),
        poNumber: poNumber.trim() === '' ? null : poNumber.trim(),
        distanceTenthsKm: tenths,
        status,
        notes: notes.trim() === '' ? null : notes.trim(),
      };
      if (initial) {
        await api().jobs.update({ ...payload, id: initial.id }).then(unwrap);
        toast('success', 'Job updated.');
      } else {
        const job = await api().jobs.add(payload).then(unwrap);
        toast('success', `Job #${job.id} created.`);
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
    <Dialog title={initial ? `Edit job #${initial.id}` : 'New job'} onClose={onClose} wide>
      <div className="form-grid">
        <label className="field">
          Customer *
          <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Job date *
          <input type="date" value={jobDate} onChange={(e) => setJobDate(e.target.value)} />
        </label>
        <label className="field" style={{ gridColumn: '1 / -1' }}>
          Delivery location *
          <input
            value={deliveryLocation}
            onChange={(e) => setDeliveryLocation(e.target.value)}
            maxLength={500}
            placeholder="1234 Range Road 52, Lethbridge AB"
          />
        </label>
        <label className="field">
          PO number
          <input value={poNumber} onChange={(e) => setPoNumber(e.target.value)} maxLength={100} />
        </label>
        <label className="field">
          Distance one-way (km)
          <input value={distanceKm} onChange={(e) => setDistanceKm(e.target.value)} placeholder="e.g. 18.5" />
        </label>
        <label className="field">
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value as Job['status'])}>
            <option value="scheduled">Scheduled</option>
            <option value="in_progress">In progress</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </label>
        <label className="field" style={{ gridColumn: '1 / -1' }}>
          Notes
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} maxLength={2000} />
        </label>
      </div>
      <div className="row">
        <button className="primary" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : initial ? 'Save changes' : 'Create job'}
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}

export function Jobs() {
  const { jobs, customers, refresh, toast, go } = useStore();
  const [dialog, setDialog] = useState<{ open: boolean; initial: Job | null }>({ open: false, initial: null });
  const [deleting, setDeleting] = useState<number | null>(null);

  const customerName = (id: number) => customers.find((c) => c.id === id)?.name ?? `#${id}`;

  async function remove(id: number) {
    if (!window.confirm(`Delete job #${id}? Only possible when it has no quotes.`)) return;
    setDeleting(id);
    try {
      await api().jobs.remove({ id }).then(unwrap);
      toast('success', `Job #${id} deleted.`);
      await refresh();
    } catch (err) {
      toast('error', friendlyError(err));
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div>
      <div className="row spread">
        <h2 style={{ marginTop: 0 }}>Jobs</h2>
        <button className="primary" onClick={() => setDialog({ open: true, initial: null })}>
          + New job
        </button>
      </div>
      <div className="card">
        {jobs.length === 0 ? (
          <div className="empty">No jobs yet.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Job</th>
                <th>Customer</th>
                <th>Date</th>
                <th>Location</th>
                <th>Distance</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id} className="clickable" onClick={() => go({ name: 'job', jobId: j.id })}>
                  <td>#{j.id}</td>
                  <td>{customerName(j.customerId)}</td>
                  <td>{formatDate(j.jobDate)}</td>
                  <td className="small-text">{j.deliveryLocation}</td>
                  <td>{formatKm(j.distanceTenthsKm)}</td>
                  <td>
                    <span className={`badge ${j.status === 'completed' ? 'issued' : j.status === 'cancelled' ? 'voided' : 'draft'}`}>
                      {j.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td
                    className="num"
                    style={{ whiteSpace: 'nowrap' }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button className="small" onClick={() => setDialog({ open: true, initial: j })}>
                      Edit
                    </button>{' '}
                    <button className="small danger" disabled={deleting === j.id} onClick={() => remove(j.id)}>
                      {deleting === j.id ? '…' : 'Delete'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {dialog.open && (
        <JobDialog
          initial={dialog.initial}
          onClose={() => setDialog({ open: false, initial: null })}
          onSaved={() => refresh()}
        />
      )}
    </div>
  );
}

export { JobDialog };
