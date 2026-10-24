/**
 * Engine tests. Every fixture is synthetic; the engine is pure (no I/O),
 * so these run anywhere with no database, no Electron, no network.
 */
import { describe, expect, it } from 'vitest';
import {
  MAX_MONTHS,
  monthlyInterestCents,
  reportRows,
  simulateDebts,
  type DebtInput,
  type Strategy,
} from '../../engine/simulator';

function debt(overrides: Partial<DebtInput> & { name: string }): DebtInput {
  return {
    id: overrides.id ?? overrides.name.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
    name: overrides.name,
    balanceCents: overrides.balanceCents ?? 0,
    aprPercent: overrides.aprPercent ?? 0,
    minPaymentCents: overrides.minPaymentCents ?? 0,
  };
}

/** 3-debt fixture where avalanche and snowball choose different targets. */
function threeDebtFixture(): DebtInput[] {
  return [
    debt({ name: 'Card A', balanceCents: 400000, aprPercent: 24, minPaymentCents: 8000 }),
    debt({ name: 'Card B', balanceCents: 200000, aprPercent: 12, minPaymentCents: 5000 }),
    debt({ name: 'Loan C', balanceCents: 600000, aprPercent: 6, minPaymentCents: 12000 }),
  ];
}

function payoffOf(resultDebts: { name: string; payoffMonth: number | null }[], name: string): number {
  const found = resultDebts.find((d) => d.name === name);
  expect(found).toBeDefined();
  expect(found?.payoffMonth).not.toBeNull();
  return found?.payoffMonth as number;
}

describe('monthlyInterestCents', () => {
  it('computes the worked example: $5,000 @ 19.99% -> 8329c first month', () => {
    // round(500000 * 0.1999 / 12) = round(8329.1666...) = 8329
    expect(monthlyInterestCents(500000, 19.99)).toBe(8329);
  });

  it('rounds half up', () => {
    // 150 * 12 / 1200 = 1.5 -> 2 ; 50 * 12 / 1200 = 0.5 -> 1
    expect(monthlyInterestCents(150, 12)).toBe(2);
    expect(monthlyInterestCents(50, 12)).toBe(1);
  });

  it('returns 0 for zero balance or zero APR', () => {
    expect(monthlyInterestCents(0, 19.99)).toBe(0);
    expect(monthlyInterestCents(500000, 0)).toBe(0);
  });
});

describe('worked amortization example', () => {
  const card = debt({ name: 'Card', balanceCents: 500000, aprPercent: 19.99, minPaymentCents: 12500 });

  it('applies interest before the first payment: month 1 ends at 495829c', () => {
    const result = simulateDebts([card], 0, 'avalanche');
    // 500000 + 8329 interest - 12500 minimum = 495829
    expect(result.monthly[0]?.totalBalanceCents).toBe(495829);
    expect(result.monthly[0]?.totalPaidCents).toBe(12500);
  });

  it('pays off fully with a zero final balance', () => {
    const result = simulateDebts([card], 0, 'avalanche');
    expect(result.neverPaysOff).toBe(false);
    expect(result.monthsToPayoff).toBe(result.monthly.length);
    const last = result.monthly[result.monthly.length - 1];
    expect(last?.totalBalanceCents).toBe(0);
  });

  it('keeps totals consistent: totalPaid = principal + interest = sum of schedule payments', () => {
    const result = simulateDebts([card], 0, 'avalanche');
    const scheduled = result.monthly.reduce((s, m) => s + m.totalPaidCents, 0);
    expect(result.totalPaidCents).toBe(scheduled);
    expect(result.totalPaidCents).toBe(500000 + result.totalInterestCents);
    expect(result.totalInterestCents).toBe(result.debts[0]?.interestPaidCents);
    expect(result.debts[0]?.totalPaidCents).toBe(result.totalPaidCents);
  });

  it('records payoffMonth for the debt and monthsToPayoff overall', () => {
    const result = simulateDebts([card], 0, 'avalanche');
    expect(result.debts[0]?.payoffMonth).toBe(result.monthsToPayoff);
  });
});

describe('zero-interest debt', () => {
  it('pays $1,000 @ 0% with $100 minimums in exactly 10 months, no interest', () => {
    const result = simulateDebts(
      [debt({ name: 'Zero', balanceCents: 100000, aprPercent: 0, minPaymentCents: 10000 })],
      0,
      'snowball',
    );
    expect(result.monthsToPayoff).toBe(10);
    expect(result.totalInterestCents).toBe(0);
    expect(result.totalPaidCents).toBe(100000);
    expect(result.debts[0]?.payoffMonth).toBe(10);
    expect(result.strategy).toBe('snowball');
  });
});

describe('validation', () => {
  const base = debt({ name: 'Card', balanceCents: 100000, aprPercent: 10, minPaymentCents: 5000 });

  it('rejects APR above 100', () => {
    expect(() => simulateDebts([{ ...base, aprPercent: 100.01 }], 0, 'avalanche')).toThrow(Error);
  });

  it('accepts APR exactly 100', () => {
    expect(() => simulateDebts([{ ...base, aprPercent: 100 }], 0, 'avalanche')).not.toThrow();
  });

  it('rejects negative APR', () => {
    expect(() => simulateDebts([{ ...base, aprPercent: -0.01 }], 0, 'avalanche')).toThrow(Error);
  });

  it('rejects negative and non-integer cents', () => {
    expect(() => simulateDebts([{ ...base, balanceCents: -1 }], 0, 'avalanche')).toThrow(Error);
    expect(() => simulateDebts([{ ...base, balanceCents: 100.5 }], 0, 'avalanche')).toThrow(Error);
    expect(() => simulateDebts([{ ...base, minPaymentCents: -1 }], 0, 'avalanche')).toThrow(Error);
  });

  it('rejects negative or non-integer extra payment', () => {
    expect(() => simulateDebts([base], -1, 'avalanche')).toThrow(Error);
    expect(() => simulateDebts([base], 10.5, 'avalanche')).toThrow(Error);
  });

  it('rejects empty and over-long names', () => {
    expect(() => simulateDebts([{ ...base, name: '' }], 0, 'avalanche')).toThrow(Error);
    expect(() => simulateDebts([{ ...base, name: 'x'.repeat(101) }], 0, 'avalanche')).toThrow(Error);
  });

  it('accepts a 100-character name and an empty id is rejected', () => {
    expect(() =>
      simulateDebts([{ ...base, name: 'x'.repeat(100) }], 0, 'avalanche'),
    ).not.toThrow();
    expect(() => simulateDebts([{ ...base, id: '' }], 0, 'avalanche')).toThrow(Error);
  });

  it('rejects an unknown strategy', () => {
    expect(() => simulateDebts([base], 0, 'bogus' as Strategy)).toThrow(Error);
  });
});

describe('never pays off', () => {
  it('flags neverPaysOff when minimums do not cover monthly interest', () => {
    // $10,000 @ 24%: monthly interest = 20000c > $100 minimum -> balance grows forever
    const result = simulateDebts(
      [debt({ name: 'Treadmill', balanceCents: 1000000, aprPercent: 24, minPaymentCents: 10000 })],
      0,
      'avalanche',
    );
    expect(result.neverPaysOff).toBe(true);
    expect(result.monthsToPayoff).toBeNull();
    expect(result.neverPaysOffDebts).toEqual(['Treadmill']);
    expect(result.monthly.length).toBe(MAX_MONTHS);
    expect(result.debts[0]?.payoffMonth).toBeNull();
  });

  it('applies interest before payments: balance grows even with a $0 minimum', () => {
    const result = simulateDebts(
      [debt({ name: 'Stall', balanceCents: 100000, aprPercent: 12, minPaymentCents: 0 })],
      0,
      'snowball',
    );
    // month 1: 100000 + 1000 interest - 0 paid = 101000
    expect(result.monthly[0]?.totalBalanceCents).toBe(101000);
    expect(result.neverPaysOff).toBe(true);
  });
});

describe('overpayment', () => {
  it('ignores leftover extra once the balance is exactly paid', () => {
    const result = simulateDebts(
      [debt({ name: 'Tiny', balanceCents: 5000, aprPercent: 12, minPaymentCents: 0 })],
      100000,
      'avalanche',
    );
    // interest 50c first, then the 100000c extra pays 5050c exactly; the rest is ignored
    expect(result.debts[0]?.payoffMonth).toBe(1);
    expect(result.debts[0]?.interestPaidCents).toBe(50);
    expect(result.debts[0]?.totalPaidCents).toBe(5050);
    expect(result.monthsToPayoff).toBe(1);
    const last = result.monthly[result.monthly.length - 1];
    expect(last?.totalBalanceCents).toBe(0);
  });

  it('caps a minimum above the balance at the amount owed', () => {
    const result = simulateDebts(
      [debt({ name: 'Tiny', balanceCents: 5000, aprPercent: 0, minPaymentCents: 10000 })],
      0,
      'avalanche',
    );
    expect(result.debts[0]?.payoffMonth).toBe(1);
    expect(result.totalPaidCents).toBe(5000);
  });
});

describe('snowballing freed minimums', () => {
  it('rolls paid-off minimums into the extra pool', () => {
    const result = simulateDebts(
      [
        debt({ name: 'Small', balanceCents: 50000, aprPercent: 0, minPaymentCents: 50000 }),
        debt({ name: 'Big', balanceCents: 100000, aprPercent: 0, minPaymentCents: 10000 }),
      ],
      0,
      'snowball',
    );
    expect(payoffOf(result.debts, 'Small')).toBe(1);
    // month 2+: Big gets its own 10000 minimum + Small's freed 50000 = 60000/mo
    expect(payoffOf(result.debts, 'Big')).toBe(3);
  });
});

describe('target ordering', () => {
  it('avalanche pays highest APR first and costs less interest than snowball', () => {
    const extra = 50000;
    const avalanche = simulateDebts(threeDebtFixture(), extra, 'avalanche');
    const snowball = simulateDebts(threeDebtFixture(), extra, 'snowball');
    expect(avalanche.totalInterestCents).toBeLessThan(snowball.totalInterestCents);
    expect(payoffOf(avalanche.debts, 'Card A')).toBeLessThan(payoffOf(avalanche.debts, 'Card B'));
    expect(payoffOf(avalanche.debts, 'Card B')).toBeLessThan(payoffOf(avalanche.debts, 'Loan C'));
  });

  it('snowball pays lowest balance first', () => {
    const snowball = simulateDebts(threeDebtFixture(), 50000, 'snowball');
    expect(payoffOf(snowball.debts, 'Card B')).toBeLessThan(payoffOf(snowball.debts, 'Card A'));
    expect(payoffOf(snowball.debts, 'Card A')).toBeLessThan(payoffOf(snowball.debts, 'Loan C'));
  });

  it('avalanche breaks APR ties by lowest balance', () => {
    const result = simulateDebts(
      [
        debt({ name: 'Big', balanceCents: 300000, aprPercent: 10, minPaymentCents: 5000 }),
        debt({ name: 'Small', balanceCents: 100000, aprPercent: 10, minPaymentCents: 5000 }),
      ],
      20000,
      'avalanche',
    );
    expect(payoffOf(result.debts, 'Small')).toBeLessThan(payoffOf(result.debts, 'Big'));
  });

  it('snowball breaks balance ties by highest APR', () => {
    // 100c @ 12% and 100c @ 6% both accrue 1c of interest, so the balances are
    // still exactly tied (101c) when the extra-payment target is chosen.
    // Extra of 101c pays exactly one of them in month 1.
    const result = simulateDebts(
      [
        debt({ name: 'High', balanceCents: 100, aprPercent: 12, minPaymentCents: 0 }),
        debt({ name: 'Low', balanceCents: 100, aprPercent: 6, minPaymentCents: 0 }),
      ],
      101,
      'snowball',
    );
    expect(payoffOf(result.debts, 'High')).toBe(1);
    expect(payoffOf(result.debts, 'Low')).toBeGreaterThan(1);
  });
});

describe('determinism and edge cases', () => {
  it('two runs are byte-identical', () => {
    const a = JSON.stringify(simulateDebts(threeDebtFixture(), 50000, 'avalanche'));
    const b = JSON.stringify(simulateDebts(threeDebtFixture(), 50000, 'avalanche'));
    expect(a).toBe(b);
  });

  it('empty debts produce zeros', () => {
    const result = simulateDebts([], 0, 'avalanche');
    expect(result.monthsToPayoff).toBe(0);
    expect(result.totalPaidCents).toBe(0);
    expect(result.totalInterestCents).toBe(0);
    expect(result.debts).toEqual([]);
    expect(result.monthly).toEqual([]);
    expect(result.neverPaysOff).toBe(false);
    expect(result.neverPaysOffDebts).toEqual([]);
  });

  it('a zero-balance debt is already paid (payoffMonth 0)', () => {
    const result = simulateDebts(
      [debt({ name: 'Zero', balanceCents: 0, aprPercent: 19.99, minPaymentCents: 10000 })],
      0,
      'avalanche',
    );
    expect(result.debts[0]?.payoffMonth).toBe(0);
    expect(result.monthsToPayoff).toBe(0);
    expect(result.monthly).toEqual([]);
  });

  it('monthsToPayoff equals the last debt payoff month', () => {
    const result = simulateDebts(
      [
        debt({ name: 'A', balanceCents: 120000, aprPercent: 0, minPaymentCents: 10000 }),
        debt({ name: 'B', balanceCents: 60000, aprPercent: 0, minPaymentCents: 10000 }),
      ],
      0,
      'snowball',
    );
    const lastPayoff = Math.max(...result.debts.map((d) => d.payoffMonth ?? 0));
    expect(result.monthsToPayoff).toBe(lastPayoff);
  });

  it('monthly array length matches monthsToPayoff when it pays off', () => {
    const result = simulateDebts(
      [debt({ name: 'A', balanceCents: 120000, aprPercent: 0, minPaymentCents: 10000 })],
      10000,
      'avalanche',
    );
    expect(result.monthly.length).toBe(result.monthsToPayoff);
  });
});

describe('long-schedule rounding drift', () => {
  it('a 30-year schedule ends at exactly 0 with consistent totals', () => {
    const principal = 25000000; // $250,000
    const apr = 6.5;
    const r = apr / 100 / 12;
    const n = 360;
    // Exact amortizing payment, rounded UP to the cent so it cannot fall short.
    const payment = Math.ceil((principal * r) / (1 - Math.pow(1 + r, -n)));
    const result = simulateDebts(
      [debt({ name: 'Mortgage', balanceCents: principal, aprPercent: apr, minPaymentCents: payment })],
      0,
      'avalanche',
    );
    expect(result.neverPaysOff).toBe(false);
    expect(result.monthsToPayoff).toBeLessThanOrEqual(360);
    const last = result.monthly[result.monthly.length - 1];
    expect(last?.totalBalanceCents).toBe(0);
    const scheduled = result.monthly.reduce((s, m) => s + m.totalPaidCents, 0);
    expect(result.totalPaidCents).toBe(scheduled);
    expect(result.totalPaidCents).toBe(principal + result.totalInterestCents);
  });
});

describe('reportRows', () => {
  it('emits one row per debt per month with the documented columns', () => {
    const rows = reportRows(
      [debt({ name: 'A', balanceCents: 100000, aprPercent: 0, minPaymentCents: 50000 })],
      0,
      'avalanche',
    );
    expect(rows.length).toBe(2); // 2 months x 1 debt
    expect(rows[0]).toEqual({
      strategy: 'avalanche',
      debt: 'A',
      month: 1,
      balanceCents: 50000,
      interestCents: 0,
      paymentCents: 50000,
    });
    expect(rows[1]?.balanceCents).toBe(0);
  });
});
