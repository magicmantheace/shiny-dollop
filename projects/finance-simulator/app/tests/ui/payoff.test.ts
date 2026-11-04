import { describe, expect, it } from 'vitest';
import { formatPayoffMonth } from '../../renderer/src/lib/money';

// Regression: the engine returns payoffMonth 0 for a zero-balance debt to mean
// "already paid" (engine/simulator.ts), and null for "still open at the
// simulation horizon". The per-debt breakdown previously lumped 0 in with
// null and labelled an already-paid debt "Never"; null was likewise
// mislabelled "Never" even though it only means the 1,200-month horizon
// was reached (Codex PR #8, cycle 2).
describe('formatPayoffMonth', () => {
  it('renders null as not within the horizon, not Never', () => {
    const label = formatPayoffMonth(null);
    expect(label).toBe('Not within horizon');
    expect(label).not.toMatch(/never/i);
  });
  it('renders 0 as already paid, not Never', () => {
    const label = formatPayoffMonth(0);
    expect(label).not.toBe('Never');
    expect(label).not.toBe(formatPayoffMonth(null));
    expect(label).toContain('Already paid');
    expect(label).toContain('0');
  });
  it('renders a positive month with its horizon', () => {
    expect(formatPayoffMonth(1)).toBe('1 (1 mo)');
    expect(formatPayoffMonth(14)).toBe('14 (1 yr 2 mo)');
  });
});
