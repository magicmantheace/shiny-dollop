/**
 * FINANCE SIMULATOR ENGINE — pure, deterministic debt-payoff simulation.
 *
 * This module has NO side effects, NO I/O, NO dates, NO randomness: the same
 * inputs always produce byte-identical outputs. All money is integer cents;
 * APR is a plain percentage (e.g. 19.99 means 19.99%).
 *
 * SIMULATION RULES
 * 1. Validation: balanceCents >= 0 (integer), aprPercent in [0, 100] (100 is
 *    allowed, 100.01 is rejected), minPaymentCents >= 0 (integer),
 *    extraPaymentCents >= 0 (integer), names non-empty and <= 100 chars,
 *    ids non-empty. Violations throw Error. (The IPC layer validates with
 *    zod before calling; this is defense in depth.)
 * 2. Each simulated month, in this order:
 *    a. Interest accrues on every open debt FIRST:
 *       interestCents = round-half-up(balanceCents * aprPercent / 100 / 12).
 *    b. Every open debt pays its minimum, capped at the amount owed.
 *    c. The extra pool = extraPaymentCents PLUS the minimums freed by debts
 *       paid off in EARLIER months (snowballing: total monthly outflow stays
 *       constant as debts die — a debt's minimum joins the pool starting the
 *       month after it is paid off, since it was spent on that debt's own
 *       minimum in its payoff month). The pool is applied to the current
 *       target debt, capped at the amount owed; any leftover is ignored. If
 *       the pool pays a debt off, the next target is chosen, until the pool
 *       is exhausted or no debt is open.
 * 3. Target selection:
 *    - avalanche: highest APR; tie -> lowest balance.
 *    - snowball:  lowest balance; tie -> highest APR.
 *    Minimums are always paid in input order; only the extra pool is
 *    target-ordered.
 * 4. Hard cap of 1200 months (100 years). Debts still open afterwards are
 *    reported via neverPaysOff=true, monthsToPayoff=null, and
 *    neverPaysOffDebts lists their names.
 * 5. A debt with a zero starting balance is already paid: payoffMonth = 0,
 *    no interest, no payments. Empty debt list -> all zeros, neverPaysOff
 *    false.
 * 6. Month numbers in `monthly` and `payoffMonth` are 1-based; the final
 *    `monthly` entry's totalBalanceCents is the end-of-month balance (0 when
 *    everything paid off).
 *
 * This is a scenario calculator, not financial advice.
 */

export type Strategy = 'avalanche' | 'snowball';

export interface DebtInput {
  id: string;
  name: string;
  balanceCents: number;
  aprPercent: number;
  minPaymentCents: number;
}

export interface DebtPayoff {
  debtId: string;
  name: string;
  payoffMonth: number | null;
  interestPaidCents: number;
  totalPaidCents: number;
}

export interface MonthlyPoint {
  month: number;
  totalBalanceCents: number;
  totalPaidCents: number;
}

export interface SimulationResult {
  strategy: Strategy;
  monthsToPayoff: number | null;
  totalPaidCents: number;
  totalInterestCents: number;
  debts: DebtPayoff[];
  monthly: MonthlyPoint[];
  neverPaysOff: boolean;
  neverPaysOffDebts: string[];
}

/**
 * Per-debt, per-month detail used for CSV report export.
 * Column contract: strategy,debt,month,balance_cents,interest_cents,payment_cents
 * where `debt` is the debt name.
 */
export interface ReportRow {
  strategy: Strategy;
  debt: string;
  month: number;
  balanceCents: number;
  interestCents: number;
  paymentCents: number;
}

/** Maximum simulated months (100 years). */
export const MAX_MONTHS = 1200;

/**
 * Monthly interest in whole cents, round-half-up:
 *   round(balanceCents * aprPercent / 100 / 12)
 */
export function monthlyInterestCents(balanceCents: number, aprPercent: number): number {
  if (balanceCents <= 0 || aprPercent <= 0) return 0;
  const raw = (balanceCents * aprPercent) / 1200;
  return Math.floor(raw + 0.5);
}

function isCents(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value);
}

function validateDebtInput(debt: DebtInput): void {
  if (typeof debt !== 'object' || debt === null) {
    throw new Error('Debt must be an object.');
  }
  if (typeof debt.id !== 'string' || debt.id.length === 0) {
    throw new Error('Debt id must be a non-empty string.');
  }
  if (typeof debt.name !== 'string' || debt.name.length === 0) {
    throw new Error('Debt name must be a non-empty string.');
  }
  if (debt.name.length > 100) {
    throw new Error(`Debt name must be at most 100 characters (got ${debt.name.length}).`);
  }
  if (!isCents(debt.balanceCents) || debt.balanceCents < 0) {
    throw new Error(`balanceCents must be an integer >= 0 (got ${String(debt.balanceCents)}).`);
  }
  if (
    typeof debt.aprPercent !== 'number' ||
    !Number.isFinite(debt.aprPercent) ||
    debt.aprPercent < 0 ||
    debt.aprPercent > 100
  ) {
    throw new Error(`aprPercent must be a number in [0, 100] (got ${String(debt.aprPercent)}).`);
  }
  if (!isCents(debt.minPaymentCents) || debt.minPaymentCents < 0) {
    throw new Error(`minPaymentCents must be an integer >= 0 (got ${String(debt.minPaymentCents)}).`);
  }
}

function validateRun(debts: DebtInput[], extraPaymentCents: number, strategy: Strategy): void {
  if (!Array.isArray(debts)) {
    throw new Error('debts must be an array.');
  }
  for (const debt of debts) {
    validateDebtInput(debt);
  }
  if (!isCents(extraPaymentCents) || extraPaymentCents < 0) {
    throw new Error(`extraPaymentCents must be an integer >= 0 (got ${String(extraPaymentCents)}).`);
  }
  if (strategy !== 'avalanche' && strategy !== 'snowball') {
    throw new Error(`strategy must be 'avalanche' or 'snowball' (got ${String(strategy)}).`);
  }
}

interface MutableDebt {
  id: string;
  name: string;
  aprPercent: number;
  minPaymentCents: number;
  balance: number;
  open: boolean;
  payoffMonth: number | null;
  interestPaid: number;
  totalPaid: number;
}

interface MonthDetail {
  debtId: string;
  name: string;
  interestCents: number;
  paymentCents: number;
  endBalanceCents: number;
}

/** Choose the debt the extra pool attacks this month (rule 3). */
function pickTarget(open: MutableDebt[], strategy: Strategy): MutableDebt | null {
  if (open.length === 0) return null;
  let best = open[0] as MutableDebt;
  for (let i = 1; i < open.length; i++) {
    const candidate = open[i] as MutableDebt;
    if (strategy === 'avalanche') {
      if (
        candidate.aprPercent > best.aprPercent ||
        (candidate.aprPercent === best.aprPercent && candidate.balance < best.balance)
      ) {
        best = candidate;
      }
    } else {
      if (
        candidate.balance < best.balance ||
        (candidate.balance === best.balance && candidate.aprPercent > best.aprPercent)
      ) {
        best = candidate;
      }
    }
  }
  return best;
}

interface FullRun {
  result: SimulationResult;
  detail: MonthDetail[][];
}

function runSimulation(debts: DebtInput[], extraPaymentCents: number, strategy: Strategy): FullRun {
  const state: MutableDebt[] = debts.map((d) => ({
    id: d.id,
    name: d.name,
    aprPercent: d.aprPercent,
    minPaymentCents: d.minPaymentCents,
    balance: d.balanceCents,
    open: d.balanceCents > 0,
    payoffMonth: d.balanceCents > 0 ? null : 0,
    interestPaid: 0,
    totalPaid: 0,
  }));

  const monthly: MonthlyPoint[] = [];
  const detail: MonthDetail[][] = [];
  let month = 0;
  // Minimums freed by debts paid off in earlier months (snowballing).
  let freedMin = 0;

  while (state.some((d) => d.open) && month < MAX_MONTHS) {
    month += 1;

    // (a) Interest accrues before any payment.
    const monthInterest = new Map<string, number>();
    for (const d of state) {
      if (!d.open) continue;
      const interest = monthlyInterestCents(d.balance, d.aprPercent);
      d.balance += interest;
      d.interestPaid += interest;
      monthInterest.set(d.id, interest);
    }

    // (b) Minimums, input order, capped at amount owed.
    const monthPaid = new Map<string, number>();
    let newlyFreed = 0;
    for (const d of state) {
      if (!d.open) continue;
      const pay = Math.min(d.minPaymentCents, d.balance);
      d.balance -= pay;
      d.totalPaid += pay;
      monthPaid.set(d.id, pay);
      if (d.balance === 0) {
        d.open = false;
        d.payoffMonth = month;
        newlyFreed += d.minPaymentCents; // joins the pool next month
      }
    }

    // (c) Extra pool: extra + minimums freed in earlier months, target-ordered.
    let pool = extraPaymentCents + freedMin;
    while (pool > 0) {
      const open = state.filter((d) => d.open);
      const target = pickTarget(open, strategy);
      if (!target) break;
      const pay = Math.min(pool, target.balance);
      target.balance -= pay;
      target.totalPaid += pay;
      pool -= pay;
      monthPaid.set(target.id, (monthPaid.get(target.id) ?? 0) + pay);
      if (target.balance === 0) {
        target.open = false;
        target.payoffMonth = month;
        newlyFreed += target.minPaymentCents; // joins the pool next month
      }
    }
    freedMin += newlyFreed;

    monthly.push({
      month,
      totalBalanceCents: state.reduce((sum, d) => sum + d.balance, 0),
      totalPaidCents: state.reduce((sum, d) => sum + (monthPaid.get(d.id) ?? 0), 0),
    });
    detail.push(
      state.map((d) => ({
        debtId: d.id,
        name: d.name,
        interestCents: monthInterest.get(d.id) ?? 0,
        paymentCents: monthPaid.get(d.id) ?? 0,
        endBalanceCents: d.balance,
      })),
    );
  }

  const neverPaysOff = state.some((d) => d.open);
  const result: SimulationResult = {
    strategy,
    monthsToPayoff: neverPaysOff ? null : month,
    totalPaidCents: state.reduce((sum, d) => sum + d.totalPaid, 0),
    totalInterestCents: state.reduce((sum, d) => sum + d.interestPaid, 0),
    debts: state.map((d) => ({
      debtId: d.id,
      name: d.name,
      payoffMonth: d.payoffMonth,
      interestPaidCents: d.interestPaid,
      totalPaidCents: d.totalPaid,
    })),
    monthly,
    neverPaysOff,
    neverPaysOffDebts: neverPaysOff ? state.filter((d) => d.open).map((d) => d.name) : [],
  };
  return { result, detail };
}

/**
 * Run a full debt-payoff simulation. Throws Error on invalid input.
 */
export function simulateDebts(
  debts: DebtInput[],
  extraPaymentCents: number,
  strategy: Strategy,
): SimulationResult {
  validateRun(debts, extraPaymentCents, strategy);
  return runSimulation(debts, extraPaymentCents, strategy).result;
}

/**
 * Per-debt, per-month detail rows for report export, for one strategy.
 * Validates input the same way as simulateDebts.
 */
export function reportRows(
  debts: DebtInput[],
  extraPaymentCents: number,
  strategy: Strategy,
): ReportRow[] {
  validateRun(debts, extraPaymentCents, strategy);
  const { detail } = runSimulation(debts, extraPaymentCents, strategy);
  const rows: ReportRow[] = [];
  detail.forEach((monthRows, index) => {
    for (const r of monthRows) {
      rows.push({
        strategy,
        debt: r.name,
        month: index + 1,
        balanceCents: r.endBalanceCents,
        interestCents: r.interestCents,
        paymentCents: r.paymentCents,
      });
    }
  });
  return rows;
}
