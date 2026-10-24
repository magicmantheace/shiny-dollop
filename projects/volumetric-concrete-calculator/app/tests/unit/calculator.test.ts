import { describe, expect, it } from 'vitest';
import { calculate, CalculationError, validateProfile } from '../../engine/calculator.js';
import type { CalculationRequest } from '../../engine/types.js';
import { fixtureProfile } from '../fixtures.js';

function baseRequest(overrides: Partial<CalculationRequest> = {}): CalculationRequest {
  return {
    profile: fixtureProfile(),
    mixDesignId: 'NOM-25',
    volume: 8,
    volumeUnit: 'm3',
    wasteAllowancePct: 5,
    ...overrides,
  };
}

describe('calculator — known values', () => {
  it('computes required quantities with waste allowance', () => {
    const r = calculate(baseRequest());
    const cement = r.materials.find((m) => m.materialId === 'cement')!;
    // 320 kg/m³ × 8 m³ = 2560 theoretical; ×1.05 = 2688 required
    expect(cement.theoreticalQty).toBeCloseTo(2560, 6);
    expect(cement.requiredQty).toBeCloseTo(2688, 6);
    // gate setting needed: 2688 / 8.0 kg per gate unit = 336
    expect(cement.gateSettingNeeded).toBeCloseTo(336, 6);
    expect(cement.basis).toBe('mass');
  });

  it('handles volume-basis materials (water, admixture)', () => {
    const r = calculate(baseRequest());
    const water = r.materials.find((m) => m.materialId === 'water')!;
    // 165 L/m³ × 8 m³ = 1320 L; ×1.05 = 1386 L; gate = 1386/5 = 277.2
    expect(water.theoreticalQty).toBeCloseTo(1320, 6);
    expect(water.requiredQty).toBeCloseTo(1386, 6);
    expect(water.gateSettingNeeded).toBeCloseTo(277.2, 6);
    expect(water.basis).toBe('volume');
  });

  it('is deterministic: identical inputs give identical outputs', () => {
    const a = calculate(baseRequest());
    const b = calculate(baseRequest());
    expect(JSON.stringify({ ...a, calculatedAt: 'x' })).toBe(
      JSON.stringify({ ...b, calculatedAt: 'x' }),
    );
  });

  it('accepts volume in other units and converts', () => {
    const r = calculate(baseRequest({ volume: 8000, volumeUnit: 'L' }));
    const cement = r.materials.find((m) => m.materialId === 'cement')!;
    expect(cement.requiredQty).toBeCloseTo(2688, 6);
    expect(r.totalVolumeM3).toBeCloseTo(8.4, 6);
  });

  it('computes totals', () => {
    const r = calculate(baseRequest());
    // mass-basis: cement 2688 + sand (800*8*1.05=6720) + stone (1050*8*1.05=8820) = 18228 kg
    expect(r.totalMassKg).toBeCloseTo(18228, 4);
    expect(r.totalVolumeM3).toBeCloseTo(8.4, 6);
  });
});

describe('calculator — inventory', () => {
  it('deducts stock and reports remaining', () => {
    const r = calculate(
      baseRequest({ startingStock: { cement: 5000, sand: 20000, stone: 20000, water: 5000, admix: 100 } }),
    );
    const cement = r.materials.find((m) => m.materialId === 'cement')!;
    expect(cement.remainingStock).toBeCloseTo(5000 - 2688, 6);
    expect(cement.shortfall).toBe(false);
  });

  it('flags shortfalls with an actionable warning', () => {
    const r = calculate(baseRequest({ startingStock: { cement: 1000 } }));
    const cement = r.materials.find((m) => m.materialId === 'cement')!;
    expect(cement.shortfall).toBe(true);
    expect(cement.remainingStock).toBeCloseTo(1000 - 2688, 6);
    const w = r.warnings.find((x) => x.code === 'STOCK_SHORTFALL');
    expect(w).toBeDefined();
    expect(w!.estimateOnly).toBe(true);
  });

  it('flags low stock below threshold', () => {
    const r = calculate(
      baseRequest({
        startingStock: { cement: 3000 },
        lowStockThresholds: { cement: 500 },
      }),
    );
    const cement = r.materials.find((m) => m.materialId === 'cement')!;
    expect(cement.lowStock).toBe(true);
    expect(r.warnings.some((w) => w.code === 'LOW_STOCK')).toBe(true);
  });
});

describe('calculator — truck limits are warnings only', () => {
  it('warns when volume exceeds entered capacity', () => {
    const r = calculate(baseRequest({ truckLimits: { maxVolume: 8 } }));
    const w = r.warnings.find((x) => x.code === 'VOLUME_CAPACITY');
    expect(w).toBeDefined();
    expect(w!.estimateOnly).toBe(true);
    expect(w!.message).toMatch(/Estimate only/);
  });

  it('warns when mass exceeds entered payload', () => {
    const r = calculate(baseRequest({ truckLimits: { maxPayloadMass: 10000 } }));
    const w = r.warnings.find((x) => x.code === 'PAYLOAD_MASS');
    expect(w).toBeDefined();
    expect(w!.message).toMatch(/never a legal payload determination/);
  });

  it('stays silent when within limits', () => {
    const r = calculate(baseRequest({ truckLimits: { maxVolume: 10, maxPayloadMass: 30000 } }));
    expect(r.warnings.filter((w) => w.code === 'VOLUME_CAPACITY' || w.code === 'PAYLOAD_MASS')).toHaveLength(0);
  });
});

describe('calculator — theoretical vs measured yield', () => {
  it('reports variance when measured volume is given', () => {
    const r = calculate(baseRequest({ measuredVolumeProducedM3: 7.8 }));
    expect(r.yieldComparison).toBeDefined();
    expect(r.yieldComparison!.theoreticalVolumeM3).toBeCloseTo(8, 9);
    expect(r.yieldComparison!.measuredVolumeM3).toBeCloseTo(7.8, 9);
    expect(r.yieldComparison!.varianceFraction).toBeCloseTo(-0.025, 9);
  });

  it('omits the comparison when no measurement is given', () => {
    expect(calculate(baseRequest()).yieldComparison).toBeUndefined();
  });
});

describe('calculator — invalid inputs are rejected', () => {
  it.each([
    [{ volume: 0 }, 'Target volume must be > 0'],
    [{ volume: -3 }, 'Target volume must be > 0'],
    [{ volume: 2_000_000 }, 'implausibly large'],
    [{ wasteAllowancePct: -1 }, 'between 0 and 100'],
    [{ wasteAllowancePct: 101 }, 'between 0 and 100'],
    [{ mixDesignId: 'NOPE' }, 'not found'],
    [{ volume: NaN }, 'finite number'],
    [{ volume: Infinity }, 'finite number'],
  ])('rejects %j', (overrides, message) => {
    let caught: unknown;
    try {
      calculate(baseRequest(overrides as Partial<CalculationRequest>));
    } catch (e) {
      caught = e;
    }
    expect(caught).toBeInstanceOf(CalculationError);
    expect((caught as Error).message).toContain(message);
  });

  it('rejects zero/negative calibration values at profile validation', () => {
    const p = fixtureProfile();
    p.calibrations[0] = { ...p.calibrations[0], measuredOutputPerUnit: 0 };
    expect(() => validateProfile(p)).toThrowError(CalculationError);
    const p2 = fixtureProfile();
    p2.calibrations[1] = { ...p2.calibrations[1], gateSetting: -5 };
    expect(() => validateProfile(p2)).toThrowError(CalculationError);
  });

  it('rejects negative targetPerM3', () => {
    const p = fixtureProfile();
    p.mixes[0].components[0] = { ...p.mixes[0].components[0], targetPerM3: -1 };
    expect(() => validateProfile(p)).toThrowError(CalculationError);
  });

  it('rejects mixes whose nominalOnly is not literally true', () => {
    const p = fixtureProfile();
    (p.mixes[0] as unknown as { nominalOnly: boolean }).nominalOnly = false;
    expect(() => validateProfile(p)).toThrowError(/nominalOnly must be true/);
  });

  it('rejects duplicate materialIds and undeclared references', () => {
    const p = fixtureProfile();
    p.materials.push({ materialId: 'cement', kind: 'cement' });
    expect(() => validateProfile(p)).toThrowError(/Duplicate materialId/);
    const p2 = fixtureProfile();
    p2.calibrations.push({ materialId: 'ghost', gateSetting: 1, measuredOutputPerUnit: 1 });
    expect(() => validateProfile(p2)).toThrowError(/undeclared materialId/);
  });

  it('warns (not throws) for materials missing calibration', () => {
    const p = fixtureProfile();
    p.calibrations = p.calibrations.filter((c) => c.materialId !== 'admix');
    const r = calculate({ ...baseRequest(), profile: p });
    expect(r.warnings.some((w) => w.code === 'NO_CALIBRATION')).toBe(true);
    const admix = r.materials.find((m) => m.materialId === 'admix')!;
    expect(Number.isNaN(admix.gateSettingNeeded)).toBe(true);
  });
});

describe('calculator — assumptions are always surfaced', () => {
  it('includes estimate and nominal-only assumptions', () => {
    const r = calculate(baseRequest());
    expect(r.assumptions.some((a) => a.includes('estimates'))).toBe(true);
    expect(r.assumptions.some((a) => a.includes('nominal identifiers only'))).toBe(true);
  });
});
