import { useState } from 'react';
import { useStore } from '../store';
import { api, unwrap } from '../api';
import { friendlyError } from '../errorMessages';
import { Dialog } from '../components/Dialog';

const SETTING_FIELDS: { key: string; label: string; kind: 'text' | 'money' | 'liters' | 'mode' }[] = [
  { key: 'company_name', label: 'Company name', kind: 'text' },
  { key: 'company_address', label: 'Company address', kind: 'text' },
  { key: 'default_concrete_rate_cents_per_m3', label: 'Default concrete rate ($/m³)', kind: 'money' },
  { key: 'default_small_load_charge_cents', label: 'Default small-load charge ($)', kind: 'money' },
  { key: 'small_load_threshold_liters', label: 'Small-load threshold (m³)', kind: 'liters' },
  { key: 'default_delivery_mode', label: 'Default delivery mode', kind: 'mode' },
  { key: 'default_delivery_flat_cents', label: 'Default flat delivery fee ($)', kind: 'money' },
  { key: 'default_delivery_per_km_cents', label: 'Default per-km rate ($/km)', kind: 'money' },
];

function toDisplay(key: string, raw: string, kind: string): string {
  if (kind === 'money') return (Number(raw) / 100).toFixed(2);
  if (kind === 'liters') return (Number(raw) / 1000).toFixed(3);
  return raw;
}

function toStored(key: string, display: string, kind: string): string | null {
  const t = display.trim();
  if (kind === 'text' || kind === 'mode') return t;
  if (kind === 'money') {
    if (!/^\d+(\.\d{1,2})?$/.test(t)) return null;
    return String(Math.round(parseFloat(t) * 100));
  }
  // liters → m³ input like 3 or 3.000
  if (!/^\d+(\.\d{1,3})?$/.test(t)) return null;
  return String(Math.round(parseFloat(t) * 1000));
}

function TaxRateDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { toast } = useStore();
  const [name, setName] = useState('');
  const [percent, setPercent] = useState('');
  const [saving, setSaving] = useState(false);

  async function save() {
    if (name.trim() === '') { toast('error', 'Tax name is required.'); return; }
    if (!/^\d+(\.\d{1,2})?$/.test(percent.trim())) { toast('error', 'Rate must look like 5 or 5.00 (%).'); return; }
    const rateBps = Math.round(parseFloat(percent.trim()) * 100);
    setSaving(true);
    try {
      await api().taxRates.add({ name: name.trim(), rateBps }).then(unwrap);
      toast('success', `Tax "${name.trim()}" added.`);
      onSaved();
      onClose();
    } catch (err) {
      toast('error', friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Add tax rate" onClose={onClose}>
      <div className="form-grid">
        <label className="field">
          Name *
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} placeholder="GST" />
        </label>
        <label className="field">
          Rate (%) *
          <input value={percent} onChange={(e) => setPercent(e.target.value)} placeholder="5" />
        </label>
      </div>
      <div className="row">
        <button className="primary" onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Add tax'}</button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}

export function Settings() {
  const { settings, taxRates, refresh, toast } = useStore();
  const [drafts, setDrafts] = useState<Record<string, string> | null>(null);
  const [saving, setSaving] = useState(false);
  const [taxDialog, setTaxDialog] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<{ id: number; name: string; formatVersion: string; importedAt: string }[]>([]);

  const values = drafts ?? Object.fromEntries(SETTING_FIELDS.map((f) => [f.key, toDisplay(f.key, settings[f.key] ?? '', f.kind)]));
  const dirty = drafts !== null;

  async function saveSettings() {
    if (!drafts) return;
    setSaving(true);
    try {
      for (const f of SETTING_FIELDS) {
        const stored = toStored(f.key, drafts[f.key] ?? '', f.kind);
        if (stored === null) {
          toast('error', `Invalid value for "${f.label}".`);
          setSaving(false);
          return;
        }
        await api().settings.set({ key: f.key, value: stored }).then(unwrap);
      }
      toast('success', 'Settings saved.');
      setDrafts(null);
      await refresh();
    } catch (err) {
      toast('error', friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  async function toggleTax(id: number, enabled: boolean) {
    try {
      await api().taxRates.update({ id, enabled: !enabled }).then(unwrap);
      await refresh();
    } catch (err) {
      toast('error', friendlyError(err));
    }
  }

  async function removeTax(id: number, name: string) {
    if (!window.confirm(`Remove tax "${name}"? Issued quotes keep their own tax snapshot.`)) return;
    try {
      await api().taxRates.remove({ id }).then(unwrap);
      toast('success', `Tax "${name}" removed.`);
      await refresh();
    } catch (err) {
      toast('error', friendlyError(err));
    }
  }

  async function runExport(label: string, fn: () => Promise<void>) {
    setBusy(label);
    try {
      await fn();
    } catch (err) {
      toast('error', friendlyError(err));
    } finally {
      setBusy(null);
    }
  }

  async function loadProfiles() {
    try {
      setProfiles(await api().calibration.list().then(unwrap));
    } catch (err) {
      toast('error', friendlyError(err));
    }
  }

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Settings</h2>

      <div className="card">
        <h2>Company & pricing defaults</h2>
        <div className="form-grid">
          {SETTING_FIELDS.map((f) => (
            <label className="field" key={f.key}>
              {f.label}
              {f.kind === 'mode' ? (
                <select
                  value={values[f.key] ?? ''}
                  onChange={(e) => setDrafts({ ...(drafts ?? values), [f.key]: e.target.value })}
                >
                  <option value="flat">Flat fee</option>
                  <option value="mileage">Per-km</option>
                </select>
              ) : (
                <input
                  value={values[f.key] ?? ''}
                  onChange={(e) => setDrafts({ ...(drafts ?? values), [f.key]: e.target.value })}
                />
              )}
            </label>
          ))}
        </div>
        <div className="row">
          <button className="primary" disabled={!dirty || saving} onClick={saveSettings}>
            {saving ? 'Saving…' : 'Save settings'}
          </button>
          {dirty && <button onClick={() => setDrafts(null)}>Reset</button>}
        </div>
        <p className="muted small-text">
          Rounding rule everywhere: half-up to the cent (e.g. $0.005 rounds up to $0.01). Money is
          stored as integer cents; volumes as integer liters; results are deterministic.
        </p>
      </div>

      <div className="card">
        <div className="row spread">
          <h2 style={{ margin: 0 }}>Tax rates</h2>
          <button className="small primary" onClick={() => setTaxDialog(true)}>+ Add tax</button>
        </div>
        <table className="data">
          <thead>
            <tr>
              <th>Name</th>
              <th className="num">Rate</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {taxRates.map((t) => (
              <tr key={t.id}>
                <td>{t.name}</td>
                <td className="num">{(t.rateBps / 100).toFixed(2)}%</td>
                <td>{t.enabled ? <span className="badge issued">enabled</span> : <span className="badge draft">disabled</span>}</td>
                <td className="num" style={{ whiteSpace: 'nowrap' }}>
                  <button className="small" onClick={() => toggleTax(t.id, t.enabled)}>
                    {t.enabled ? 'Disable' : 'Enable'}
                  </button>{' '}
                  <button className="small danger" onClick={() => removeTax(t.id, t.name)}>Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted small-text">Canadian default: GST 5% (Alberta has no provincial sales tax).</p>
      </div>

      <div className="card">
        <h2>Data export</h2>
        <div className="row">
          <button
            disabled={busy !== null}
            onClick={() => runExport('csv', async () => {
              const r = await api().exports.csv().then(unwrap);
              if (r.written.length === 0) toast('info', 'Export cancelled.');
              else toast('success', `CSV files written: ${r.written.join(', ')}`);
            })}
          >
            {busy === 'csv' ? '…' : 'Export CSV (customers, jobs, invoices, inventory)'}
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Backup & restore</h2>
        <div className="row">
          <button
            disabled={busy !== null}
            onClick={() => runExport('backup', async () => {
              const r = await api().backup.create().then(unwrap);
              if (r.written) toast('success', `Backup saved to ${r.written}`);
              else toast('info', 'Backup cancelled.');
            })}
          >
            {busy === 'backup' ? '…' : 'Back up database'}
          </button>
          <button
            className="danger"
            disabled={busy !== null}
            onClick={() => {
              if (window.confirm('Restore replaces the current database with the backup file. A rollback copy is kept first. Continue?')) {
                void runExport('restore', async () => {
                  const r = await api().backup.restore().then(unwrap);
                  if (r.restored) {
                    toast('success', `Database restored. Rollback copy: ${r.rollbackPath}`);
                    await refresh();
                  } else {
                    toast('info', 'Restore cancelled.');
                  }
                });
              }
            }}
          >
            {busy === 'restore' ? '…' : 'Restore from backup…'}
          </button>
        </div>
        <p className="muted small-text">
          Restore validates the file before touching the live database (must be a Concrete
          Operations database at a supported schema version); the pre-restore database is kept
          as a rollback copy.
        </p>
      </div>

      <div className="card">
        <div className="row spread">
          <h2 style={{ margin: 0 }}>Calibration profiles <span className="muted small-text">(interop with the Mix Calculator)</span></h2>
          <div className="row">
            <button className="small" onClick={loadProfiles}>Refresh</button>
            <button
              className="small primary"
              onClick={() => runExport('calimport', async () => {
                const r = await api().calibration.import().then(unwrap);
                if (r.imported) {
                  toast('success', `Imported "${r.imported.name}" (format v${r.imported.formatVersion}).`);
                  await loadProfiles();
                  await refresh('audit');
                } else toast('info', 'Import cancelled.');
              })}
            >
              {busy === 'calimport' ? '…' : 'Import…'}
            </button>
          </div>
        </div>
        {profiles.length === 0 ? (
          <div className="empty">No calibration profiles imported. See docs/CALIBRATION_EXCHANGE.md for the format.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Name</th>
                <th>Format</th>
                <th>Imported</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td className="mono small-text">v{p.formatVersion}</td>
                  <td className="muted small-text">{p.importedAt.slice(0, 10)}</td>
                  <td className="num" style={{ whiteSpace: 'nowrap' }}>
                    <button
                      className="small"
                      onClick={() => runExport(`calexp-${p.id}`, async () => {
                        const r = await api().calibration.export({ id: p.id }).then(unwrap);
                        if (r.written) toast('success', `Exported to ${r.written}`);
                      })}
                    >
                      Export
                    </button>{' '}
                    <button
                      className="small danger"
                      onClick={() => {
                        if (window.confirm(`Remove calibration profile "${p.name}"?`)) {
                          void runExport(`caldel-${p.id}`, async () => {
                            await api().calibration.remove({ id: p.id }).then(unwrap);
                            await loadProfiles();
                          });
                        }
                      }}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {taxDialog && <TaxRateDialog onClose={() => setTaxDialog(false)} onSaved={() => refresh()} />}
    </div>
  );
}
