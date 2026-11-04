// Deterministic seeded dungeon generator (pure library).
//
// Guarantees:
// - Same (seed, params) -> identical DungeonMap, on every run and platform.
//   All randomness flows from one mulberry32 stream seeded by the seed
//   string; iteration order is fixed everywhere; no Math.random()/Date.
// - Connectivity by construction: room centers are joined by a minimum
//   spanning tree of carved L-corridors (plus a few extra loops), and
//   validateDungeon() independently proves reachability with BFS.
// - Budget: placements are only added while they fit the budget; the
//   generator never produces an over-budget map.

import { nextInt, pick, rngFromSeed, type Rng } from './prng.js';
import { cheapestCost, getTheme } from './themes.js';
import type {
  DungeonMap,
  GenParams,
  Placement,
  PlacementKind,
  Room,
} from './types.js';

/** Budget rule (documented): 30 base + 20 per difficulty point + 2 per
 *  requested room. Difficulty 1..5 and roomCount 3..40 -> 56..210 points. */
export function budgetLimitFor(params: GenParams): number {
  return 30 + params.difficulty * 20 + params.roomCount * 2;
}

const ROMAN = ['II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'];

interface Rect { x: number; y: number; w: number; h: number }

function overlaps(a: Rect, b: Rect): boolean {
  // 1-tile padding around each room keeps rooms visually distinct.
  return (
    a.x - 1 < b.x + b.w &&
    a.x + a.w + 1 > b.x &&
    a.y - 1 < b.y + b.h &&
    a.y + a.h + 1 > b.y
  );
}

function carveCorridor(
  tiles: string[][],
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  horizontalFirst: boolean,
): void {
  const carve = (x: number, y: number): void => {
    const row = tiles[y];
    if (row && row[x] === '#') row[x] = '+';
  };
  let x = x0;
  let y = y0;
  const stepX = () => { x += Math.sign(x1 - x); };
  const stepY = () => { y += Math.sign(y1 - y); };
  carve(x, y);
  if (horizontalFirst) {
    while (x !== x1) { stepX(); carve(x, y); }
    while (y !== y1) { stepY(); carve(x, y); }
  } else {
    while (y !== y1) { stepY(); carve(x, y); }
    while (x !== x1) { stepX(); carve(x, y); }
  }
}

export function generateDungeon(params: GenParams): DungeonMap {
  const theme = getTheme(params.theme);
  const rng: Rng = rngFromSeed(
    `${params.seed}|${params.theme}|${params.gridWidth}x${params.gridHeight}|${params.roomCount}|${params.difficulty}`,
  );
  const W = params.gridWidth;
  const H = params.gridHeight;

  // --- Room placement -----------------------------------------------------
  const rects: Rect[] = [];
  const passes: Array<{ wMax: number; hMax: number }> = [
    { wMax: 7, hMax: 6 },
    { wMax: 5, hMax: 5 },
  ];
  for (const pass of passes) {
    if (rects.length >= params.roomCount) break;
    const attempts = params.roomCount * 60;
    for (let i = 0; i < attempts && rects.length < params.roomCount; i++) {
      const w = nextInt(rng, 3, pass.wMax);
      const h = nextInt(rng, 3, pass.hMax);
      const rect: Rect = {
        w,
        h,
        x: nextInt(rng, 1, W - w - 2),
        y: nextInt(rng, 1, H - h - 2),
      };
      if (!rects.some((r) => overlaps(r, rect))) rects.push(rect);
    }
  }
  if (rects.length < 3) {
    throw new Error(
      `Could not place at least 3 rooms on a ${W}x${H} grid; increase the grid size or lower the room count.`,
    );
  }

  // --- Tiles + room floors --------------------------------------------------
  const tiles: string[][] = Array.from({ length: H }, () =>
    Array.from({ length: W }, () => '#'),
  );
  for (const r of rects) {
    for (let y = r.y; y < r.y + r.h; y++) {
      for (let x = r.x; x < r.x + r.w; x++) {
        const row = tiles[y];
        if (row) row[x] = '.';
      }
    }
  }

  const centers = rects.map((r) => ({
    cx: r.x + Math.floor(r.w / 2),
    cy: r.y + Math.floor(r.h / 2),
  }));

  // --- Connectivity: MST over room centers (deterministic Kruskal) --------
  interface Edge { a: number; b: number; d: number }
  const edges: Edge[] = [];
  for (let i = 0; i < rects.length; i++) {
    for (let j = i + 1; j < rects.length; j++) {
      const ci = centers[i]!;
      const cj = centers[j]!;
      const d = Math.abs(ci.cx - cj.cx) + Math.abs(ci.cy - cj.cy);
      edges.push({ a: i, b: j, d });
    }
  }
  edges.sort((e1, e2) => e1.d - e2.d || e1.a - e2.a || e1.b - e2.b);
  const parent = rects.map((_, i) => i);
  const find = (v: number): number => {
    let root = v;
    while (parent[root] !== root) root = parent[root]!;
    return root;
  };
  const inTree = new Set<string>();
  const key = (a: number, b: number): string => `${Math.min(a, b)}-${Math.max(a, b)}`;
  for (const e of edges) {
    const ra = find(e.a);
    const rb = find(e.b);
    if (ra !== rb) {
      parent[ra] = rb;
      inTree.add(key(e.a, e.b));
      carveCorridor(tiles, centers[e.a]!.cx, centers[e.a]!.cy, centers[e.b]!.cx, centers[e.b]!.cy, rng() < 0.5);
    }
  }
  // Extra loops: shortest non-tree edges, up to floor(rooms/3), for a less
  // linear feel. Deterministic: edges are already in sorted order.
  let loops = 0;
  const loopBudget = Math.floor(rects.length / 3);
  for (const e of edges) {
    if (loops >= loopBudget) break;
    if (!inTree.has(key(e.a, e.b))) {
      carveCorridor(tiles, centers[e.a]!.cx, centers[e.a]!.cy, centers[e.b]!.cx, centers[e.b]!.cy, rng() < 0.5);
      loops++;
    }
  }

  // --- Entrance: room nearest the top-left --------------------------------
  let entranceIdx = 0;
  let bestScore = Number.POSITIVE_INFINITY;
  centers.forEach((c, i) => {
    const score = c.cx + c.cy;
    if (score < bestScore) { bestScore = score; entranceIdx = i; }
  });

  // --- Room names (unique within the map) ----------------------------------
  const usedNames = new Map<string, number>();
  const nameFor = (): string => {
    const base = `${pick(rng, theme.roomNamePrefixes)} ${pick(rng, theme.roomNameNouns)}`;
    const seen = usedNames.get(base) ?? 0;
    usedNames.set(base, seen + 1);
    if (seen === 0) return base;
    return `${base} ${ROMAN[seen - 1] ?? `${seen + 1}`}`;
  };

  const rooms: Room[] = rects.map((r, i) => ({
    id: `room-${i + 1}`,
    name: nameFor(),
    x: r.x,
    y: r.y,
    w: r.w,
    h: r.h,
    cx: centers[i]!.cx,
    cy: centers[i]!.cy,
    isEntrance: i === entranceIdx,
    placements: [],
  }));

  // --- Placements within budget --------------------------------------------
  // Weighted kind draw per non-entrance room; a room may stay empty.
  // A placement is added only if it fits the remaining budget; generation
  // stops adding once the cheapest possible placement no longer fits.
  const budgetLimit = budgetLimitFor(params);
  const cheapest = cheapestCost(theme);
  let budgetUsed = 0;
  let placementSeq = 0;
  const kinds: Array<{ kind: PlacementKind; weight: number }> = [
    { kind: 'encounter', weight: 40 },
    { kind: 'trap', weight: 20 },
    { kind: 'hazard', weight: 20 },
    { kind: 'treasure', weight: 20 },
  ];
  const totalWeight = kinds.reduce((s, k) => s + k.weight, 0);
  for (const room of rooms) {
    if (room.isEntrance) continue;
    if (budgetLimit - budgetUsed < cheapest) break;
    // 15% of rooms stay empty.
    if (rng() < 0.15) continue;
    let roll = rng() * totalWeight;
    let chosen: PlacementKind = 'encounter';
    for (const k of kinds) {
      roll -= k.weight;
      if (roll <= 0) { chosen = k.kind; break; }
    }
    const entry = pick(rng, theme.tables[chosen]);
    if (budgetUsed + entry.cost > budgetLimit) continue;
    placementSeq++;
    const placement: Placement = {
      id: `p${placementSeq}`,
      kind: chosen,
      key: entry.key,
      name: entry.name,
      cost: entry.cost,
    };
    room.placements.push(placement);
    budgetUsed += entry.cost;
  }

  return {
    params: { ...params },
    gridWidth: W,
    gridHeight: H,
    tiles: tiles.map((row) => row.join('')),
    rooms,
    budgetLimit,
    budgetUsed,
  };
}

/** Sum of placement costs on a map (recomputed, never trusted from input). */
export function computeBudgetUsed(map: DungeonMap): number {
  return map.rooms.reduce(
    (sum, room) => sum + room.placements.reduce((s, p) => s + p.cost, 0),
    0,
  );
}
