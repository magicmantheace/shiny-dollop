// Placement editing operations (pure functions over a DungeonMap).
//
// BUDGET RULE (documented, tested): edits are BLOCKED when they would
// push budgetUsed over budgetLimit — addPlacement/movePlacement throw a
// PddError with code BUDGET_EXCEEDED and the map is left unchanged.
// Removals always succeed. Costs and names always come from the theme
// table — a client can never invent a cheaper cost for a known key, and
// unknown keys are rejected with PLACEMENT_UNKNOWN.

import { PDD_ERROR_CODES, pddError } from './errors.js';
import { computeBudgetUsed } from './generator.js';
import { getTheme, tableEntry } from './themes.js';
import type { DungeonMap, Placement, PlacementKind, Room } from './types.js';

function cloneMap(map: DungeonMap): DungeonMap {
  return {
    ...map,
    params: { ...map.params },
    tiles: [...map.tiles],
    rooms: map.rooms.map((r) => ({
      ...r,
      placements: r.placements.map((p) => ({ ...p })),
    })),
  };
}

export interface PlacementCostMismatch {
  placementId: string;
  kind: PlacementKind;
  key: string;
  /** Theme-table cost, or null when the kind/key is unknown for the theme. */
  expectedCost: number | null;
  actualCost: number;
}

/**
 * Placements on a supplied map whose cost does not match the theme table
 * for their kind/key (including placements with an unknown kind/key).
 * Save/import must reject maps with any mismatches: computeBudgetUsed
 * sums supplied costs, so a map that zeroes its costs would otherwise
 * defeat the budget even though generation/editing never produce it.
 */
export function placementCostMismatches(map: DungeonMap): PlacementCostMismatch[] {
  const theme = getTheme(map.params.theme);
  const mismatches: PlacementCostMismatch[] = [];
  for (const room of map.rooms) {
    for (const placement of room.placements) {
      const entry = tableEntry(theme, placement.kind, placement.key);
      if (!entry || entry.cost !== placement.cost) {
        mismatches.push({
          placementId: placement.id,
          kind: placement.kind,
          key: placement.key,
          expectedCost: entry?.cost ?? null,
          actualCost: placement.cost,
        });
      }
    }
  }
  return mismatches;
}

export function describePlacementCostMismatches(
  mismatches: PlacementCostMismatch[],
): string {
  return mismatches
    .map((m) =>
      m.expectedCost === null
        ? `${m.kind}/${m.key} (placement ${m.placementId}) is not in the theme tables`
        : `${m.kind}/${m.key} (placement ${m.placementId}) costs ${m.actualCost}, expected ${m.expectedCost} from the theme table`,
    )
    .join('; ');
}

export function findRoom(map: DungeonMap, roomId: string): Room {
  const room = map.rooms.find((r) => r.id === roomId);
  if (!room) throw pddError(PDD_ERROR_CODES.ROOM_NOT_FOUND, `Room not found: ${roomId}`);
  return room;
}

export function findPlacement(
  map: DungeonMap,
  placementId: string,
): { room: Room; placement: Placement } {
  for (const room of map.rooms) {
    const placement = room.placements.find((p) => p.id === placementId);
    if (placement) return { room, placement };
  }
  throw pddError(
    PDD_ERROR_CODES.PLACEMENT_NOT_FOUND,
    `Placement not found: ${placementId}`,
  );
}

/** Next deterministic placement id: max existing numeric suffix + 1. */
export function nextPlacementId(map: DungeonMap): string {
  let max = 0;
  for (const room of map.rooms) {
    for (const p of room.placements) {
      const m = /^p(\d+)$/.exec(p.id);
      if (m) max = Math.max(max, Number(m[1]));
    }
  }
  return `p${max + 1}`;
}

export function addPlacement(
  map: DungeonMap,
  roomId: string,
  kind: PlacementKind,
  key: string,
): DungeonMap {
  const theme = getTheme(map.params.theme);
  const entry = tableEntry(theme, kind, key);
  if (!entry) {
    throw pddError(
      PDD_ERROR_CODES.PLACEMENT_UNKNOWN,
      `Unknown ${kind} for theme ${theme.id}: ${key}`,
    );
  }
  const used = computeBudgetUsed(map);
  if (used + entry.cost > map.budgetLimit) {
    throw pddError(
      PDD_ERROR_CODES.BUDGET_EXCEEDED,
      `Adding ${entry.name} (cost ${entry.cost}) would exceed the budget: ${used} + ${entry.cost} > ${map.budgetLimit}. Remove a placement first.`,
    );
  }
  const next = cloneMap(map);
  const room = findRoom(next, roomId);
  room.placements.push({
    id: nextPlacementId(next),
    kind,
    key: entry.key,
    name: entry.name,
    cost: entry.cost,
  });
  next.budgetUsed = computeBudgetUsed(next);
  return next;
}

export function removePlacement(map: DungeonMap, placementId: string): DungeonMap {
  const next = cloneMap(map);
  const { room } = findPlacement(next, placementId);
  room.placements = room.placements.filter((p) => p.id !== placementId);
  next.budgetUsed = computeBudgetUsed(next);
  return next;
}

export function movePlacement(
  map: DungeonMap,
  placementId: string,
  toRoomId: string,
): DungeonMap {
  const next = cloneMap(map);
  const { room: fromRoom, placement } = findPlacement(next, placementId);
  const toRoom = findRoom(next, toRoomId);
  if (fromRoom.id === toRoom.id) return next; // no-op move, still valid
  fromRoom.placements = fromRoom.placements.filter((p) => p.id !== placementId);
  toRoom.placements.push(placement);
  next.budgetUsed = computeBudgetUsed(next);
  return next;
}
