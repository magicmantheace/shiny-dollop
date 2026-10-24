import { describe, expect, it } from 'vitest';
import { DungeonService } from '../../electron/main/service.js';
import { insertDungeon, openDatabase } from '../../electron/main/store.js';
import { PDD_ERROR_CODES } from '../../shared/errors.js';
import { computeBudgetUsed } from '../../shared/generator.js';
import {
  MAX_PLACEMENTS_PER_ROOM,
  addPlacement,
  movePlacement,
  removePlacement,
} from '../../shared/placements.js';
import { getTheme } from '../../shared/themes.js';
import type { DungeonMap } from '../../shared/types.js';
import { BASE_PARAMS, makeFixture } from './helpers.js';

const ROOMY_PARAMS = { ...BASE_PARAMS, seed: 'placement-seed', roomCount: 5, difficulty: 5 };

describe('placements (service)', () => {
  it('adding a known entry applies the theme table cost and name', async () => {
    const { service, db } = makeFixture();
    const map = await service.generate(ROOMY_PARAMS);
    const saved = await service.dungeonsSave({ name: 'Placement Host', map });
    const room = saved.map.rooms.find((r) => !r.isEntrance);
    expect(room).toBeDefined();
    const entry = getTheme('sunken-crypt').tables.encounter.find((e) => e.key === 'pale-warden');
    expect(entry).toBeDefined();
    const before = saved.map.budgetUsed;
    const updated = await service.placementsAdd(saved.id, {
      roomId: room!.id,
      kind: 'encounter',
      key: 'pale-warden',
    });
    const placedRoom = updated.map.rooms.find((r) => r.id === room!.id);
    const placement = placedRoom?.placements.find((p) => p.key === 'pale-warden');
    expect(placement).toBeDefined();
    expect(placement?.name).toBe(entry!.name);
    expect(placement?.cost).toBe(entry!.cost);
    expect(updated.map.budgetUsed).toBe(before + entry!.cost);
    expect(updated.map.budgetUsed).toBe(computeBudgetUsed(updated.map));
    db.close();
  });

  it('adding an unknown key rejects with PLACEMENT_UNKNOWN', async () => {
    const { service, db } = makeFixture();
    const map = await service.generate(ROOMY_PARAMS);
    const saved = await service.dungeonsSave({ name: 'Unknown Host', map });
    const room = saved.map.rooms[0]!;
    await expect(
      service.placementsAdd(saved.id, { roomId: room.id, kind: 'encounter', key: 'no-such-thing' }),
    ).rejects.toMatchObject({ code: 'PLACEMENT_UNKNOWN' });
    db.close();
  });

  it('remove frees budget and move relocates between rooms (service)', async () => {
    const { service, db } = makeFixture();
    const map = await service.generate(ROOMY_PARAMS);
    const saved = await service.dungeonsSave({ name: 'Move Host', map });
    const [first, second] = saved.map.rooms;
    const added = await service.placementsAdd(saved.id, {
      roomId: first!.id,
      kind: 'treasure',
      key: 'sunken-offering-bowl',
    });
    const placement = added.map.rooms
      .find((r) => r.id === first!.id)
      ?.placements.find((p) => p.key === 'sunken-offering-bowl');
    expect(placement).toBeDefined();

    const moved = await service.placementsMove(saved.id, placement!.id, second!.id);
    expect(
      moved.map.rooms.find((r) => r.id === first!.id)?.placements.some((p) => p.id === placement!.id),
    ).toBe(false);
    expect(
      moved.map.rooms.find((r) => r.id === second!.id)?.placements.some((p) => p.id === placement!.id),
    ).toBe(true);

    const removed = await service.placementsRemove(saved.id, placement!.id);
    expect(removed.map.budgetUsed).toBe(saved.map.budgetUsed);
    expect(
      removed.map.rooms.some((r) => r.placements.some((p) => p.id === placement!.id)),
    ).toBe(false);
    db.close();
  });

  it('edits persist across a database reopen', async () => {
    const { service, db, dbPath } = makeFixture();
    const map = await service.generate(ROOMY_PARAMS);
    const saved = await service.dungeonsSave({ name: 'Persistent Host', map });
    const room = saved.map.rooms.find((r) => !r.isEntrance)!;
    const updated = await service.placementsAdd(saved.id, {
      roomId: room.id,
      kind: 'trap',
      key: 'silt-dart-trap',
    });
    const placementId = updated.map.rooms
      .find((r) => r.id === room.id)
      ?.placements.find((p) => p.key === 'silt-dart-trap')?.id;
    expect(placementId).toBeDefined();
    db.close();

    const db2 = openDatabase(dbPath);
    const service2 = new DungeonService(db2);
    const reopened = await service2.dungeonsGet(saved.id);
    const found = reopened.map.rooms
      .find((r) => r.id === room.id)
      ?.placements.find((p) => p.id === placementId);
    expect(found).toBeDefined();
    expect(found?.name).toBe('Silt Dart Trap');
    db2.close();
  });
});

describe('placements (pure budget rule)', () => {
  function tinyBudgetMap(): DungeonMap {
    const row = '#'.repeat(12);
    return {
      params: {
        seed: 'tiny',
        gridWidth: 12,
        gridHeight: 12,
        roomCount: 3,
        theme: 'sunken-crypt',
        difficulty: 1,
      },
      gridWidth: 12,
      gridHeight: 12,
      tiles: Array.from({ length: 12 }, () => row),
      rooms: [
        {
          id: 'room-1',
          name: 'Tiny Vault',
          x: 1,
          y: 1,
          w: 3,
          h: 3,
          cx: 2,
          cy: 2,
          isEntrance: true,
          placements: [],
        },
      ],
      budgetLimit: 3,
      budgetUsed: 0,
    };
  }

  it('adding beyond a tiny budget throws BUDGET_EXCEEDED and leaves the map unchanged', () => {
    const map = tinyBudgetMap();
    expect(() => addPlacement(map, 'room-1', 'encounter', 'pale-warden')).toThrowError(
      expect.objectContaining({ code: 'BUDGET_EXCEEDED' }),
    );
    expect(map.rooms[0]?.placements).toEqual([]);
    expect(map.budgetUsed).toBe(0);
  });

  it('pure add/remove/move round-trip recomputes the budget', () => {
    const map = { ...tinyBudgetMap(), budgetLimit: 100 };
    const added = addPlacement(map, 'room-1', 'treasure', 'sunken-offering-bowl');
    expect(added.budgetUsed).toBe(2);
    const placement = added.rooms[0]!.placements[0]!;
    const withSecondRoom: DungeonMap = {
      ...added,
      rooms: [
        ...added.rooms,
        {
          id: 'room-2',
          name: 'Tiny Annex',
          x: 6,
          y: 6,
          w: 3,
          h: 3,
          cx: 7,
          cy: 7,
          isEntrance: false,
          placements: [],
        },
      ],
    };
    const moved = movePlacement(withSecondRoom, placement.id, 'room-2');
    expect(moved.rooms[0]?.placements).toEqual([]);
    expect(moved.rooms[1]?.placements.map((p) => p.id)).toEqual([placement.id]);
    const removed = removePlacement(moved, placement.id);
    expect(removed.budgetUsed).toBe(0);
  });
});

describe('placements (per-room placement limit)', () => {
  // Regression: roomSchema caps a room at 50 placements, but the edit
  // operations only checked the budget. 51 Sunken Offering Bowls cost
  // 102 points and fit a difficulty-5 budget (140), so placementsAdd
  // used to persist a map that live validation, saving and JSON import
  // all then rejected. Moving into a full room had the same problem.
  function roomyMap(): DungeonMap {
    const row = '#'.repeat(12);
    const room = (id: string, isEntrance: boolean) => ({
      id,
      name: id,
      x: 1,
      y: 1,
      w: 3,
      h: 3,
      cx: 2,
      cy: 2,
      isEntrance,
      placements: [] as DungeonMap['rooms'][number]['placements'],
    });
    return {
      params: {
        seed: 'roomy',
        gridWidth: 12,
        gridHeight: 12,
        roomCount: 3,
        theme: 'sunken-crypt',
        difficulty: 5,
      },
      gridWidth: 12,
      gridHeight: 12,
      tiles: Array.from({ length: 12 }, () => row),
      rooms: [room('room-1', true), room('room-2', false)],
      budgetLimit: 140,
      budgetUsed: 0,
    };
  }

  it('the limit constant matches the schema cap of 50', () => {
    expect(MAX_PLACEMENTS_PER_ROOM).toBe(50);
  });

  it('adding the 51st placement to a room throws PLACEMENT_LIMIT_EXCEEDED even when it fits the budget', () => {
    let map = roomyMap();
    for (let i = 0; i < MAX_PLACEMENTS_PER_ROOM; i++) {
      map = addPlacement(map, 'room-1', 'treasure', 'sunken-offering-bowl');
    }
    expect(map.rooms[0]?.placements).toHaveLength(50);
    expect(map.budgetUsed).toBe(100); // the 51st bowl (102 total) fits the 140 budget
    expect(() =>
      addPlacement(map, 'room-1', 'treasure', 'sunken-offering-bowl'),
    ).toThrowError(
      expect.objectContaining({ code: PDD_ERROR_CODES.PLACEMENT_LIMIT_EXCEEDED }),
    );
    // The rejected edit leaves the map unchanged.
    expect(map.rooms[0]?.placements).toHaveLength(50);
    expect(map.budgetUsed).toBe(100);
  });

  it('moving a placement into a full room throws PLACEMENT_LIMIT_EXCEEDED and leaves the map unchanged', () => {
    let map = roomyMap();
    for (let i = 0; i < MAX_PLACEMENTS_PER_ROOM; i++) {
      map = addPlacement(map, 'room-2', 'treasure', 'sunken-offering-bowl');
    }
    map = addPlacement(map, 'room-1', 'treasure', 'sunken-offering-bowl');
    const mover = map.rooms[0]!.placements[0]!;
    expect(() => movePlacement(map, mover.id, 'room-2')).toThrowError(
      expect.objectContaining({ code: PDD_ERROR_CODES.PLACEMENT_LIMIT_EXCEEDED }),
    );
    expect(map.rooms[0]?.placements.map((p) => p.id)).toEqual([mover.id]);
    expect(map.rooms[1]?.placements).toHaveLength(50);
  });

  it('moving within the same full room stays a valid no-op', () => {
    let map = roomyMap();
    for (let i = 0; i < MAX_PLACEMENTS_PER_ROOM; i++) {
      map = addPlacement(map, 'room-1', 'treasure', 'sunken-offering-bowl');
    }
    const first = map.rooms[0]!.placements[0]!;
    const moved = movePlacement(map, first.id, 'room-1');
    expect(moved.rooms[0]?.placements).toHaveLength(50);
  });

  it('service placementsAdd rejects the 51st placement and does not persist it', async () => {
    const { service, db } = makeFixture();
    const generated = await service.generate(ROOMY_PARAMS);
    const target = generated.rooms[0]!;
    const full: DungeonMap = {
      ...generated,
      budgetLimit: 500,
      rooms: generated.rooms.map((r) =>
        r.id === target.id
          ? {
              ...r,
              placements: Array.from({ length: MAX_PLACEMENTS_PER_ROOM }, (_, i) => ({
                id: `p${i + 1}`,
                kind: 'treasure' as const,
                key: 'sunken-offering-bowl',
                name: 'Sunken Offering Bowl',
                cost: 2,
              })),
            }
          : { ...r, placements: [] },
      ),
    };
    full.budgetUsed = computeBudgetUsed(full);
    insertDungeon(db, {
      id: 'full-room-1',
      name: 'Full Room',
      createdAt: '2026-10-24T00:00:00.000Z',
      updatedAt: '2026-10-24T00:00:00.000Z',
      map: full,
    });

    await expect(
      service.placementsAdd('full-room-1', {
        roomId: target.id,
        kind: 'treasure',
        key: 'sunken-offering-bowl',
      }),
    ).rejects.toMatchObject({ code: PDD_ERROR_CODES.PLACEMENT_LIMIT_EXCEEDED });

    // Nothing was persisted past the limit, so the stored dungeon still
    // validates and its JSON export still imports cleanly.
    const stored = await service.dungeonsGet('full-room-1');
    expect(stored.map.rooms.find((r) => r.id === target.id)?.placements).toHaveLength(50);
    const exported = await service.exportJson('full-room-1');
    const imported = await service.importJson(exported);
    expect(imported.map).toEqual(stored.map);
    db.close();
  });
});
