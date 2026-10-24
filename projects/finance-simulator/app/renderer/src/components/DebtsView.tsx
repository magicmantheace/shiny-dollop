import { useEffect, useState } from 'react';
import { getSim, type DebtInput } from '../types';
import { centsToDollars, dollarsToCents, formatUSD } from '../lib/money';
import { validateDebt, type DebtFormValues } from '../lib/validation';
import { styles } from '../styles';

const emptyForm: DebtFormValues = { name: '', balance: '', apr: '', minimum: '' };

export default function DebtsView() {
  const [debts, setDebts] = useState<DebtInput[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<DebtFormValues>(emptyForm);
  const [errors, setErrors] = useState<ReturnType<typeof validateDebt>>({});
  const [editingId, setEditingId] = useState<string | null>(null);

  const refresh = async () => {
    try {
      setError(null);
      const list = await getSim().debts.list();
      setDebts(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load debts.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const set = (k: keyof DebtFormValues) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const startEdit = (d: DebtInput) => {
    setEditingId(d.id);
    setForm({
      name: d.name,
      balance: centsToDollars(d.balanceCents),
      apr: String(d.aprPercent),
      minimum: centsToDollars(d.minPaymentCents),
    });
    setErrors({});
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(emptyForm);
    setErrors({});
  };

  const submit = async () => {
    const errs = validateDebt(form);
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;
    try {
      setError(null);
      await getSim().debts.upsert({
        id: editingId ?? (typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `debt-${Date.now()}`),
        name: form.name.trim(),
        balanceCents: dollarsToCents(form.balance) as number,
        aprPercent: Number(form.apr.trim()),
        minPaymentCents: dollarsToCents(form.minimum) as number,
      });
      cancelEdit();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save debt.');
    }
  };

  const remove = async (id: string, name: string) => {
    if (!window.confirm(`Delete debt "${name}"? This cannot be undone.`)) return;
    try {
      setError(null);
      await getSim().debts.remove(id);
      if (editingId === id) cancelEdit();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete debt.');
    }
  };

  const totalMin = debts.reduce((s, d) => s + d.minPaymentCents, 0);
  const totalBal = debts.reduce((s, d) => s + d.balanceCents, 0);

  return (
    <div>
      {error && <div style={styles.errorBox}>{error}</div>}
      <div style={styles.card}>
        <h2 style={styles.cardTitle}>Debts ({debts.length})</h2>
        {loading ? (
          <p style={styles.muted}>Loading…</p>
        ) : debts.length === 0 ? (
          <p style={styles.muted}>No debts yet. Add one below — synthetic data only.</p>
        ) : (
          <table style={styles.table} aria-label="Debts">
            <thead>
              <tr>
                <th style={styles.th}>Name</th>
                <th style={{ ...styles.th, textAlign: 'right' }}>Balance</th>
                <th style={{ ...styles.th, textAlign: 'right' }}>APR</th>
                <th style={{ ...styles.th, textAlign: 'right' }}>Minimum</th>
                <th style={styles.th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {debts.map((d) => (
                <tr key={d.id}>
                  <td style={styles.td}>{d.name}</td>
                  <td style={styles.tdRight}>{formatUSD(d.balanceCents)}</td>
                  <td style={styles.tdRight}>{d.aprPercent.toFixed(2)}%</td>
                  <td style={styles.tdRight}>{formatUSD(d.minPaymentCents)}</td>
                  <td style={styles.td}>
                    <button style={styles.buttonSecondary} onClick={() => startEdit(d)}>Edit</button>{' '}
                    <button style={styles.buttonDanger} onClick={() => void remove(d.id, d.name)}>Delete</button>
                  </td>
                </tr>
              ))}
              <tr>
                <td style={styles.td}><strong>Total</strong></td>
                <td style={styles.tdRight}><strong>{formatUSD(totalBal)}</strong></td>
                <td style={styles.tdRight}>—</td>
                <td style={styles.tdRight}><strong>{formatUSD(totalMin)}/mo</strong></td>
                <td style={styles.td} />
              </tr>
            </tbody>
          </table>
        )}
      </div>

      <div style={styles.card}>
        <h2 style={styles.cardTitle}>{editingId ? 'Edit debt' : 'Add debt'}</h2>
        <div style={styles.formGrid}>
          <div>
            <label style={styles.label}>Name *</label>
            <input style={styles.input} value={form.name} onChange={set('name')} placeholder="Visa" />
            {errors.name && <div style={styles.fieldError}>{errors.name}</div>}
          </div>
          <div>
            <label style={styles.label}>Balance ($) *</label>
            <input style={styles.input} value={form.balance} onChange={set('balance')} placeholder="5000.00" inputMode="decimal" />
            {errors.balance && <div style={styles.fieldError}>{errors.balance}</div>}
          </div>
          <div>
            <label style={styles.label}>APR (%) *</label>
            <input style={styles.input} value={form.apr} onChange={set('apr')} placeholder="9.94" inputMode="decimal" />
            {errors.apr && <div style={styles.fieldError}>{errors.apr}</div>}
          </div>
          <div>
            <label style={styles.label}>Minimum payment ($) *</label>
            <input style={styles.input} value={form.minimum} onChange={set('minimum')} placeholder="125.00" inputMode="decimal" />
            {errors.minimum && <div style={styles.fieldError}>{errors.minimum}</div>}
          </div>
        </div>
        <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
          <button style={styles.button} onClick={() => void submit()}>{editingId ? 'Save changes' : 'Add debt'}</button>
          {editingId && <button style={styles.buttonSecondary} onClick={cancelEdit}>Cancel</button>}
        </div>
      </div>
    </div>
  );
}
