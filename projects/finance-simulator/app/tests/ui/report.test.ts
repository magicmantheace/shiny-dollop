import { describe, expect, it } from 'vitest';
import {
  REPORT_CSV_HEADER,
  csvEscape,
  reportRowToCsv,
  reportRowsToCsv,
  type ReportRowInput,
} from '../../renderer/src/lib/report';

const row = (over: Partial<ReportRowInput> = {}): ReportRowInput => ({
  strategy: 'avalanche',
  debt: 'Visa',
  month: 1,
  balanceCents: 90000,
  interestCents: 828,
  paymentCents: 20000,
  ...over,
});

describe('REPORT_CSV_HEADER', () => {
  it('matches the main-process export contract', () => {
    // Keep in sync with REPORT_CSV_HEADER in app/electron/report.ts.
    expect(REPORT_CSV_HEADER).toBe('strategy,debt,month,balance_cents,interest_cents,payment_cents');
  });
});

describe('csvEscape', () => {
  it('leaves plain cells alone', () => {
    expect(csvEscape('Visa')).toBe('Visa');
  });
  it('quotes cells containing commas or quotes', () => {
    expect(csvEscape('Store, card')).toBe('"Store, card"');
    expect(csvEscape('The "best" card')).toBe('"The ""best"" card"');
  });
});

describe('reportRowToCsv', () => {
  it('renders one per-debt per-month row in cents', () => {
    expect(reportRowToCsv(row())).toBe('avalanche,Visa,1,90000,828,20000');
  });
  it('escapes debt names with commas', () => {
    expect(reportRowToCsv(row({ debt: 'Store, card' }))).toContain('"Store, card"');
  });
});

describe('reportRowsToCsv', () => {
  it('starts with the header and ends with a newline', () => {
    const csv = reportRowsToCsv([row(), row({ strategy: 'snowball', month: 2 })]);
    const lines = csv.split('\n');
    expect(lines[0]).toBe(REPORT_CSV_HEADER);
    expect(lines[1]).toBe('avalanche,Visa,1,90000,828,20000');
    expect(lines[2]).toBe('snowball,Visa,2,90000,828,20000');
    expect(csv.endsWith('\n')).toBe(true);
  });
  it('produces just the header for an empty row list', () => {
    expect(reportRowsToCsv([])).toBe(REPORT_CSV_HEADER + '\n');
  });
});
