/**
 * MVP acceptance workflow, end to end at the engine level:
 * enter a calibrated mix and desired cubic metres → reproducible cement,
 * sand, stone, water (+ admixture) quantities and estimated remaining stock.
 *
 * Uses the same engine code paths the desktop UI calls through IPC.
 */
import { describe, expect, it } from 'vitest';
import { calculate } from '../../engine/calculator.js';
import { calculationToCsv } from '../../engine/csv.js';
import { exportEnvelope, validateEnvelope } from '../../engine/exchange.js';
import { fixtureProfile } from '../fixtures.js';

describe('MVP acceptance: calibrated mix → quantities + remaining stock', () => {
  it('produces reproducible quantities and stock estimates', () => {
    const request = {
      profile: fixtureProfile(),
      mixDesignId: 'NOM-25',
      volume: 8,
      volumeUnit: 'm3' as const,
      wasteAllowancePct: 5,
      startingStock: { cement: 10000, sand: 30000, stone: 30000, water: 8000, admix: 200 },
      lowStockThresholds: { cement: 2000 },
      truckLimits: { maxVolume: 10, maxPayloadMass: 40000 },
    };

    const first = calculate(request);
    const second = calculate(request);

    // Reproducible: identical inputs → identical outputs.
    expect(JSON.stringify({ ...first, calculatedAt: 't' })).toBe(
      JSON.stringify({ ...second, calculatedAt: 't' }),
    );

    // Cement, sand, stone, water (+ admixture) quantities present.
    const ids = first.materials.map((m) => m.materialId).sort();
    expect(ids).toEqual(['admix', 'cement', 'sand', 'stone', 'water']);

    // Known values: cement 320 kg/m³ × 8 m³ × 1.05 = 2688 kg.
    const cement = first.materials.find((m) => m.materialId === 'cement')!;
    expect(cement.requiredQty).toBeCloseTo(2688, 6);
    expect(cement.gateSettingNeeded).toBeCloseTo(336, 6);
    expect(cement.remainingStock).toBeCloseTo(7312, 6);
    expect(cement.shortfall).toBe(false);
    expect(cement.lowStock).toBe(false);

    // Water: 165 L/m³ × 8 × 1.05 = 1386 L; gate 277.2.
    const water = first.materials.find((m) => m.materialId === 'water')!;
    expect(water.requiredQty).toBeCloseTo(1386, 6);
    expect(water.remainingStock).toBeCloseTo(8000 - 1386, 6);

    // No warnings when everything fits.
    expect(first.warnings).toHaveLength(0);

    // Assumptions are surfaced with the result.
    expect(first.assumptions.length).toBeGreaterThan(0);

    // CSV export is unit-aware and carries the disclaimer.
    const csv = calculationToCsv(first, 'kg');
    expect(csv).toContain('requiredQty (incl. waste)');
    expect(csv).toContain('qtyUnit');
    expect(csv).toContain('nominal identifiers only');
    expect(csv).toContain('never a legal payload determination');

    // Calibration envelope export validates against the v1.0.0 contract.
    const envelope = exportEnvelope(fixtureProfile());
    expect(() => validateEnvelope(envelope)).not.toThrow();
    expect(envelope.formatVersion).toBe('1.0.0');
  });

  it('changing only the volume scales every quantity linearly', () => {
    const at8 = calculate({
      profile: fixtureProfile(),
      mixDesignId: 'NOM-25',
      volume: 8,
      volumeUnit: 'm3',
      wasteAllowancePct: 0,
    });
    const at4 = calculate({
      profile: fixtureProfile(),
      mixDesignId: 'NOM-25',
      volume: 4,
      volumeUnit: 'm3',
      wasteAllowancePct: 0,
    });
    for (const m8 of at8.materials) {
      const m4 = at4.materials.find((m) => m.materialId === m8.materialId)!;
      expect(m8.requiredQty).toBeCloseTo(m4.requiredQty * 2, 9);
    }
  });
});
