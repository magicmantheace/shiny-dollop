import { useEffect, useState } from 'react';
import { getSim, FREQUENCY_LABELS, INCOME_FREQUENCIES, type IncomeRecord } from '../types';
import { centsToDollars, dollarsToCents, formatUSD } from '../lib/money';
import { monthlyIncomeTotalCents } from '../lib/frequency';
import { validateIncome, type IncomeFormValues } from '../lib/validation';
import { styles } from '../styles';

const emptyForm: IncomeFormValues = { name: '', amount: '', frequency: 'monthly' };

export default function IncomeView() {
  const [income, setIncome] = useState<IncomeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<IncomeFormValues>(emptyForm);
  const [errors, setErrors] = useState<ReturnType<typeof validateIncome>>({});
  const [editingId, setEditingId] = useState<string | null>(null);

  const refresh = async () => {
    try {
      setError(null);
      setIncome(await getSim().income.list());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load income.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const setField = (k: keyof IncomeFormValues) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const startEdit = (r: IncomeRecord) => {
    setEditingId(r.id);
    setForm({ name: r.name, amount: centsToDollars(r.amountCents), frequency: r.frequency });
    setErrors({});
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(emptyForm);
    setErrors({});
  };

  const submit = async () => {
    const errs = validateIncome(form);
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;
    try {
      setError(null);
      await getSim().income.upsert({
        id: editingId ?? (typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `inc-${Date.now()}`),
        name: form.name.trim(),
        amountCents: dollarsToCents(form.amount) as number,
        frequency: form.frequency as IncomeRecord['frequency'],
      });
      cancelEdit();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save income.');
    }
  };

  const remove = async (id: string, name: string) => {
    if (!window.confirm(`Delete income source "${name}"?`)) return;
    try {
      setError(null);
      await getSim().income.remove(id);
      if (editingId === id) cancelEdit();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete income.');
    }
  };

  const monthlyTotal = monthlyIncomeTotalCents(income);
  const hasOnce = income.some((r) => r.frequency === 'once');

  return (
    <div>
      {error && <div style={styles.errorBox}>{error}</div>}
      <div style={styles.card}>
        <h2 style={styles.cardTitle}>Income sources ({income.length})</h2>
        {loading ? (
          <p style={styles.muted}>Loading…</p>
        ) : income.length === 0 ? (
          <p style={styles.muted}>No income sources yet. Add one below — synthetic data only.</p>
        ) : (
          <table style={styles.table} aria-label="Income sources">
            <thead>
              <tr>
                <th style={styles.th}>Name</th>
                <th style={{ ...styles.th, textAlign: 'right' }}>Amount</th>
                <th style={styles.th}>Frequency</th>
                <th style={styles.th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {income.map((r) => (
                <tr key={r.id}>
                  <td style={styles.td}>{r.name}</td>
                  <td style={styles.tdRight}>{formatUSD(r.amountCents)}</td>
                  <td style={styles.td}>{FREQUENCY_LABELS[r.frequency]}</td>
                  <td style={styles.td}>
                    <button style={styles.buttonSecondary} onClick={() => startEdit(r)}>Edit</button>{' '}
                    <button style={styles.buttonDanger} onClick={() => void remove(r.id, r.name)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div style={{ marginTop: '12px', fontSize: '16px' }}>
          <strong>Monthly income total: {formatUSD(monthlyTotal)}</strong>
          {hasOnce && (
            <div style={styles.muted}>One-time income is excluded from the monthly total.</div>
          )}
        </div>
      </div>

      <div style={styles.card}>
        <h2 style={styles.cardTitle}>{editingId ? 'Edit income source' : 'Add income source'}</h2>
        <div style={styles.formGrid}>
          <div>
            <label style={styles.label}>Name *</label>
            <input style={styles.input} value={form.name} onChange={setField('name')} placeholder="Paycheck" />
            {errors.name && <div style={styles.fieldError}>{errors.name}</div>}
          </div>
          <div>
            <label style={styles.label}>Amount ($) *</label>
            <input style={styles.input} value={form.amount} onChange={setField('amount')} placeholder="1557.51" inputMode="decimal" />
            {errors.amount && <div style={styles.fieldError}>{errors.amount}</div>}
          </div>
          <div>
            <label style={styles.label}>Frequency *</label>
            <select style={styles.select} value={form.frequency} onChange={setField('frequency')}>
              {INCOME_FREQUENCIES.map((f) => (
                <option key={f} value={f}>{FREQUENCY_LABELS[f]}</option>
              ))}
            </select>
            {errors.frequency && <div style={styles.fieldError}>{errors.frequency}</div>}
          </div>
        </div>
        <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
          <button style={styles.button} onClick={() => void submit()}>{editingId ? 'Save changes' : 'Add income'}</button>
          {editingId && <button style={styles.buttonSecondary} onClick={cancelEdit}>Cancel</button>}
        </div>
      </div>
    </div>
  );
}
