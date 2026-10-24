import { describe, expect, it } from 'vitest';
import { balancePolyline, chartMaxBalance, downsample } from '../../renderer/src/lib/chart';
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

describe('chartMaxBalance', () => {
  it('returns the shared ceiling across strategies', () => {
    expect(chartMaxBalance([[month(1, 9000)], [month(1, 12000)]])).toBe(12000);
  });
  it('returns 0 for empty input', () => {
    expect(chartMaxBalance([])).toBe(0);
  });
});
