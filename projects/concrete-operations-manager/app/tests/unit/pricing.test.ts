import { describe, expect, it } from 'vitest';
import {
  computeTotals,
  concreteLineCents,
  divRoundHalfUp,
  mileageFeeCents,
  taxCents,
} from '../../shared/pricing';
import type { PricingParams } from '../../shared/pricing';

function baseParams(overrides: Partial<PricingParams> = {}): PricingParams {
  return {
    concreteRateCentsPerM3: 18000,
    smallLoadThresholdLiters: 3000,
    smallLoadChargeCents: 15000,
    smallLoadApplied: true,
    deliveryMode: 'flat',
    deliveryFlatCents: 7500,
    deliveryPerKmCents: 350,
    distanceTenthsKm: null,
    taxes: [{ name: 'GST', rateBps: 500 }],
    taxExempt: false,
    ...overrides,
  };
}

describe('divRoundHalfUp', () => {
  it('rounds exact values', () => {
    expect(divRoundHalfUp(45000, 1)).toBe(45000);
  });
  it('rounds half a cent up', () => {
    // 500/1000 = 0.5 → 1
    expect(divRoundHalfUp(500, 1000)).toBe(1);
  });
  it('rounds just under half down', () => {
    // 499/1000 = 0.499 → 0
    expect(divRoundHalfUp(499, 1000)).toBe(0);
  });
  it('rejects negative or unsafe inputs', () => {
    expect(() => divRoundHalfUp(-1, 1000)).toThrow();
    expect(() => divRoundHalfUp(5, 0)).toThrow();
  });
});

describe('concreteLineCents', () => {
  it('computes 2.5 m³ @ $180/m³ = $450.00', () => {
    expect(concreteLineCents(2500, 18000)).toBe(45000);
  });
  it('rounds half-cent lines up', () => {
    // 1 L @ $5.00/m³ = 0.5¢ → 1¢
    expect(concreteLineCents(1, 500)).toBe(1);
  });
});

describe('taxCents', () => {
  it('computes GST 5% on $675.00 = $33.75', () => {
    expect(taxCents(67500, 500)).toBe(3375);
  });
  it('rounds half-cent tax up', () => {
    // 10¢ @ 5% = 0.5¢ → 1¢
    expect(taxCents(10, 500)).toBe(1);
  });
});

describe('mileageFeeCents', () => {
  it('computes 18.5 km @ $3.50/km = $64.75', () => {
    expect(mileageFeeCents(185, 350)).toBe(6475);
  });
});

describe('computeTotals', () => {
  it('itemizes the canonical MVP quote: 2.5 m³ @ $180 + small load + flat delivery + GST', () => {
    const t = computeTotals(
      [{ pourId: 1, mixDesignId: 'C25/30', liters: 2500 }],
      baseParams(),
    );
    expect(t.lines.map((l) => l.kind)).toEqual(['concrete', 'small_load', 'delivery']);
    expect(t.lines[0]?.amountCents).toBe(45000);
    expect(t.lines[1]?.amountCents).toBe(15000);
    expect(t.lines[2]?.amountCents).toBe(7500);
    expect(t.subtotalCents).toBe(67500);
    expect(t.taxLines).toHaveLength(1);
    expect(t.taxLines[0]).toMatchObject({ name: 'GST', rateBps: 500, taxableCents: 67500, taxCents: 3375 });
    expect(t.totalCents).toBe(70875);
    expect(t.taxExemptApplied).toBe(false);
  });

  it('does NOT apply the small-load charge at exactly the threshold', () => {
    const t = computeTotals(
      [{ pourId: 1, mixDesignId: 'C25/30', liters: 3000 }],
      baseParams(),
    );
    expect(t.lines.map((l) => l.kind)).toEqual(['concrete', 'delivery']);
  });

  it('applies the small-load charge just under the threshold', () => {
    const t = computeTotals(
      [{ pourId: 1, mixDesignId: 'C25/30', liters: 2999 }],
      baseParams(),
    );
    expect(t.lines.some((l) => l.kind === 'small_load')).toBe(true);
  });

  it('honours an alternate customer rate and skips delivery when mode is none', () => {
    const t = computeTotals(
      [{ pourId: 1, mixDesignId: 'C32/40', liters: 4000 }],
      baseParams({ concreteRateCentsPerM3: 21000, deliveryMode: 'none' }),
    );
    expect(t.lines[0]?.amountCents).toBe(84000); // 4 m³ @ $210
    expect(t.lines.map((l) => l.kind)).toEqual(['concrete']);
    expect(t.subtotalCents).toBe(84000);
    expect(t.taxLines[0]?.taxCents).toBe(4200);
    expect(t.totalCents).toBe(88200);
  });

  it('charges $0 tax for tax-exempt customers but keeps the tax lines visible', () => {
    const t = computeTotals(
      [{ pourId: 1, mixDesignId: 'C25/30', liters: 2500 }],
      baseParams({ taxExempt: true }),
    );
    expect(t.taxExemptApplied).toBe(true);
    expect(t.taxLines[0]?.taxCents).toBe(0);
    expect(t.totalCents).toBe(t.subtotalCents);
  });

  it('computes mileage delivery from the job distance', () => {
    const t = computeTotals(
      [{ pourId: 1, mixDesignId: 'C25/30', liters: 5000 }],
      baseParams({ deliveryMode: 'mileage', distanceTenthsKm: 185 }),
    );
    const delivery = t.lines.find((l) => l.kind === 'delivery');
    expect(delivery?.amountCents).toBe(6475);
    expect(delivery?.label).toContain('mileage');
  });

  it('supports multiple taxes as separate lines', () => {
    const t = computeTotals(
      [{ pourId: 1, mixDesignId: 'C25/30', liters: 1000 }],
      baseParams({ taxes: [{ name: 'GST', rateBps: 500 }, { name: 'PST', rateBps: 700 }] }),
    );
    expect(t.taxLines).toHaveLength(2);
    expect(t.taxLines[0]?.taxCents).toBe(taxCents(t.subtotalCents, 500));
    expect(t.taxLines[1]?.taxCents).toBe(taxCents(t.subtotalCents, 700));
    expect(t.totalCents).toBe(t.subtotalCents + t.taxLines[0]!.taxCents + t.taxLines[1]!.taxCents);
  });

  it('is deterministic: same inputs always give the same outputs', () => {
    const volumes = [
      { pourId: 1, mixDesignId: 'C25/30', liters: 2480 },
      { pourId: 2, mixDesignId: 'C32/40', liters: 1513 },
    ];
    const a = computeTotals(volumes, baseParams());
    const b = computeTotals(volumes, baseParams());
    expect(a).toEqual(b);
  });

  it('rejects insane inputs instead of overflowing', () => {
    expect(() =>
      computeTotals([{ pourId: 1, mixDesignId: 'x', liters: 10 }], baseParams({ concreteRateCentsPerM3: -5 })),
    ).toThrow();
  });
});
