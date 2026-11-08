/**
 * Typed units for the Volumetric Concrete Mix Calculator.
 *
 * All internal math is done in base units (cubic metres for volume,
 * kilograms for mass). Conversions are exact constants; display rounding
 * happens only at presentation/export time so calculations stay
 * deterministic: identical inputs always produce identical outputs.
 */

export type VolumeUnit = 'm3' | 'L' | 'yd3';
export type MassUnit = 'kg' | 't' | 'lb';

export const VOLUME_UNITS: readonly VolumeUnit[] = ['m3', 'L', 'yd3'];
export const MASS_UNITS: readonly MassUnit[] = ['kg', 't', 'lb'];

/** Multiply a value in the given volume unit to get cubic metres. */
export const VOLUME_TO_M3: Record<VolumeUnit, number> = {
  m3: 1,
  L: 0.001,
  yd3: 0.764554857984,
};

/** Multiply a value in the given mass unit to get kilograms. */
export const MASS_TO_KG: Record<MassUnit, number> = {
  kg: 1,
  t: 1000,
  lb: 0.45359237,
};

export function isVolumeUnit(u: unknown): u is VolumeUnit {
  return typeof u === 'string' && (VOLUME_UNITS as readonly string[]).includes(u);
}

export function isMassUnit(u: unknown): u is MassUnit {
  return typeof u === 'string' && (MASS_UNITS as readonly string[]).includes(u);
}

export function volumeToM3(value: number, unit: VolumeUnit): number {
  return value * VOLUME_TO_M3[unit];
}

export function volumeFromM3(m3: number, unit: VolumeUnit): number {
  return m3 / VOLUME_TO_M3[unit];
}

export function massToKg(value: number, unit: MassUnit): number {
  return value * MASS_TO_KG[unit];
}

export function massFromKg(kg: number, unit: MassUnit): number {
  return kg / MASS_TO_KG[unit];
}

/**
 * Round for display/export. Internal values are never rounded; this is
 * applied only when presenting numbers to the user or writing exports.
 */
export function roundDisplay(value: number, decimals = 2): number {
  if (!Number.isFinite(value)) return NaN;
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

export function unitLabel(unit: VolumeUnit | MassUnit): string {
  return unit;
}
