import { describe, expect, it } from 'vitest';
import {
  MONTHLY_FACTOR,
  monthlyEquivalentCents,
  monthlyIncomeTotalCents,
} from '../../renderer/src/lib/frequency';

describe('MONTHLY_FACTOR', () => {
  it('annualizes biweekly and weekly correctly', () => {
    expect(MONTHLY_FACTOR.biweekly).toBeCloseTo(26 / 12, 10);
    expect(MONTHLY_FACTOR.weekly).toBeCloseTo(52 / 12, 10);
  });
  it('excludes one-time income from the monthly total', () => {
    expect(MONTHLY_FACTOR.once).toBe(0);
  });
});

describe('monthlyEquivalentCents', () => {
  it('passes monthly amounts through unchanged', () => {
    expect(monthlyEquivalentCents(300000, 'monthly')).toBe(300000);
  });
  it('converts a $1,557.51 biweekly paycheck', () => {
    // 155751 * 26 / 12 = 337460.5 -> rounds to 337461
    expect(monthlyEquivalentCents(155751, 'biweekly')).toBe(337461);
  });
});

describe('monthlyIncomeTotalCents', () => {
  it('sums recurring sources and skips one-time entries', () => {
    const total = monthlyIncomeTotalCents([
      { amountCents: 155751, frequency: 'biweekly' },
      { amountCents: 50000, frequency: 'monthly' },
      { amountCents: 100000, frequency: 'once' },
    ]);
    expect(total).toBe(337461 + 50000);
  });
  it('returns 0 for no records', () => {
    expect(monthlyIncomeTotalCents([])).toBe(0);
  });
});
