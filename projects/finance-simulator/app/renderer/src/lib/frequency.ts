// Frequency -> monthly-income math.
// One-time income is deliberately excluded from the monthly total.

import type { IncomeFrequency, IncomeRecord } from '../types';

/** Factor to convert one period's amount into a monthly amount. */
export const MONTHLY_FACTOR: Record<IncomeFrequency, number> = {
  monthly: 1,
  biweekly: 26 / 12,
  weekly: 52 / 12,
  once: 0,
};

export function monthlyEquivalentCents(amountCents: number, frequency: IncomeFrequency): number {
  return Math.round(amountCents * MONTHLY_FACTOR[frequency]);
}

/** Sum of all recurring income expressed as monthly cents. 'once' entries are excluded. */
export function monthlyIncomeTotalCents(records: Array<Pick<IncomeRecord, 'amountCents' | 'frequency'>>): number {
  return records.reduce((sum, r) => sum + monthlyEquivalentCents(r.amountCents, r.frequency), 0);
}

/** Sum of all minimum payments as monthly cents. */
export function monthlyMinimumsTotalCents(minPaymentCents: number[]): number {
  return minPaymentCents.reduce((sum, c) => sum + c, 0);
}
