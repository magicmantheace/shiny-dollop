import { useState } from 'react';
import { getSim, type SimulationResult } from '../types';
import { dollarsToCents, formatHorizon, formatPayoffMonth, formatUnpaidWithinHorizon, formatUSD } from '../lib/money';
import { monthlyIncomeTotalCents } from '../lib/frequency';
import { validateExtraPayment } from '../lib/validation';
import { balancePolyline, chartMaxBalance, downsample } from '../lib/chart';
import { styles, theme } from '../styles';

interface Comparison {
  avalanche: SimulationResult;
  snowball: SimulationResult;
}

function ResultCard({ result, accent }: { result: SimulationResult; accent: string }) {
  return (
    <div style={styles.card}>
      <h2 style={{ ...styles.cardTitle, color: accent }}>
        {result.strategy === 'avalanche' ? 'Avalanche (highest APR first)' : 'Snowball (smallest balance first)'}
      </h2>
      {result.neverPaysOff || result.monthsToPayoff === null ? (
        <div style={{ ...styles.banner, ...styles.bannerWarn }}>
          {formatUnpaidWithinHorizon(result.neverPaysOffDebts)}
        </div>
      ) : (
        <div style={styles.statRow}>
          <span>Months to payoff</span>
          <strong>{result.monthsToPayoff} ({formatHorizon(result.monthsToPayoff)})</strong>
        </div>
      )}
      <div style={styles.statRow}>
        <span>Total paid</span>
        <strong>{formatUSD(result.totalPaidCents)}</strong>
      </div>
      <div style={styles.statRow}>
        <span>Total interest</span>
        <strong>{formatUSD(result.totalInterestCents)}</strong>
      </div>
    </div>
  );
}

function BalanceChart({ comparison }: { comparison: Comparison }) {
  const width = 640;
  const height = 220;
  const max = chartMaxBalance([comparison.avalanche.monthly, comparison.snowball.monthly]);
  const av = downsample(comparison.avalanche.monthly, 200);
  const sn = downsample(comparison.snowball.monthly, 200);
  const avPts = balancePolyline(av, width, height, max);
  const snPts = balancePolyline(sn, width, height, max);
  return (
    <div style={styles.card}>
      <h2 style={styles.cardTitle}>Balance over time</h2>
      <svg
        width="100%"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Total balance per month for avalanche and snowball strategies"
        style={{ background: theme.panel2, borderRadius: '6px' }}
      >
        <polyline points={avPts} fill="none" stroke={theme.accent} strokeWidth="2" />
        <polyline points={snPts} fill="none" stroke={theme.ok} strokeWidth="2" />
      </svg>
      <div style={{ display: 'flex', gap: '20px', marginTop: '8px', fontSize: '13px' }}>
        <span><span style={{ color: theme.accent }}>■</span> Avalanche</span>
        <span><span style={{ color: theme.ok }}>■</span> Snowball</span>
      </div>
    </div>
  );
}

function ScheduleTable({ comparison }: { comparison: Comparison }) {
  const [strategy, setStrategy] = useState<'avalanche' | 'snowball'>('avalanche');
  const result = comparison[strategy];
  // MonthlyPoint.totalPaidCents is the amount paid THAT month; accumulate for display.
  let running = 0;
  const cumulative = result.monthly.map((m) => {
    running += m.totalPaidCents;
    return { month: m.month, totalBalanceCents: m.totalBalanceCents, paidCumulativeCents: running };
  });
  const last = cumulative[cumulative.length - 1];
  const shown = cumulative.length > 25 && last !== undefined
    ? [...cumulative.slice(0, 24), last]
    : cumulative;
  return (
    <div style={styles.card}>
      <h2 style={styles.cardTitle}>Monthly schedule (aggregate)</h2>
      <div style={{ marginBottom: '8px' }}>
        <label style={styles.label}>Strategy</label>
        <select style={{ ...styles.select, width: '220px' }} value={strategy} onChange={(e) => setStrategy(e.target.value as 'avalanche' | 'snowball')}>
          <option value="avalanche">Avalanche</option>
          <option value="snowball">Snowball</option>
        </select>
      </div>
      <div style={styles.scrollBox}>
        <table style={styles.table} aria-label="Monthly aggregate schedule">
          <thead>
            <tr>
              <th style={styles.th}>Month</th>
              <th style={{ ...styles.th, textAlign: 'right' }}>Total balance</th>
              <th style={{ ...styles.th, textAlign: 'right' }}>Paid (cumulative)</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((m, i) => (
              <tr key={m.month}>
                <td style={styles.td}>
                  {m.month}
                  {i === shown.length - 1 && result.monthly.length > 25 ? ' (final)' : ''}
                </td>
                <td style={styles.tdRight}>{formatUSD(m.totalBalanceCents)}</td>
                <td style={styles.tdRight}>{formatUSD(m.paidCumulativeCents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {result.monthly.length > 25 && (
        <p style={styles.muted}>Showing first 24 months + final month of {result.monthly.length}.</p>
      )}
      <p style={styles.muted}>Paid is cumulative across months. Interest accrues monthly before payments.</p>
    </div>
  );
}

function PayoffBreakdown({ comparison }: { comparison: Comparison }) {
  const [strategy, setStrategy] = useState<'avalanche' | 'snowball'>('avalanche');
  const result = comparison[strategy];
  return (
    <div style={styles.card}>
      <h2 style={styles.cardTitle}>Per-debt payoff breakdown</h2>
      <div style={{ marginBottom: '8px' }}>
        <select style={{ ...styles.select, width: '220px' }} value={strategy} onChange={(e) => setStrategy(e.target.value as 'avalanche' | 'snowball')}>
          <option value="avalanche">Avalanche</option>
          <option value="snowball">Snowball</option>
        </select>
      </div>
      <table style={styles.table} aria-label="Per-debt payoff breakdown">
        <thead>
          <tr>
            <th style={styles.th}>Debt</th>
            <th style={{ ...styles.th, textAlign: 'right' }}>Payoff month</th>
            <th style={{ ...styles.th, textAlign: 'right' }}>Total paid</th>
            <th style={{ ...styles.th, textAlign: 'right' }}>Interest paid</th>
          </tr>
        </thead>
        <tbody>
          {result.debts.map((d) => (
            <tr key={d.debtId}>
              <td style={styles.td}>{d.name}</td>
              <td style={styles.tdRight}>
                {formatPayoffMonth(d.payoffMonth)}
              </td>
              <td style={styles.tdRight}>{formatUSD(d.totalPaidCents)}</td>
              <td style={styles.tdRight}>{formatUSD(d.interestPaidCents)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SimulatorView() {
  const [extra, setExtra] = useState('');
  const [extraError, setExtraError] = useState<string | undefined>();
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [budget, setBudget] = useState<{ income: number; minimums: number } | null>(null);
  const [lastExtraCents, setLastExtraCents] = useState(0);
  const [exportMsg, setExportMsg] = useState<string | null>(null);

  const run = async () => {
    const err = validateExtraPayment(extra);
    setExtraError(err);
    if (err) return;
    const extraCents = extra.trim() === '' ? 0 : (dollarsToCents(extra) as number);
    setRunning(true);
    setError(null);
    try {
      const sim = getSim();
      const [income, debts] = await Promise.all([sim.income.list(), sim.debts.list()]);
      if (debts.length === 0) {
        setError('Add at least one debt before running a simulation.');
        return;
      }
      setBudget({
        income: monthlyIncomeTotalCents(income),
        minimums: debts.reduce((s, d) => s + d.minPaymentCents, 0),
      });
      const cmp = await sim.simulate.run(extraCents);
      setComparison(cmp);
      setLastExtraCents(extraCents);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Simulation failed.');
    } finally {
      setRunning(false);
    }
  };

  const exportReport = async (format: 'csv' | 'json') => {
    setExportMsg(null);
    try {
      const res = await getSim().report.save({
        format,
        extraPaymentCents: lastExtraCents,
        defaultName: `finance-simulation-${format === 'csv' ? 'csv' : 'json'}`,
      });
      setExportMsg(res.cancelled ? 'Export cancelled.' : `Saved to ${res.savedPath ?? 'selected location'}.`);
    } catch (e) {
      setExportMsg(e instanceof Error ? e.message : 'Export failed.');
    }
  };

  const unaffordable = budget !== null && budget.minimums > budget.income;

  return (
    <div>
      {error && <div style={styles.errorBox}>{error}</div>}
      <div style={styles.card}>
        <h2 style={styles.cardTitle}>Run comparison</h2>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ width: '220px' }}>
            <label style={styles.label}>Extra monthly payment ($)</label>
            <input
              style={styles.input}
              value={extra}
              onChange={(e) => setExtra(e.target.value)}
              placeholder="0.00"
              inputMode="decimal"
            />
            {extraError && <div style={styles.fieldError}>{extraError}</div>}
          </div>
          <button style={styles.button} onClick={() => void run()} disabled={running}>
            {running ? 'Running…' : 'Run comparison'}
          </button>
        </div>
      </div>

      {budget && (
        <div style={{ ...styles.banner, ...(unaffordable ? styles.bannerWarn : styles.bannerOk) }}>
          {unaffordable ? (
            <>
              ⚠ Unaffordable: total minimums {formatUSD(budget.minimums)}/mo exceed monthly income{' '}
              {formatUSD(budget.income)}/mo. Simulations below assume payments can still be made.
            </>
          ) : (
            <>
              ✓ Budget check: total minimums {formatUSD(budget.minimums)}/mo against monthly income{' '}
              {formatUSD(budget.income)}/mo.
            </>
          )}
        </div>
      )}

      {comparison && (
        <>
          <div style={styles.cards2}>
            <ResultCard result={comparison.avalanche} accent={theme.accent} />
            <ResultCard result={comparison.snowball} accent={theme.ok} />
          </div>
          <BalanceChart comparison={comparison} />
          <ScheduleTable comparison={comparison} />
          <PayoffBreakdown comparison={comparison} />
          <div style={styles.card}>
            <h2 style={styles.cardTitle}>Export scenario report</h2>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button style={styles.buttonSecondary} onClick={() => void exportReport('csv')}>Export CSV</button>
              <button style={styles.buttonSecondary} onClick={() => void exportReport('json')}>Export JSON</button>
            </div>
            {exportMsg && <p style={styles.muted}>{exportMsg}</p>}
            <p style={styles.muted}>Exports use the same extra-payment scenario shown above.</p>
          </div>
        </>
      )}
    </div>
  );
}
