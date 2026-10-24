// Chart data transforms: turn SimulationResult monthly series into SVG-ready points.

import type { MonthlyPoint } from '../types';

export interface ChartPoint {
  x: number;
  y: number;
}

/**
 * Build an SVG polyline `points` string for a monthly balance series.
 * x maps month index 0..maxMonthIndex across the width; y maps balance
 * 0..maxBalanceCents down the height (SVG y grows downward).
 */
export function balancePolyline(
  monthly: MonthlyPoint[],
  width: number,
  height: number,
  maxBalanceCents: number,
): string {
  if (monthly.length === 0 || width <= 0 || height <= 0) return '';
  const maxBalance = Math.max(1, maxBalanceCents);
  const maxMonthIndex = Math.max(1, monthly.length - 1);
  const pts: string[] = monthly.map((m, i) => {
    const x = (i / maxMonthIndex) * width;
    const y = height - (Math.max(0, m.totalBalanceCents) / maxBalance) * height;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });
  return pts.join(' ');
}

/** Downsample a monthly series to at most `maxPoints` points (keeps first and last). */
export function downsample(monthly: MonthlyPoint[], maxPoints: number): MonthlyPoint[] {
  if (monthly.length <= maxPoints) return monthly;
  const step = (monthly.length - 1) / (maxPoints - 1);
  const out: MonthlyPoint[] = [];
  for (let i = 0; i < maxPoints; i++) {
    const m = monthly[Math.round(i * step)];
    if (m !== undefined) out.push(m);
  }
  return out;
}

/** Shared y-axis ceiling so avalanche and snowball series are visually comparable. */
export function chartMaxBalance(series: MonthlyPoint[][]): number {
  let max = 0;
  for (const s of series) {
    for (const m of s) {
      if (m.totalBalanceCents > max) max = m.totalBalanceCents;
    }
  }
  return max;
}
