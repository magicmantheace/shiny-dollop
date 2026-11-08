import { describe, expect, it } from 'vitest';
import { stableStringify } from '../../shared/export.js';
import { computeBudgetUsed, generateDungeon } from '../../shared/generator.js';
import type { GenParams } from '../../shared/types.js';
import { validateDungeon } from '../../shared/validate.js';
import { BASE_PARAMS, breakableFixture, makeFixture } from './helpers.js';

describe('generator determinism', () => {
  it('same params generate a deep-equal map with identical stable bytes', () => {
    const a = generateDungeon(BASE_PARAMS);
    const b = generateDungeon(BASE_PARAMS);
    expect(b).toEqual(a);
    expect(stableStringify(b)).toBe(stableStringify(a));
  });

  it('export bytes are identical after saving the same map under the same name', async () => {
    const { service, db } = makeFixture();
    const map = await service.generate(BASE_PARAMS);
    const first = await service.dungeonsSave({ name: 'Deterministic', map });
    const second = await service.dungeonsSave({ name: 'Deterministic', map });
    const export1 = await service.exportJson(first.id);
    const export2 = await service.exportJson(second.id);
    expect(export2).toBe(export1);
    db.close();
  });

  it('different seeds produce different tiles', () => {
    const a = generateDungeon(BASE_PARAMS);
    const b = generateDungeon({ ...BASE_PARAMS, seed: 'another-seed' });
    expect(b.tiles).not.toEqual(a.tiles);
  });
});

describe('generator connectivity', () => {
  const combos: GenParams[] = [
    { seed: 'alpha', gridWidth: 24, gridHeight: 18, roomCount: 8, theme: 'sunken-crypt', difficulty: 2 },
    { seed: 'beta', gridWidth: 30, gridHeight: 24, roomCount: 12, theme: 'ember-deep', difficulty: 3 },
    { seed: 'gamma', gridWidth: 40, gridHeight: 30, roomCount: 20, theme: 'sunken-crypt', difficulty: 4 },
    { seed: 'delta', gridWidth: 20, gridHeight: 16, roomCount: 6, theme: 'ember-deep', difficulty: 1 },
    { seed: 'epsilon', gridWidth: 50, gridHeight: 40, roomCount: 30, theme: 'sunken-crypt', difficulty: 5 },
    { seed: 'zeta', gridWidth: 36, gridHeight: 28, roomCount: 15, theme: 'ember-deep', difficulty: 2 },
  ];

  it('every generated map is fully connected (6 seed/size/theme combos)', () => {
    for (const params of combos) {
      const map = generateDungeon(params);
      const result = validateDungeon(map);
      expect(result.connected, `combo ${params.seed} should be connected`).toBe(true);
      expect(result.unreachableRoomIds).toEqual([]);
      expect(result.reachableRoomCount).toBe(result.roomCount);
    }
  });

  it('validator fails a hand-broken fixture with exactly one unreachable room', () => {
    const { broken, roomId } = breakableFixture();
    const result = validateDungeon(broken);
    expect(result.connected).toBe(false);
    expect(result.valid).toBe(false);
    expect(result.unreachableRoomIds).toEqual([roomId]);
  });
});

describe('generator budget', () => {
  it('generated maps are never over budget at any difficulty', () => {
    for (const difficulty of [1, 2, 3, 4, 5]) {
      const map = generateDungeon({ ...BASE_PARAMS, seed: `budget-${difficulty}`, difficulty });
      expect(map.budgetUsed).toBeLessThanOrEqual(map.budgetLimit);
      expect(map.budgetUsed).toBe(computeBudgetUsed(map));
      expect(validateDungeon(map).overBudget).toBe(false);
    }
  });
});
