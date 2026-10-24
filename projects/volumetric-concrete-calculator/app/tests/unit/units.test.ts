import { describe, expect, it } from 'vitest';
import {
  MASS_TO_KG,
  VOLUME_TO_M3,
  isMassUnit,
  isVolumeUnit,
  massFromKg,
  massToKg,
  roundDisplay,
  volumeFromM3,
  volumeToM3,
} from '../../engine/units.js';

describe('unit conversions', () => {
  it('converts litres and cubic yards to cubic metres', () => {
    expect(volumeToM3(1000, 'L')).toBeCloseTo(1, 10);
    expect(volumeToM3(1, 'yd3')).toBeCloseTo(VOLUME_TO_M3.yd3, 10);
    expect(volumeToM3(1, 'm3')).toBe(1);
  });

  it('converts cubic metres back to display units', () => {
    expect(volumeFromM3(1, 'L')).toBeCloseTo(1000, 10);
    expect(volumeFromM3(VOLUME_TO_M3.yd3, 'yd3')).toBeCloseTo(1, 10);
  });

  it('converts tonnes and pounds to kilograms', () => {
    expect(massToKg(1, 't')).toBe(1000);
    expect(massToKg(1, 'lb')).toBeCloseTo(MASS_TO_KG.lb, 10);
    expect(massToKg(1, 'kg')).toBe(1);
  });

  it('converts kilograms back to display units', () => {
    expect(massFromKg(1000, 't')).toBeCloseTo(1, 10);
    expect(massFromKg(MASS_TO_KG.lb, 'lb')).toBeCloseTo(1, 10);
  });

  it('round-trips without loss beyond display precision', () => {
    for (const v of [0.5, 3.75, 12.3]) {
      expect(volumeFromM3(volumeToM3(v, 'yd3'), 'yd3')).toBeCloseTo(v, 9);
      expect(massFromKg(massToKg(v, 'lb'), 'lb')).toBeCloseTo(v, 9);
    }
  });

  it('validates unit strings', () => {
    expect(isVolumeUnit('m3')).toBe(true);
    expect(isVolumeUnit('gallon')).toBe(false);
    expect(isMassUnit('t')).toBe(true);
    expect(isMassUnit('oz')).toBe(false);
    expect(isVolumeUnit(undefined)).toBe(false);
  });

  it('rounds only for display', () => {
    // NB: 1.005 is not exactly representable in binary; use values that are.
    expect(roundDisplay(1.125, 2)).toBe(1.13);
    expect(roundDisplay(2.5, 0)).toBe(3);
    expect(Number.isNaN(roundDisplay(Infinity))).toBe(true);
  });
});
