import { useState } from 'react';
import { useStore } from '../store';
import { api, unwrap } from '../api';
import { friendlyError } from '../errorMessages';
import { Dialog } from '../components/Dialog';
import { formatCents } from '../format';
import type { Customer } from '../../shared/types';
import type { CustomerAddInput } from '../../shared/schemas';

function emptyForm(): CustomerAddInput {
  return {
    name: '',
    contactName: null,
    phone: null,
    email: null,
    address: null,
    taxExempt: false,
    notes: null,
  };
}

function CustomerDialog({
  initial,
  onClose,
  onSaved,
}: {
  initial: Customer | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { toast, settings } = useStore();
  const [form, setForm] = useState<CustomerAddInput>(() =>
    initial
      ? {
          name: initial.name,
          contactName: initial.contactName,
          phone: initial.phone,
          email: initial.email,
          address: initial.address,
          taxExempt: initial.taxExempt,
          concreteRateCentsPerM3: initial.concreteRateCentsPerM3,
          smallLoadChargeCents: initial.smallLoadChargeCents,
          deliveryFeeMode: initial.deliveryFeeMode,
          deliveryFlatCents: initial.deliveryFlatCents,
          deliveryPerKmCents: initial.deliveryPerKmCents,
          notes: initial.notes,
        }
      : emptyForm(),
  );
  const [rateDollars, setRateDollars] = useState(
    initial?.concreteRateCentsPerM3 != null ? (initial.concreteRateCentsPerM3 / 100).toFixed(2) : '',
  );
  const [smallLoadDollars, setSmallLoadDollars] = useState(
    initial?.smallLoadChargeCents != null ? (initial.smallLoadChargeCents / 100).toFixed(2) : '',
  );
  const [flatDollars, setFlatDollars] = useState(
    initial?.deliveryFlatCents != null ? (initial.deliveryFlatCents / 100).toFixed(2) : '',
  );
  const [perKmDollars, setPerKmDollars] = useState(
    initial?.deliveryPerKmCents != null ? (initial.deliveryPerKmCents / 100).toFixed(2) : '',
  );
  const [saving, setSaving] = useState(false);

  const parseMoney = (v: string): number | null | 'invalid' => {
    const t = v.trim();
    if (t === '') return null;
    if (!/^\d+(\.\d{1,2})?$/.test(t)) return 'invalid';
    return Math.round(parseFloat(t) * 100);
  };

  async function save() {
    const rate = parseMoney(rateDollars);
    const smallLoad = parseMoney(smallLoadDollars);
    const flat = parseMoney(flatDollars);
    const perKm = parseMoney(perKmDollars);
    if (rate === 'invalid' || smallLoad === 'invalid' || flat === 'invalid' || perKm === 'invalid') {
      toast('error', 'Money fields must look like 180.00 (dollars and cents).');
      return;
    }
    if (!form.name || form.name.trim() === '') {
      toast('error', 'Customer name is required.');
      return;
    }
    setSaving(true);
    try {
      const payload: CustomerAddInput = {
        ...form,
        name: form.name.trim(),
        concreteRateCentsPerM3: rate,
        smallLoadChargeCents: smallLoad,
        deliveryFlatCents: flat,
        deliveryPerKmCents: perKm,
      };
      if (initial) {
        await api().customers.update({ ...payload, id: initial.id }).then(unwrap);
        toast('success', `Customer "${payload.name}" updated. Pricing changes were written to the audit trail.`);
      } else {
        await api().customers.add(payload).then(unwrap);
        toast('success', `Customer "${payload.name}" created.`);
      }
      onSaved();
      onClose();
    } catch (err) {
      toast('error', friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  const set = <K extends keyof CustomerAddInput>(k: K, v: CustomerAddInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  return (
    <Dialog title={initial ? 'Edit customer' : 'New customer'} onClose={onClose} wide>
      <div className="form-grid">
        <label className="field">
          Name *
          <input value={form.name ?? ''} onChange={(e) => set('name', e.target.value)} maxLength={200} />
        </label>
        <label className="field">
          Contact name
          <input value={form.contactName ?? ''} onChange={(e) => set('contactName', e.target.value)} maxLength={200} />
        </label>
        <label className="field">
          Phone
          <input value={form.phone ?? ''} onChange={(e) => set('phone', e.target.value)} maxLength={40} />
        </label>
        <label className="field">
          Email
          <input value={form.email ?? ''} onChange={(e) => set('email', e.target.value)} maxLength={200} />
        </label>
        <label className="field" style={{ gridColumn: '1 / -1' }}>
          Address
          <input value={form.address ?? ''} onChange={(e) => set('address', e.target.value)} maxLength={500} />
        </label>
        <label className="field inline" style={{ gridColumn: '1 / -1' }}>
          <input
            type="checkbox"
            checked={form.taxExempt ?? false}
            onChange={(e) => set('taxExempt', e.target.checked)}
          />
          Tax-exempt customer (no tax charged; shown as exempt on documents)
        </label>
      </div>
      <h3>Customer-specific pricing (blank = use company defaults)</h3>
      <div className="form-grid">
        <label className="field">
          Concrete rate ($/m³)
          <input
            value={rateDollars}
            onChange={(e) => setRateDollars(e.target.value)}
            placeholder={`default ${formatCents(Number(settings['default_concrete_rate_cents_per_m3'] ?? 18000))}`}
          />
        </label>
        <label className="field">
          Small-load charge ($)
          <input
            value={smallLoadDollars}
            onChange={(e) => setSmallLoadDollars(e.target.value)}
            placeholder={`default ${formatCents(Number(settings['default_small_load_charge_cents'] ?? 15000))}`}
          />
        </label>
        <label className="field">
          Delivery mode
          <select
            value={form.deliveryFeeMode ?? ''}
            onChange={(e) => set('deliveryFeeMode', (e.target.value || null) as 'flat' | 'mileage' | null)}
          >
            <option value="">Company default</option>
            <option value="flat">Flat fee</option>
            <option value="mileage">Per-km</option>
          </select>
        </label>
        <label className="field">
          Flat delivery fee ($)
          <input value={flatDollars} onChange={(e) => setFlatDollars(e.target.value)} placeholder="default" />
        </label>
        <label className="field">
          Per-km rate ($/km)
          <input value={perKmDollars} onChange={(e) => setPerKmDollars(e.target.value)} placeholder="default" />
        </label>
        <label className="field" style={{ gridColumn: '1 / -1' }}>
          Notes
          <textarea value={form.notes ?? ''} onChange={(e) => set('notes', e.target.value)} rows={2} maxLength={2000} />
        </label>
      </div>
      <div className="row">
        <button className="primary" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : initial ? 'Save changes' : 'Create customer'}
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}

export function Customers() {
  const { customers, refresh, toast } = useStore();
  const [dialog, setDialog] = useState<{ open: boolean; initial: Customer | null }>({
    open: false,
    initial: null,
  });
  const [deleting, setDeleting] = useState<number | null>(null);

  async function remove(id: number, name: string) {
    if (!window.confirm(`Delete customer "${name}"? This is only possible when the customer has no jobs.`)) return;
    setDeleting(id);
    try {
      await api().customers.remove({ id }).then(unwrap);
      toast('success', `Customer "${name}" deleted.`);
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
        <h2 style={{ marginTop: 0 }}>Customers</h2>
        <button className="primary" onClick={() => setDialog({ open: true, initial: null })}>
          + New customer
        </button>
      </div>
      <div className="card">
        {customers.length === 0 ? (
          <div className="empty">No customers yet. Create one to start quoting.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Name</th>
                <th>Contact</th>
                <th>Rate</th>
                <th>Tax</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {customers.map((c) => (
                <tr key={c.id}>
                  <td>
                    <strong>{c.name}</strong>
                    {c.address && <div className="muted small-text">{c.address}</div>}
                  </td>
                  <td className="small-text">
                    {[c.contactName, c.phone, c.email].filter(Boolean).join(' · ') || '—'}
                  </td>
                  <td className="small-text">
                    {c.concreteRateCentsPerM3 != null ? `${formatCents(c.concreteRateCentsPerM3)}/m³` : <span className="muted">default</span>}
                  </td>
                  <td>{c.taxExempt ? <span className="badge exempt">exempt</span> : <span className="muted">taxable</span>}</td>
                  <td className="num" style={{ whiteSpace: 'nowrap' }}>
                    <button className="small" onClick={() => setDialog({ open: true, initial: c })}>
                      Edit
                    </button>{' '}
                    <button
                      className="small danger"
                      disabled={deleting === c.id}
                      onClick={() => remove(c.id, c.name)}
                    >
                      {deleting === c.id ? '…' : 'Delete'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {dialog.open && (
        <CustomerDialog
          initial={dialog.initial}
          onClose={() => setDialog({ open: false, initial: null })}
          onSaved={() => refresh()}
        />
      )}
    </div>
  );
}
