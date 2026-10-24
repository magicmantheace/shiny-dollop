// Renderer-side copy of the report layout contract.
// Authoritative implementation: Worker A — app/electron/report.ts (main process).
// Actual file export runs in main via sim.report.save; these helpers mirror
// the layout so renderer-side tests and docs stay pinned to the same contract.
//
// CSV column contract (per-debt, per-month rows):
//   strategy,debt,month,balance_cents,interest_cents,payment_cents
// where `debt` is the debt name and balances are integer cents.

/** Must stay identical to REPORT_CSV_HEADER in app/electron/report.ts. */
export const REPORT_CSV_HEADER = 'strategy,debt,month,balance_cents,interest_cents,payment_cents';

export interface ReportRowInput {
  strategy: 'avalanche' | 'snowball';
  debt: string; // debt name
  month: number;
  balanceCents: number;
  interestCents: number;
  paymentCents: number;
}

export function csvEscape(value: string): string {
  return /[",\n\r]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

export function reportRowToCsv(row: ReportRowInput): string {
  return [
    row.strategy,
    csvEscape(row.debt),
    String(row.month),
    String(row.balanceCents),
    String(row.interestCents),
    String(row.paymentCents),
  ].join(',');
}

/** Full CSV text: header + one row per (strategy, debt, month). */
export function reportRowsToCsv(rows: ReportRowInput[]): string {
  return [REPORT_CSV_HEADER, ...rows.map(reportRowToCsv)].join('\n') + '\n';
}

export const DISCLAIMER = 'Scenarios only \u2014 not financial advice.';
