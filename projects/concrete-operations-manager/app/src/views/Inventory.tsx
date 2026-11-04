import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { api, unwrap } from '../api';
import { friendlyError } from '../errorMessages';
import { Dialog } from '../components/Dialog';
import { formatCents, formatDate } from '../format';
import type { InventoryConsumption, InventoryReceipt } from '../../shared/types';

function ReceiptDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { toast, materials } = useStore();
  const [materialId, setMaterialId] = useState(String(materials[0]?.id ?? ''));
  const [supplier, setSupplier] = useState('');
  const [receivedDate, setReceivedDate] = useState(new Date().toISOString().slice(0, 10));
  const [qtyKg, setQtyKg] = useState('');
  const [cost, setCost] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  async function save() {
    const qty = Number(qtyKg);
    if (!materialId) { toast('error', 'Pick a material.'); return; }
    if (supplier.trim() === '') { toast('error', 'Supplier is required.'); return; }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(receivedDate)) { toast('error', 'Date must be YYYY-MM-DD.'); return; }
    if (!Number.isInteger(qty) || qty <= 0) { toast('error', 'Quantity must be a positive whole number of kg.'); return; }
    const costCents = cost.trim() === '' ? 0 : /^\d+(\.\d{1,2})?$/.test(cost.trim()) ? Math.round(parseFloat(cost.trim()) * 100) : NaN;
    if (Number.isNaN(costCents)) { toast('error', 'Cost must look like 1234.56.'); return; }
    setSaving(true);
    try {
      await api().inventory.receiptAdd({
        materialId: Number(materialId),
        supplier: supplier.trim(),
        receivedDate,
        qtyKg: qty,
        costCents,
        notes: notes.trim() === '' ? null : notes.trim(),
      }).then(unwrap);
      toast('success', 'Receipt recorded.');
      onSaved();
      onClose();
    } catch (err) {
      toast('error', friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Record material receipt" onClose={onClose}>
      <div className="form-grid">
        <label className="field">
          Material *
          <select value={materialId} onChange={(e) => setMaterialId(e.target.value)}>
            {materials.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Supplier *
          <input value={supplier} onChange={(e) => setSupplier(e.target.value)} maxLength={200} />
        </label>
        <label className="field">
          Received date *
          <input type="date" value={receivedDate} onChange={(e) => setReceivedDate(e.target.value)} />
        </label>
        <label className="field">
          Quantity (kg) *
          <input value={qtyKg} onChange={(e) => setQtyKg(e.target.value)} inputMode="numeric" />
        </label>
        <label className="field">
          Cost ($)
          <input value={cost} onChange={(e) => setCost(e.target.value)} placeholder="0.00" />
        </label>
        <label className="field" style={{ gridColumn: '1 / -1' }}>
          Notes
          <input value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} />
        </label>
      </div>
      <div className="row">
        <button className="primary" onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Record receipt'}</button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}

function ConsumptionDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { toast, materials, jobs } = useStore();
  const [jobId, setJobId] = useState('');
  const [pours, setPours] = useState<{ id: number; mixDesignId: string }[]>([]);
  const [pourId, setPourId] = useState('');
  const [materialId, setMaterialId] = useState(String(materials[0]?.id ?? ''));
  const [qtyKg, setQtyKg] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!jobId) { setPours([]); setPourId(''); return; }
    api().pours.listByJob({ jobId: Number(jobId) }).then(unwrap).then((p) => {
      setPours(p);
      setPourId(p[0] ? String(p[0].id) : '');
    }).catch((err: unknown) => toast('error', friendlyError(err)));
  }, [jobId, toast]);

  async function save() {
    const qty = Number(qtyKg);
    if (!pourId || !materialId) { toast('error', 'Pick a pour and a material.'); return; }
    if (!Number.isInteger(qty) || qty <= 0) { toast('error', 'Quantity must be a positive whole number of kg.'); return; }
    setSaving(true);
    try {
      await api().inventory.consumptionAdd({ pourId: Number(pourId), materialId: Number(materialId), qtyKg: qty }).then(unwrap);
      toast('success', 'Consumption recorded.');
      onSaved();
      onClose();
    } catch (err) {
      toast('error', friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Record material consumption" onClose={onClose}>
      <div className="form-grid">
        <label className="field">
          Job *
          <select value={jobId} onChange={(e) => setJobId(e.target.value)}>
            <option value="">— pick a job —</option>
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>#{j.id} · {j.deliveryLocation}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Pour *
          <select value={pourId} onChange={(e) => setPourId(e.target.value)} disabled={pours.length === 0}>
            {pours.map((p) => (
              <option key={p.id} value={p.id}>#{p.id} · mix {p.mixDesignId}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Material *
          <select value={materialId} onChange={(e) => setMaterialId(e.target.value)}>
            {materials.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Quantity (kg) *
          <input value={qtyKg} onChange={(e) => setQtyKg(e.target.value)} inputMode="numeric" />
        </label>
      </div>
      <p className="muted small-text">
        Consumption can never exceed stock on hand — the app blocks it and tells you to record a receipt first.
      </p>
      <div className="row">
        <button className="primary" onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Record consumption'}</button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}

export function Inventory() {
  const { stock, materials, refresh, toast } = useStore();
  const [receipts, setReceipts] = useState<InventoryReceipt[]>([]);
  const [consumption, setConsumption] = useState<InventoryConsumption[]>([]);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [consumeOpen, setConsumeOpen] = useState(false);
  const [newMaterial, setNewMaterial] = useState('');

  const materialName = (id: number) => materials.find((m) => m.id === id)?.name ?? `#${id}`;

  const reload = async () => {
    try {
      const [r, c] = await Promise.all([
        api().inventory.receipts().then(unwrap),
        api().inventory.consumption().then(unwrap),
      ]);
      setReceipts(r);
      setConsumption(c);
    } catch (err) {
      toast('error', friendlyError(err));
    }
  };

  useEffect(() => { void reload(); }, []);

  async function addMaterial() {
    const name = newMaterial.trim();
    if (name === '') { toast('error', 'Material name is required.'); return; }
    try {
      await api().inventory.materialAdd({ name }).then(unwrap);
      toast('success', `Material "${name}" added.`);
      setNewMaterial('');
      await refresh();
    } catch (err) {
      toast('error', friendlyError(err));
    }
  }

  return (
    <div>
      <div className="row spread">
        <h2 style={{ marginTop: 0 }}>Inventory</h2>
        <div className="row">
          <button className="primary small" onClick={() => setReceiptOpen(true)}>+ Receipt</button>
          <button className="small" onClick={() => setConsumeOpen(true)}>+ Consumption</button>
        </div>
      </div>

      <div className="card">
        <h2>Stock on hand</h2>
        <table className="data">
          <thead>
            <tr>
              <th>Material</th>
              <th className="num">Received</th>
              <th className="num">Consumed</th>
              <th className="num">On hand</th>
            </tr>
          </thead>
          <tbody>
            {stock.map((s) => (
              <tr key={s.materialId}>
                <td>{s.name}</td>
                <td className="num">{s.receivedKg.toLocaleString()} {s.unit}</td>
                <td className="num">{s.consumedKg.toLocaleString()} {s.unit}</td>
                <td className="num"><strong>{s.onHandKg.toLocaleString()} {s.unit}</strong></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="row" style={{ marginTop: 10 }}>
          <input
            value={newMaterial}
            onChange={(e) => setNewMaterial(e.target.value)}
            placeholder="New material name"
            maxLength={200}
          />
          <button className="small" onClick={addMaterial}>Add material</button>
        </div>
      </div>

      <div className="card">
        <h2>Receipts</h2>
        {receipts.length === 0 ? (
          <div className="empty">No receipts yet.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Date</th>
                <th>Material</th>
                <th>Supplier</th>
                <th className="num">Qty</th>
                <th className="num">Cost</th>
              </tr>
            </thead>
            <tbody>
              {receipts.map((r) => (
                <tr key={r.id}>
                  <td>{formatDate(r.receivedDate)}</td>
                  <td>{materialName(r.materialId)}</td>
                  <td>{r.supplier}</td>
                  <td className="num">{r.qtyKg.toLocaleString()} kg</td>
                  <td className="num">{formatCents(r.costCents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>Consumption</h2>
        {consumption.length === 0 ? (
          <div className="empty">No consumption recorded yet.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Pour</th>
                <th>Material</th>
                <th className="num">Qty</th>
              </tr>
            </thead>
            <tbody>
              {consumption.map((c) => (
                <tr key={c.id}>
                  <td>#{c.pourId}</td>
                  <td>{materialName(c.materialId)}</td>
                  <td className="num">{c.qtyKg.toLocaleString()} kg</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {receiptOpen && <ReceiptDialog onClose={() => setReceiptOpen(false)} onSaved={() => { void reload(); void refresh(); }} />}
      {consumeOpen && <ConsumptionDialog onClose={() => setConsumeOpen(false)} onSaved={() => { void reload(); void refresh(); }} />}
    </div>
  );
}
