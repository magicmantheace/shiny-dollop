import { describe, expect, it } from 'vitest';
import { DungeonService } from '../../electron/main/service.js';
import { openDatabase } from '../../electron/main/store.js';
import { BASE_PARAMS, makeFixture } from './helpers.js';

describe('persistence', () => {
  it('save / list / get / delete round-trip', async () => {
    const { service, db } = makeFixture();
    const map = await service.generate(BASE_PARAMS);
    const saved = await service.dungeonsSave({ name: 'Round Trip', map });
    expect(saved.id).toBeTruthy();
    expect(saved.name).toBe('Round Trip');
    expect(saved.createdAt).toBeTruthy();
    expect(saved.map).toEqual(map);

    const list = await service.dungeonsList();
    expect(list).toHaveLength(1);
    expect(list[0]).toMatchObject({
      id: saved.id,
      name: 'Round Trip',
      seed: BASE_PARAMS.seed,
      theme: BASE_PARAMS.theme,
      roomCount: map.rooms.length,
      budgetUsed: map.budgetUsed,
      budgetLimit: map.budgetLimit,
    });

    const fetched = await service.dungeonsGet(saved.id);
    expect(fetched).toEqual(saved);

    await service.dungeonsDelete(saved.id);
    expect(await service.dungeonsList()).toEqual([]);
    await expect(service.dungeonsGet(saved.id)).rejects.toMatchObject({
      code: 'DUNGEON_NOT_FOUND',
    });
    db.close();
  });

  it('a saved dungeon is identical after reopening the database file', async () => {
    const { service, db, dbPath } = makeFixture();
    const map = await service.generate({ ...BASE_PARAMS, seed: 'reopen-seed' });
    const saved = await service.dungeonsSave({ name: 'Reopen Me', map });
    db.close();

    const db2 = openDatabase(dbPath);
    const service2 = new DungeonService(db2);
    const reopened = await service2.dungeonsGet(saved.id);
    expect(reopened).toEqual(saved);
    const list = await service2.dungeonsList();
    expect(list.map((s) => s.id)).toEqual([saved.id]);
    db2.close();
  });

  it('deleting a missing dungeon rejects with DUNGEON_NOT_FOUND', async () => {
    const { service, db } = makeFixture();
    await expect(service.dungeonsDelete('no-such-dungeon')).rejects.toMatchObject({
      code: 'DUNGEON_NOT_FOUND',
    });
    db.close();
  });

  it('getting a missing dungeon rejects with DUNGEON_NOT_FOUND', async () => {
    const { service, db } = makeFixture();
    await expect(service.dungeonsGet('no-such-dungeon')).rejects.toMatchObject({
      code: 'DUNGEON_NOT_FOUND',
    });
    db.close();
  });
});
