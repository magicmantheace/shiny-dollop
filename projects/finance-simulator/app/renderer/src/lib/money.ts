// Money conversion and formatting helpers.
// All persisted/computed values are integer cents; the UI speaks dollars.

const usdFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
});

/** Parse a dollar string like "5000.00" into integer cents. Returns null on invalid input. */
export function dollarsToCents(input: string): number | null {
  const trimmed = input.trim().replace(/[$,\s]/g, '');
  if (trimmed === '') return null;
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return null;
  const [whole, frac = ''] = trimmed.split('.');
  const cents = Number(whole) * 100 + Number((frac + '00').slice(0, 2));
  if (!Number.isSafeInteger(cents)) return null;
  return cents;
}

/** Format integer cents as a dollars string with exactly two decimals, e.g. 500000 -> "5000.00". */
export function centsToDollars(cents: number): string {
  const rounded = Math.round(cents);
  const sign = rounded < 0 ? '-' : '';
  const abs = Math.abs(rounded);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`;
}

/** Display integer cents as USD, e.g. 500000 -> "$5,000.00". */
export function formatUSD(cents: number): string {
  return usdFormatter.format(Math.round(cents) / 100);
}

/** Simulation horizon in engine/simulator.ts (MAX_MONTHS = 1200). */
export const SIMULATION_HORIZON_MONTHS = 1200;

/**
 * Banner for a result that is still open when the simulation reaches its
 * horizon. The engine stops at SIMULATION_HORIZON_MONTHS whether the debt
 * truly never amortises (minimums below monthly interest) or would simply
 * need longer — e.g. $1,201 at 0% APR paid $1/month still owes $1 after
 * 1,200 months. The result carries no cause, so this wording must claim
 * only what is known: not paid off *within the horizon*. It must NOT say
 * "never" or blame minimums not covering interest.
 */
export function formatUnpaidWithinHorizon(
  debtNames: string[],
  horizonMonths: number = SIMULATION_HORIZON_MONTHS,
): string {
  const base = `Not paid off within the ${horizonMonths.toLocaleString('en-US')}-month simulation horizon (${formatHorizon(horizonMonths)})`;
  return debtNames.length > 0 ? `${base} — still open: ${debtNames.join(', ')}.` : `${base}.`;
}

/**
 * Label a per-debt payoff month. The engine's contract (engine/simulator.ts):
 * null = still open at the simulation horizon (see formatUnpaidWithinHorizon
 * — not proof it would never pay off), 0 = already paid (zero starting
 * balance), positive = that 1-based month. Zero must NOT be lumped in with
 * null: an already-paid debt is not unpaid.
 */
export function formatPayoffMonth(payoffMonth: number | null): string {
  if (payoffMonth === null) return 'Not within horizon';
  if (payoffMonth === 0) return 'Already paid (month 0)';
  return `${payoffMonth} (${formatHorizon(payoffMonth)})`;
}

/** Humanize a payoff horizon in months, e.g. 14 -> "1 yr 2 mo", 8 -> "8 mo". */
export function formatHorizon(months: number): string {
  if (!Number.isFinite(months) || months <= 0) return '—';
  const m = Math.round(months);
  const years = Math.floor(m / 12);
  const rest = m % 12;
  const parts: string[] = [];
  if (years > 0) parts.push(`${years} yr`);
  if (rest > 0) parts.push(`${rest} mo`);
  return parts.join(' ') || '0 mo';
}
