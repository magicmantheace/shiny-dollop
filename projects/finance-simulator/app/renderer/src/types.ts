// Renderer-side copy of the window.sim contract.
// Authoritative implementation: Worker A — app/electron/preload.ts,
// app/shared/api-types.ts, app/engine/simulator.ts, app/shared/types.ts.
// This file mirrors those shapes; any drift is a bug. See "Contract notes"
// in docs/PRODUCT_SPEC.md (as-built appendix).
//
// Contract deviations vs. the original task brief are marked [DEV].

export type IncomeFrequency = 'monthly' | 'biweekly' | 'weekly' | 'once';


export const INCOME_FREQUENCIES: IncomeFrequency[] = ['monthly', 'biweekly', 'weekly', 'once'];

export const FREQUENCY_LABELS: Record<IncomeFrequency, string> = {
  monthly: 'Monthly',
  biweekly: 'Every 2 weeks',
  weekly: 'Weekly',
  once: 'One-time (excluded from monthly total)',
};

export interface DebtInput {
  id: string;
  name: string;
  balanceCents: number;
  aprPercent: number;
  minPaymentCents: number;
}

export interface DebtRecord extends DebtInput {
  createdAt: string;
}

export interface IncomeRecord {
  id: string;
  name: string;
  amountCents: number;
  frequency: IncomeFrequency;
  createdAt: string;
}

export interface DebtPayoff {
  debtId: string;
  name: string;
  payoffMonth: number | null; // null = never pays off; 0 = already paid (zero balance)
  interestPaidCents: number;
  totalPaidCents: number;
}

export interface MonthlyPoint {
  month: number; // 1-based
  totalBalanceCents: number;
  totalPaidCents: number; // cumulative across all debts
}

export interface SimulationResult {
  strategy: 'avalanche' | 'snowball';
  monthsToPayoff: number | null; // null = never pays off
  totalPaidCents: number;
  totalInterestCents: number;
  debts: DebtPayoff[];
  monthly: MonthlyPoint[];
  neverPaysOff: boolean;
  neverPaysOffDebts: string[]; // debt NAMES (per engine/simulator.ts)
}

export interface ReportSaveResult {
  savedPath?: string;
  cancelled?: boolean;
}

export interface SimDebtsApi {
  list(): Promise<DebtRecord[]>;
  upsert(input: DebtInput): Promise<DebtRecord>;
  remove(id: string): Promise<{ ok: true }>; // [DEV] brief said `delete`
}

export interface SimIncomeApi {
  list(): Promise<IncomeRecord[]>;
  upsert(input: { id?: string; name: string; amountCents: number; frequency: IncomeFrequency }): Promise<IncomeRecord>;
  remove(id: string): Promise<{ ok: true }>; // [DEV] brief said `delete`
}

export interface SimSimulateApi {
  // [DEV] brief said run({ extraPaymentCents }); actual API takes the raw number.
  run(extraPaymentCents: number): Promise<{ avalanche: SimulationResult; snowball: SimulationResult }>;
}

export interface SimReportApi {
  save(params: { format: 'csv' | 'json'; extraPaymentCents: number; defaultName: string }): Promise<ReportSaveResult>;
}

export interface SimApi {
  debts: SimDebtsApi;
  income: SimIncomeApi;
  simulate: SimSimulateApi;
  report: SimReportApi;
}

/**
 * Access the preload bridge without augmenting the global Window type,
 * so renderer typings cannot collide with Worker A's preload typings.
 */
export function getSim(): SimApi {
  const w = window as unknown as { sim?: SimApi };
  if (!w.sim) {
    throw new Error(
      'The sim bridge (window.sim) is unavailable. This app must run inside its Electron shell.',
    );
  }
  return w.sim;
}

export const DISCLAIMER = 'Scenarios only \u2014 not financial advice.';
