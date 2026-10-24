/**
 * Report builder tests. buildCsv/buildJson are pure given a scenario;
 * fixtures are synthetic.
 */
import { DatabaseSync } from 'node:sqlite';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { runMigrations } from '../../db/migrations';
import { upsertDebt, upsertIncomeSource } from '../../db/records';
import {
  buildCsv,
  buildCsvRows,
  buildJson,
  loadScenario,
  REPORT_CSV_HEADER,
} from '../../electron/report';

let db: DatabaseSync;

beforeEach(() => {
  db = new DatabaseSync(':memory:');
  runMigrations(db);
  upsertDebt(db, { name: 'Card', balanceCents: 100000, aprPercent: 0, minPaymentCents: 50000 });
  upsertIncomeSource(db, { name: 'Pay', amountCents: 155751, frequency: 'biweekly' });
});

afterEach(() => {
  db.close();
});

describe('CSV report', () => {
  it('uses the documented column header', () => {
    expect(REPORT_CSV_HEADER).toBe('strategy,debt,month,balance_cents,interest_cents,payment_cents');
    expect(buildCsv(loadScenario(db, 0)).split('\n')[0]).toBe(REPORT_CSV_HEADER);
  });

  it('emits one row per strategy x debt x month', () => {
    const scenario = loadScenario(db, 0);
    const rows = buildCsvRows(scenario);
    // 1 debt, 2 months per strategy, 2 strategies + header
    expect(rows.length).toBe(1 + 2 * 2);
    expect(rows[1]).toBe('avalanche,Card,1,50000,0,50000');
    expect(rows[2]).toBe('avalanche,Card,2,0,0,50000');
    expect(rows[3]).toBe('snowball,Card,1,50000,0,50000');
  });

  it('escapes debt names containing commas', () => {
    upsertDebt(db, { name: 'Card, Visa', balanceCents: 1000, aprPercent: 0, minPaymentCents: 1000 });
    const rows = buildCsvRows(loadScenario(db, 0));
    expect(rows.some((r) => r.includes('"Card, Visa"'))).toBe(true);
  });
});

describe('JSON report', () => {
  it('contains both strategies plus debts and income', () => {
    const parsed = JSON.parse(buildJson(loadScenario(db, 25000))) as {
      extraPaymentCents: number;
      debts: unknown[];
      income: unknown[];
      avalanche: { strategy: string };
      snowball: { strategy: string };
    };
    expect(parsed.extraPaymentCents).toBe(25000);
    expect(parsed.debts.length).toBeGreaterThanOrEqual(1);
    expect(parsed.income.length).toBe(1);
    expect(parsed.avalanche.strategy).toBe('avalanche');
    expect(parsed.snowball.strategy).toBe('snowball');
  });
});
