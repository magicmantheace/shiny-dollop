// Independent connectivity + budget validator.
// BFS over non-wall tiles from the entrance room's center; a room counts
// as reachable when its center tile is reached. This is a proof, checked
// against generated maps in tests, and it correctly fails hand-broken
// disconnected fixtures.

import { computeBudgetUsed } from './generator.js';
import type { DungeonMap, ValidationResult } from './types.js';

export function validateDungeon(map: DungeonMap): ValidationResult {
  const budgetUsed = computeBudgetUsed(map);
  const overBudget = budgetUsed > map.budgetLimit;
  const entrance = map.rooms.find((r) => r.isEntrance) ?? map.rooms[0];
  const unreachableRoomIds: string[] = [];
  let reachableRoomCount = 0;

  if (!entrance) {
    return {
      connected: false,
      roomCount: 0,
      reachableRoomCount: 0,
      unreachableRoomIds: [],
      budgetUsed,
      budgetLimit: map.budgetLimit,
      overBudget,
      valid: false,
    };
  }

  const W = map.gridWidth;
  const H = map.gridHeight;
  const walkable = (x: number, y: number): boolean => {
    if (x < 0 || y < 0 || x >= W || y >= H) return false;
    const row = map.tiles[y];
    return row !== undefined && row[x] !== '#';
  };

  const visited = new Set<string>();
  const queue: Array<[number, number]> = [[entrance.cx, entrance.cy]];
  visited.add(`${entrance.cx},${entrance.cy}`);
  while (queue.length > 0) {
    const [x, y] = queue.shift()!;
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]] as const) {
      const nx = x + dx;
      const ny = y + dy;
      const k = `${nx},${ny}`;
      if (walkable(nx, ny) && !visited.has(k)) {
        visited.add(k);
        queue.push([nx, ny]);
      }
    }
  }

  for (const room of map.rooms) {
    if (visited.has(`${room.cx},${room.cy}`)) reachableRoomCount++;
    else unreachableRoomIds.push(room.id);
  }

  const connected = unreachableRoomIds.length === 0;
  return {
    connected,
    roomCount: map.rooms.length,
    reachableRoomCount,
    unreachableRoomIds,
    budgetUsed,
    budgetLimit: map.budgetLimit,
    overBudget,
    valid: connected && !overBudget,
  };
}
