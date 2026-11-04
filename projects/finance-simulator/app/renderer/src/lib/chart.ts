// Chart data transforms: turn SimulationResult monthly series into SVG-ready points.

import type { MonthlyPoint } from '../types';

export interface ChartPoint {
  x: number;
  y: number;
}

/**
 * Build an SVG polyline `points` string for a monthly balance series.
 * x maps each point's own `month` across the width against a shared
 * maximum month (see chartMaxMonth): month 1 sits at x=0 and the shared
 * final month at x=width, so two strategies with different payoff
 * horizons do NOT both stretch to the right edge — the earlier payoff
 * visibly ends earlier. y maps balance 0..maxBalanceCents down the
 * height (SVG y grows downward).
 *
 * `maxMonth` defaults to the series' own last month (single-series use).
 * Callers plotting several series must pass the shared maximum so the
 * x-axis means the same month for every line.
 */
export function balancePolyline(
  monthly: MonthlyPoint[],
  width: number,
  height: number,
  maxBalanceCents: number,
  maxMonth?: number,
): string {
  if (monthly.length === 0 || width <= 0 || height <= 0) return '';
  const maxBalance = Math.max(1, maxBalanceCents);
  const ownMaxMonth = monthly.reduce((acc, m) => Math.max(acc, m.month), 0);
  const span = Math.max(1, (maxMonth ?? ownMaxMonth) - 1);
  const pts: string[] = monthly.map((m) => {
    const x = ((m.month - 1) / span) * width;
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

/** Shared x-axis maximum month so avalanche and snowball series share one time axis. */
export function chartMaxMonth(series: MonthlyPoint[][]): number {
  let max = 0;
  for (const s of series) {
    for (const m of s) {
      if (m.month > max) max = m.month;
    }
  }
  return max;
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
