/**
 * Deterministic pricing engine. Shared by main and tests; pure functions
 * with no I/O. All money is integer cents; all volumes are integer liters.
 *
 * Rounding rule (explicit, everywhere): half-up to the cent —
 *   result = floor(numerator / denominator + 1/2)
 * implemented as floor((2*numerator + denominator) / (2*denominator)) on
 * non-negative integers, so results are exact and platform-independent.
 */

import type {
  DocumentTotals,
  LineItem,
  QuoteParamsSnapshot,
  TaxLine,
} from './types';

/** Half-up rounding of numerator/denominator to an integer. Non-negative only. */
export function divRoundHalfUp(numerator: number, denominator: number): number {
  if (!Number.isSafeInteger(numerator) || numerator < 0) {
    throw new Error(`divRoundHalfUp: numerator must be a non-negative safe integer, got ${numerator}`);
  }
  if (!Number.isSafeInteger(denominator) || denominator <= 0) {
    throw new Error(`divRoundHalfUp: denominator must be a positive safe integer, got ${denominator}`);
  }
  // Guard against intermediate overflow: cap operands to well under 2^53/2.
  if (numerator > Number.MAX_SAFE_INTEGER / 4) {
    throw new Error('divRoundHalfUp: numerator too large');
  }
  return Math.floor((2 * numerator + denominator) / (2 * denominator));
}

/**
 * Concrete line amount: volume_liters × rate_cents_per_m3 / 1000,
 * rounded half-up to the cent.
 */
export function concreteLineCents(volumeLiters: number, rateCentsPerM3: number): number {
  return divRoundHalfUp(volumeLiters * rateCentsPerM3, 1000);
}

/** Tax on a taxable subtotal: taxable_cents × rate_bps / 10000, half-up. */
export function taxCents(taxableCents: number, rateBps: number): number {
  return divRoundHalfUp(taxableCents * rateBps, 10000);
}

/** Mileage fee: distance_tenths_km × rate_cents_per_km / 10, half-up. */
export function mileageFeeCents(distanceTenthsKm: number, rateCentsPerKm: number): number {
  return divRoundHalfUp(distanceTenthsKm * rateCentsPerKm, 10);
}

export interface PricingVolume {
  pourId: number;
  mixDesignId: string;
  liters: number;
}

export interface PricingParams {
  concreteRateCentsPerM3: number;
  smallLoadThresholdLiters: number;
  smallLoadChargeCents: number;
  smallLoadApplied: boolean;
  deliveryMode: 'flat' | 'mileage' | 'none';
  deliveryFlatCents: number;
  deliveryPerKmCents: number;
  distanceTenthsKm: number | null;
  taxes: { name: string; rateBps: number }[];
  taxExempt: boolean;
}

const MAX_SAFE_PRODUCT = Number.MAX_SAFE_INTEGER / 4;

function assertSaneParams(p: PricingParams): void {
  const ints: [string, number][] = [
    ['concreteRateCentsPerM3', p.concreteRateCentsPerM3],
    ['smallLoadThresholdLiters', p.smallLoadThresholdLiters],
    ['smallLoadChargeCents', p.smallLoadChargeCents],
    ['deliveryFlatCents', p.deliveryFlatCents],
    ['deliveryPerKmCents', p.deliveryPerKmCents],
  ];
  for (const [name, v] of ints) {
    if (!Number.isSafeInteger(v) || v < 0) {
      throw new Error(`pricing: ${name} must be a non-negative integer, got ${v}`);
    }
    if (v > MAX_SAFE_PRODUCT) throw new Error(`pricing: ${name} too large`);
  }
  for (const t of p.taxes) {
    if (!Number.isSafeInteger(t.rateBps) || t.rateBps < 0 || t.rateBps > 100000) {
      throw new Error(`pricing: invalid tax rate for ${t.name}`);
    }
  }
}

/**
 * Compute the full itemized totals for a quote or invoice.
 * Each charge appears as its own line; each tax appears as its own line.
 * Pure and deterministic: same inputs → same outputs, always.
 */
export function computeTotals(volumes: PricingVolume[], params: PricingParams): DocumentTotals {
  assertSaneParams(params);
  for (const v of volumes) {
    if (!Number.isSafeInteger(v.liters) || v.liters < 0 || v.liters > MAX_SAFE_PRODUCT) {
      throw new Error(`pricing: invalid volume for pour ${v.pourId}`);
    }
  }

  const lines: LineItem[] = [];
  let totalLiters = 0;
  for (const v of volumes) {
    totalLiters += v.liters;
    const amount = concreteLineCents(v.liters, params.concreteRateCentsPerM3);
    lines.push({
      kind: 'concrete',
      label: `Concrete — mix ${v.mixDesignId} (nominal design ID)`,
      detail: `${formatLiters(v.liters)} @ ${formatCents(params.concreteRateCentsPerM3)}/m³`,
      quantityLiters: v.liters,
      rateCentsPerM3: params.concreteRateCentsPerM3,
      amountCents: amount,
    });
  }

  if (
    params.smallLoadApplied &&
    params.smallLoadChargeCents > 0 &&
    totalLiters < params.smallLoadThresholdLiters
  ) {
    lines.push({
      kind: 'small_load',
      label: 'Small-load charge',
      detail: `under ${formatLiters(params.smallLoadThresholdLiters)} threshold (${formatLiters(totalLiters)} ordered)`,
      amountCents: params.smallLoadChargeCents,
    });
  }

  if (params.deliveryMode === 'flat' && params.deliveryFlatCents > 0) {
    lines.push({
      kind: 'delivery',
      label: 'Delivery fee (flat)',
      amountCents: params.deliveryFlatCents,
    });
  } else if (
    params.deliveryMode === 'mileage' &&
    params.distanceTenthsKm !== null &&
    params.deliveryPerKmCents > 0
  ) {
    const fee = mileageFeeCents(params.distanceTenthsKm, params.deliveryPerKmCents);
    lines.push({
      kind: 'delivery',
      label: 'Delivery fee (mileage)',
      detail: `${(params.distanceTenthsKm / 10).toFixed(1)} km @ ${formatCents(params.deliveryPerKmCents)}/km`,
      amountCents: fee,
    });
  }

  const subtotalCents = lines.reduce((s, l) => s + l.amountCents, 0);

  const taxLines: TaxLine[] = params.taxes.map((t) => ({
    name: t.name,
    rateBps: t.rateBps,
    taxableCents: subtotalCents,
    taxCents: params.taxExempt ? 0 : taxCents(subtotalCents, t.rateBps),
  }));

  const totalTax = taxLines.reduce((s, t) => s + t.taxCents, 0);
  return {
    lines,
    subtotalCents,
    taxLines,
    totalCents: subtotalCents + totalTax,
    taxExemptApplied: params.taxExempt,
  };
}

/** Build the auditable params snapshot stored with each quote. */
export function snapshotParams(
  volumes: PricingVolume[],
  params: PricingParams,
  fromDelivered: boolean,
): QuoteParamsSnapshot {
  return {
    concreteRateCentsPerM3: params.concreteRateCentsPerM3,
    smallLoadThresholdLiters: params.smallLoadThresholdLiters,
    smallLoadChargeCents: params.smallLoadChargeCents,
    smallLoadApplied: params.smallLoadApplied,
    deliveryMode: params.deliveryMode,
    deliveryFlatCents: params.deliveryFlatCents,
    deliveryPerKmCents: params.deliveryPerKmCents,
    distanceTenthsKm: params.distanceTenthsKm,
    taxes: params.taxes.map((t) => ({ name: t.name, rateBps: t.rateBps })),
    taxExempt: params.taxExempt,
    volumes: volumes.map((v) => ({ pourId: v.pourId, mixDesignId: v.mixDesignId, liters: v.liters })),
    fromDelivered,
  };
}

/** "2.500 m³" style display for a liter quantity. */
export function formatLiters(liters: number): string {
  return `${(liters / 1000).toFixed(3)} m³`;
}

/** "$180.00" style display for cents. */
export function formatCents(cents: number): string {
  const sign = cents < 0 ? '-' : '';
  const abs = Math.abs(cents);
  return `${sign}$${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`;
}
