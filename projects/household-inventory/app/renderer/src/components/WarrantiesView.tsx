import { useEffect, useState } from 'react';
import { styles, theme } from '../styles';
import { formatCents, describeDaysLeft } from '../format';
import type { WarrantyExpiry } from '../../../shared/types';

interface WarrantiesViewProps {
  onSelectItem: (id: string) => void;
}

const WINDOWS = [30, 60, 90, 365];

export default function WarrantiesView({ onSelectItem }: WarrantiesViewProps) {
  const [withinDays, setWithinDays] = useState(90);
  const [entries, setEntries] = useState<WarrantyExpiry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load(days: number) {
    setError(null);
    setLoading(true);
    try {
      const data = await window.inv.warranties.expiring(days);
      setEntries(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(withinDays);
  }, [withinDays]);

  const expired = entries.filter((e) => e.daysLeft < 0).sort((a, b) => a.daysLeft - b.daysLeft);
  const expiring = entries
    .filter((e) => e.daysLeft >= 0)
    .sort((a, b) => a.daysLeft - b.daysLeft);

  function row(e: WarrantyExpiry) {
    return (
      <tr key={e.item.id}>
        <td style={styles.td}>
          <button
            onClick={() => onSelectItem(e.item.id)}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              color: theme.accent,
              cursor: 'pointer',
              fontSize: '14px',
              textAlign: 'left',
            }}
          >
            {e.item.name}
          </button>
        </td>
        <td style={styles.td}>{e.item.category}</td>
        <td style={styles.td}>{e.item.warrantyEnd ?? '—'}</td>
        <td style={styles.td}>{describeDaysLeft(e.daysLeft)}</td>
        <td style={styles.tdRight}>{formatCents(e.item.purchasePriceCents)}</td>
      </tr>
    );
  }

  return (
    <div>
      <div style={{ ...styles.card, display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <div style={{ flex: '0 1 220px' }}>
          <label style={styles.label} htmlFor="inv-win">Show warranties expiring within</label>
          <select
            id="inv-win"
            style={styles.select}
            value={withinDays}
            onChange={(e) => setWithinDays(Number(e.target.value))}
          >
            {WINDOWS.map((w) => (
              <option key={w} value={w}>{w} days</option>
            ))}
          </select>
        </div>
        <p style={{ ...styles.muted, margin: 0 }}>
          Warranties already past their end date always appear under Expired.
        </p>
      </div>

      {error && <div style={styles.errorBox}>Failed to load warranties: {error}</div>}

      {loading ? (
        <p style={styles.muted}>Loading warranties…</p>
      ) : entries.length === 0 ? (
        <div style={styles.card}>
          <p style={styles.muted}>No warranties are being tracked. Add a warranty end date to an item and it will show up here.</p>
        </div>
      ) : (
        <>
          <div style={styles.card}>
            <h2 style={{ ...styles.cardTitle, color: theme.danger }}>
              Expired ({expired.length})
            </h2>
            {expired.length === 0 ? (
              <p style={styles.muted}>None.</p>
            ) : (
              <div style={styles.scrollBox}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Item</th>
                      <th style={styles.th}>Category</th>
                      <th style={styles.th}>Warranty ended</th>
                      <th style={styles.th}>Status</th>
                      <th style={{ ...styles.th, textAlign: 'right' }}>Price</th>
                    </tr>
                  </thead>
                  <tbody>{expired.map(row)}</tbody>
                </table>
              </div>
            )}
          </div>
          <div style={styles.card}>
            <h2 style={{ ...styles.cardTitle, color: theme.warn }}>
              Expiring within {withinDays} days ({expiring.length})
            </h2>
            {expiring.length === 0 ? (
              <p style={styles.muted}>None.</p>
            ) : (
              <div style={styles.scrollBox}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Item</th>
                      <th style={styles.th}>Category</th>
                      <th style={styles.th}>Warranty ends</th>
                      <th style={styles.th}>Status</th>
                      <th style={{ ...styles.th, textAlign: 'right' }}>Price</th>
                    </tr>
                  </thead>
                  <tbody>{expiring.map(row)}</tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
