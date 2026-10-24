import { describe, expect, it } from 'vitest';
import type { GenParams } from '../../shared/types.js';
import { BASE_PARAMS, cloneMap, makeFixture } from './helpers.js';

describe('validation', () => {
  it('generate rejects bad params with PARAMS_INVALID', async () => {
    const { service, db } = makeFixture();
    const badParams: GenParams[] = [
      { ...BASE_PARAMS, seed: '' },
      { ...BASE_PARAMS, seed: '   ' },
      { ...BASE_PARAMS, gridWidth: 5 },
      { ...BASE_PARAMS, gridHeight: 99 },
      { ...BASE_PARAMS, roomCount: 99 },
      { ...BASE_PARAMS, roomCount: 2 },
      { ...BASE_PARAMS, difficulty: 0 },
      { ...BASE_PARAMS, difficulty: 6 },
      { ...BASE_PARAMS, theme: 'lava-pit' as GenParams['theme'] },
    ];
    for (const params of badParams) {
      await expect(service.generate(params)).rejects.toMatchObject({ code: 'PARAMS_INVALID' });
    }
    db.close();
  });

  it('save rejects an over-budget map with BUDGET_EXCEEDED', async () => {
    const { service, db } = makeFixture();
    const map = await service.generate(BASE_PARAMS);
    const over = cloneMap(map);
    const room = over.rooms.find((r) => !r.isEntrance) ?? over.rooms[0]!;
    room.placements.push({
      id: 'p9999',
      kind: 'encounter',
      key: 'pale-warden',
      name: 'Pale Warden',
      cost: 100_000,
    });
    over.budgetUsed = 100_000;
    await expect(service.dungeonsSave({ name: 'Over Budget', map: over })).rejects.toMatchObject({
      code: 'BUDGET_EXCEEDED',
    });
    db.close();
  });

  it('save rejects a structurally bad map', async () => {
    const { service, db } = makeFixture();
    const map = await service.generate(BASE_PARAMS);

    const wrongTileCount = cloneMap(map);
    wrongTileCount.tiles = wrongTileCount.tiles.slice(1);
    await expect(
      service.dungeonsSave({ name: 'Bad Tiles', map: wrongTileCount }),
    ).rejects.toMatchObject({ code: 'DUNGEON_INVALID' });

    const badChar = cloneMap(map);
    badChar.tiles = badChar.tiles.map((row, i) => (i === 0 ? `X${row.slice(1)}` : row));
    await expect(service.dungeonsSave({ name: 'Bad Char', map: badChar })).rejects.toMatchObject({
      code: 'DUNGEON_INVALID',
    });

    const shortRow = cloneMap(map);
    shortRow.tiles = shortRow.tiles.map((row, i) => (i === 0 ? row.slice(1) : row));
    await expect(service.dungeonsSave({ name: 'Short Row', map: shortRow })).rejects.toMatchObject({
      code: 'DUNGEON_INVALID',
    });
    db.close();
  });

  it('save rejects an empty name', async () => {
    const { service, db } = makeFixture();
    const map = await service.generate(BASE_PARAMS);
    await expect(service.dungeonsSave({ name: '   ', map })).rejects.toMatchObject({
      code: 'DUNGEON_INVALID',
    });
    db.close();
  });

  it('validateMap reports a valid generated map as connected and valid', async () => {
    const { service, db } = makeFixture();
    const map = await service.generate(BASE_PARAMS);
    const result = await service.validateMap(map);
    expect(result.connected).toBe(true);
    expect(result.valid).toBe(true);
    expect(result.overBudget).toBe(false);
    db.close();
  });
});
