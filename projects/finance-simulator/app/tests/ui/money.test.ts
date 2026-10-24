import { describe, expect, it } from 'vitest';
import { centsToDollars, dollarsToCents, formatHorizon, formatUSD } from '../../renderer/src/lib/money';

describe('dollarsToCents', () => {
  it('parses a plain dollar amount', () => {
    expect(dollarsToCents('5000.00')).toBe(500000);
  });
  it('parses without decimals', () => {
    expect(dollarsToCents('42')).toBe(4200);
  });
  it('parses a single decimal digit', () => {
    expect(dollarsToCents('12.5')).toBe(1250);
  });
  it('strips $ and commas', () => {
    expect(dollarsToCents('$1,557.51')).toBe(155751);
  });
  it('returns null for empty input', () => {
    expect(dollarsToCents('   ')).toBeNull();
  });
  it('returns null for garbage', () => {
    expect(dollarsToCents('abc')).toBeNull();
    expect(dollarsToCents('12.345')).toBeNull();
    expect(dollarsToCents('-50')).toBeNull();
  });
});

describe('centsToDollars', () => {
  it('formats with two decimals', () => {
    expect(centsToDollars(500000)).toBe('5000.00');
  });
  it('pads single-cent values', () => {
    expect(centsToDollars(5)).toBe('0.05');
  });
  it('handles zero and negative', () => {
    expect(centsToDollars(0)).toBe('0.00');
    expect(centsToDollars(-125)).toBe('-1.25');
  });
});

describe('formatUSD', () => {
  it('formats as US dollars', () => {
    expect(formatUSD(500000)).toBe('$5,000.00');
  });
});

describe('formatHorizon', () => {
  it('formats months under a year', () => {
    expect(formatHorizon(8)).toBe('8 mo');
  });
  it('formats years and leftover months', () => {
    expect(formatHorizon(14)).toBe('1 yr 2 mo');
  });
  it('formats exact years without month part', () => {
    expect(formatHorizon(24)).toBe('2 yr');
  });
  it('returns a dash for non-positive input', () => {
    expect(formatHorizon(0)).toBe('—');
  });
});
