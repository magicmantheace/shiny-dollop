import type { DocumentTotals } from '../../shared/types';
import { formatCents } from '../format';

/**
 * Itemized charge breakdown: every charge on its own line, every tax on
 * its own line. Used for both quotes and invoices.
 */
export function DocumentTotalsView({ totals }: { totals: DocumentTotals }) {
  return (
    <div>
      <table className="data" aria-label="Itemized charges">
        <thead>
          <tr>
            <th>Charge</th>
            <th>Detail</th>
            <th className="num">Amount</th>
          </tr>
        </thead>
        <tbody>
          {totals.lines.map((l, i) => (
            <tr key={i}>
              <td>{l.label}</td>
              <td className="muted">{l.detail ?? '—'}</td>
              <td className="num">{formatCents(l.amountCents)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="totals">
        <div className="trow">
          <span>Subtotal</span>
          <span className="num">{formatCents(totals.subtotalCents)}</span>
        </div>
        {totals.taxLines.map((t, i) => (
          <div className="trow" key={i}>
            <span>
              {t.name} ({(t.rateBps / 100).toFixed(2)}%)
              {totals.taxExemptApplied && <span className="badge exempt" style={{ marginLeft: 8 }}>exempt</span>}
            </span>
            <span className="num">{formatCents(t.taxCents)}</span>
          </div>
        ))}
        <div className="trow grand">
          <span>Total (CAD)</span>
          <span className="num">{formatCents(totals.totalCents)}</span>
        </div>
      </div>
    </div>
  );
}
