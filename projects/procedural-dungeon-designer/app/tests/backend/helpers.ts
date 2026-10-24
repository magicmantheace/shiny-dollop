import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DungeonService } from '../../electron/main/service.js';
import { openDatabase } from '../../electron/main/store.js';
import { generateDungeon } from '../../shared/generator.js';
import { validateDungeon } from '../../shared/validate.js';
import type { DungeonMap, GenParams } from '../../shared/types.js';

export function makeFixture() {
  const dir = mkdtempSync(join(tmpdir(), 'pdd-test-'));
  const dbPath = join(dir, 'test.sqlite');
  const db = openDatabase(dbPath);
  const service = new DungeonService(db);
  return { dir, dbPath, db, service };
}

export const BASE_PARAMS: GenParams = {
  seed: 'test-seed',
  gridWidth: 24,
  gridHeight: 18,
  roomCount: 8,
  theme: 'sunken-crypt',
  difficulty: 2,
};

/** Deep clone via JSON (maps are plain data). */
export function cloneMap(map: DungeonMap): DungeonMap {
  return JSON.parse(JSON.stringify(map)) as DungeonMap;
}

/**
 * Wall off a room's center with a ring of walls so BFS cannot reach the
 * center tile. Returns a clone where exactly that room is unreachable,
 * or null when walling that room would disconnect other rooms too.
 */
export function isolateRoom(map: DungeonMap, roomId: string): DungeonMap | null {
  const room = map.rooms.find((r) => r.id === roomId);
  if (!room) return null;
  const broken = cloneMap(map);
  const grid = broken.tiles.map((row) => row.split(''));
  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      if (dx === 0 && dy === 0) continue;
      const x = room.cx + dx;
      const y = room.cy + dy;
      const row = grid[y];
      if (row && x >= 0 && x < row.length) row[x] = '#';
    }
  }
  broken.tiles = grid.map((row) => row.join(''));
  const result = validateDungeon(broken);
  if (
    !result.connected &&
    result.unreachableRoomIds.length === 1 &&
    result.unreachableRoomIds[0] === roomId
  ) {
    return broken;
  }
  return null;
}

/** Find a generated map + room that can be isolated exactly. */
export function breakableFixture(params: GenParams = BASE_PARAMS): {
  map: DungeonMap;
  broken: DungeonMap;
  roomId: string;
} {
  const map = generateDungeon(params);
  for (const room of map.rooms) {
    if (room.isEntrance) continue;
    const broken = isolateRoom(map, room.id);
    if (broken) return { map, broken, roomId: room.id };
  }
  throw new Error('no room could be isolated exactly for this fixture');
}
