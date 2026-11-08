import { describe, expect, it } from 'vitest';
import { simulateDebts, MAX_MONTHS } from '../../engine/simulator';
import { formatUnpaidWithinHorizon, SIMULATION_HORIZON_MONTHS } from '../../renderer/src/lib/money';

// Regression (Codex PR #8, cycle 2): the result banner lumped every debt
// still open at the 1,200-month cap together as "Never — minimums don't
// cover interest". That is wrong for a debt that simply needs longer than
// the horizon: $1,201 at 0% APR paid $1/month has no interest at all and
// still owes $1 after 1,200 months — it would pay off in month 1,201.
// The banner may only claim "not paid off within the simulation horizon".
describe('unpaid-within-horizon banner', () => {
  it('keeps the renderer horizon in sync with the engine cap', () => {
    expect(SIMULATION_HORIZON_MONTHS).toBe(MAX_MONTHS);
  });

  it('reproduces the counterexample: 0% APR debt outliving the horizon', () => {
    const result = simulateDebts(
      [{ id: 'slow', name: 'Slow', balanceCents: 120_100, aprPercent: 0, minPaymentCents: 100 }],
      0,
      'avalanche',
    );
    expect(result.monthly).toHaveLength(MAX_MONTHS);
    // $1.00 remains after 1,200 months, so it is still open at the cap...
    expect(result.monthly[MAX_MONTHS - 1]?.totalBalanceCents).toBe(100);
    expect(result.neverPaysOff).toBe(true);
    expect(result.neverPaysOffDebts).toEqual(['Slow']);
    // ...but nothing about interest or permanent non-payment follows.
    const banner = formatUnpaidWithinHorizon(result.neverPaysOffDebts);
    expect(banner).toContain('Not paid off within the 1,200-month simulation horizon');
    expect(banner).toContain('Slow');
    expect(banner).not.toMatch(/never/i);
    expect(banner).not.toMatch(/interest/i);
  });

  it('names no unsupported cause for a genuine interest treadmill either', () => {
    const banner = formatUnpaidWithinHorizon(['Treadmill']);
    expect(banner).not.toMatch(/never/i);
    expect(banner).not.toMatch(/minimums don.t cover interest/i);
    expect(banner).toContain('Treadmill');
  });

  it('omits the debt list when no names are supplied', () => {
    const banner = formatUnpaidWithinHorizon([]);
    expect(banner).toContain('Not paid off within');
    expect(banner).not.toContain('still open');
    expect(banner.endsWith('.')).toBe(true);
  });
});
