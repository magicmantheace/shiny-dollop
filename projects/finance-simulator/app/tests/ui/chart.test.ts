import { describe, expect, it } from 'vitest';
import { balancePolyline, chartMaxBalance, chartMaxMonth, downsample } from '../../renderer/src/lib/chart';
import type { MonthlyPoint } from '../../renderer/src/types';

function month(month: number, totalBalanceCents: number): MonthlyPoint {
  return { month, totalBalanceCents, totalPaidCents: 0 };
}

describe('balancePolyline', () => {
  it('produces one point per month', () => {
    const pts = balancePolyline([month(1, 1000), month(2, 500), month(3, 0)], 300, 150, 1000);
    expect(pts.split(' ')).toHaveLength(3);
  });
  it('maps the max balance to the top and zero to the bottom', () => {
    const pts = balancePolyline([month(1, 1000), month(2, 0)], 200, 100, 1000).split(' ');
    expect(pts[0]).toBe('0.00,0.00');
    expect(pts[1]).toBe('200.00,100.00');
  });
  it('returns empty string for empty series', () => {
    expect(balancePolyline([], 200, 100, 1000)).toBe('');
  });
});

describe('downsample', () => {
  it('keeps short series intact', () => {
    const series = [month(1, 1), month(2, 2)];
    expect(downsample(series, 100)).toEqual(series);
  });
  it('keeps first and last points when downsampling', () => {
    const series = Array.from({ length: 60 }, (_, i) => month(i + 1, 60000 - i * 1000));
    const down = downsample(series, 13);
    expect(down).toHaveLength(13);
    expect(down[0].month).toBe(1);
    expect(down[down.length - 1].month).toBe(60);
  });
});

// Regression (Codex PR #8, round 1): BalanceChart plotted each strategy
// against its OWN series length, so a 3-month and a 5-month payoff both
// ended at the right edge and looked identical. x must come from each
// point's month against a maximum month shared by both strategies.
describe('balancePolyline shared month axis', () => {
  const width = 400;
  const short = [month(1, 3000), month(2, 2000), month(3, 0)]; // pays off month 3
  const long = [month(1, 5000), month(2, 4000), month(3, 3000), month(4, 1500), month(5, 0)]; // month 5

  it('ends the earlier payoff before the right edge on a shared axis', () => {
    const sharedMax = chartMaxMonth([short, long]);
    const shortPts = balancePolyline(short, width, 100, 5000, sharedMax).split(' ');
    const longPts = balancePolyline(long, width, 100, 5000, sharedMax).split(' ');
    // Month 3 of a shared 5-month axis: (3-1)/(5-1) * 400 = 200 — half width.
    expect(shortPts[shortPts.length - 1]).toBe('200.00,100.00');
    expect(longPts[longPts.length - 1]).toBe('400.00,100.00');
  });

  it('aligns the same month at the same x across different-length series', () => {
    const sharedMax = chartMaxMonth([short, long]);
    const shortPts = balancePolyline(short, width, 100, 5000, sharedMax).split(' ');
    const longPts = balancePolyline(long, width, 100, 5000, sharedMax).split(' ');
    expect(shortPts[2].split(',')[0]).toBe(longPts[2].split(',')[0]); // both are month 3
    expect(shortPts[0].split(',')[0]).toBe('0.00'); // month 1 anchors the axis start
  });

  it('uses each point’s month, not its position, after downsampling', () => {
    const sparse = downsample(long, 3); // months 1, 3, 5
    const pts = balancePolyline(sparse, width, 100, 5000, chartMaxMonth([long])).split(' ');
    expect(pts.map((p) => p.split(',')[0])).toEqual(['0.00', '200.00', '400.00']);
  });
});

describe('chartMaxMonth', () => {
  it('returns the latest month across strategies', () => {
    expect(chartMaxMonth([[month(1, 1), month(3, 0)], [month(1, 1), month(5, 0)]])).toBe(5);
  });
  it('returns 0 for empty input', () => {
    expect(chartMaxMonth([])).toBe(0);
    expect(chartMaxMonth([[]])).toBe(0);
  });
});

describe('chartMaxBalance', () => {
  it('returns the shared ceiling across strategies', () => {
    expect(chartMaxBalance([[month(1, 9000)], [month(1, 12000)]])).toBe(12000);
  });
  it('returns 0 for empty input', () => {
    expect(chartMaxBalance([])).toBe(0);
  });
});
