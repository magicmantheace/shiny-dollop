/**
 * Scenario report writer (runs in main, has filesystem access).
 *
 * CSV column contract (documented here and in the header row itself):
 *   strategy,debt,month,balance_cents,interest_cents,payment_cents
 * One row per strategy x debt x simulated month, for both avalanche and
 * snowball. balance_cents is the end-of-month balance.
 *
 * JSON format: { generatedAt, extraPaymentCents, debts, income, avalanche, snowball }.
 */
import type { DatabaseSync } from 'node:sqlite';
import fsp from 'node:fs/promises';
import {
  reportRows,
  simulateDebts,
  type ReportRow,
  type SimulationResult,
} from '../engine/simulator';
import { listDebts, listIncomeSources } from '../db/records';
import {
  debtRecordToInput,
  type DebtRecord,
  type IncomeRecord,
} from '../shared/types';

export const REPORT_CSV_HEADER = 'strategy,debt,month,balance_cents,interest_cents,payment_cents';

export interface ScenarioData {
  debts: DebtRecord[];
  income: IncomeRecord[];
  avalanche: SimulationResult;
  snowball: SimulationResult;
  extraPaymentCents: number;
}

export function loadScenario(db: DatabaseSync, extraPaymentCents: number): ScenarioData {
  const debts = listDebts(db);
  const income = listIncomeSources(db);
  const inputs = debts.map(debtRecordToInput);
  return {
    debts,
    income,
    avalanche: simulateDebts(inputs, extraPaymentCents, 'avalanche'),
    snowball: simulateDebts(inputs, extraPaymentCents, 'snowball'),
    extraPaymentCents,
  };
}

function csvEscape(value: string): string {
  return /[",\n\r]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** Build every CSV row (both strategies). Deterministic given the inputs. */
export function buildCsvRows(scenario: ScenarioData): string[] {
  const rows: string[] = [REPORT_CSV_HEADER];
  const inputs = scenario.debts.map(debtRecordToInput);
  for (const strategy of ['avalanche', 'snowball'] as const) {
    const detail: ReportRow[] = reportRows(inputs, scenario.extraPaymentCents, strategy);
    for (const r of detail) {
      rows.push(
        [
          r.strategy,
          csvEscape(r.debt),
          String(r.month),
          String(r.balanceCents),
          String(r.interestCents),
          String(r.paymentCents),
        ].join(','),
      );
    }
  }
  return rows;
}

export function buildCsv(scenario: ScenarioData): string {
  return buildCsvRows(scenario).join('\n') + '\n';
}

export function buildJson(scenario: ScenarioData): string {
  return (
    JSON.stringify(
      {
        generatedAt: new Date().toISOString(),
        extraPaymentCents: scenario.extraPaymentCents,
        debts: scenario.debts,
        income: scenario.income,
        avalanche: scenario.avalanche,
        snowball: scenario.snowball,
      },
      null,
      2,
    ) + '\n'
  );
}

/** Write the report file from main. outPath is validated by the caller. */
export async function writeReportFile(
  db: DatabaseSync,
  format: 'csv' | 'json',
  extraPaymentCents: number,
  outPath: string,
): Promise<string> {
  const scenario = loadScenario(db, extraPaymentCents);
  const content = format === 'csv' ? buildCsv(scenario) : buildJson(scenario);
  await fsp.writeFile(outPath, content, 'utf8');
  return outPath;
}
