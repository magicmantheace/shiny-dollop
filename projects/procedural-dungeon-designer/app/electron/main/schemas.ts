// Zod schemas validating every IPC / service input before it reaches
// the generator, the store or the export code. Structural bounds for a
// DungeonMap live here: tile grid shape, allowed tile characters, room
// and placement counts, and bounded name strings.
import { z } from 'zod';
import { MAX_PLACEMENTS_PER_ROOM } from '../../shared/placements.js';

export const themeIdSchema = z.enum(['sunken-crypt', 'ember-deep']);

export const placementKindSchema = z.enum(['encounter', 'trap', 'hazard', 'treasure']);

export const genParamsSchema = z
  .object({
    seed: z.string().trim().min(1).max(64),
    gridWidth: z.number().int().min(12).max(60),
    gridHeight: z.number().int().min(12).max(48),
    roomCount: z.number().int().min(3).max(40),
    theme: themeIdSchema,
    difficulty: z.number().int().min(1).max(5),
  })
  .strict();

export const placementSchema = z
  .object({
    id: z.string().trim().min(1).max(100),
    kind: placementKindSchema,
    key: z.string().trim().min(1).max(100),
    name: z.string().trim().min(1).max(200),
    cost: z.number().int().min(0).max(100_000),
  })
  .strict();

export const roomSchema = z
  .object({
    id: z.string().trim().min(1).max(100),
    name: z.string().trim().min(1).max(200),
    x: z.number().int().min(0).max(10_000),
    y: z.number().int().min(0).max(10_000),
    w: z.number().int().min(1).max(10_000),
    h: z.number().int().min(1).max(10_000),
    cx: z.number().int().min(0).max(10_000),
    cy: z.number().int().min(0).max(10_000),
    isEntrance: z.boolean(),
    placements: z.array(placementSchema).max(MAX_PLACEMENTS_PER_ROOM),
  })
  .strict();

export const dungeonMapSchema = z
  .object({
    params: genParamsSchema,
    gridWidth: z.number().int().min(12).max(60),
    gridHeight: z.number().int().min(12).max(48),
    tiles: z.array(z.string().min(1).max(60)),
    rooms: z.array(roomSchema).max(64),
    budgetLimit: z.number().int().min(0).max(1_000_000),
    budgetUsed: z.number().int().min(0).max(1_000_000),
  })
  .strict()
  .superRefine((map, ctx) => {
    if (map.tiles.length !== map.gridHeight) {
      ctx.addIssue({
        code: 'custom',
        path: ['tiles'],
        message: `tiles must have exactly gridHeight (${map.gridHeight}) rows, got ${map.tiles.length}`,
      });
    }
    map.tiles.forEach((row, i) => {
      if (row.length !== map.gridWidth) {
        ctx.addIssue({
          code: 'custom',
          path: ['tiles', i],
          message: `tile row ${i} must have exactly gridWidth (${map.gridWidth}) characters, got ${row.length}`,
        });
      }
      if (!/^[#.+]+$/.test(row)) {
        ctx.addIssue({
          code: 'custom',
          path: ['tiles', i],
          message: `tile row ${i} may only contain '#', '.' and '+' characters`,
        });
      }
    });
    if (map.gridWidth !== map.params.gridWidth || map.gridHeight !== map.params.gridHeight) {
      ctx.addIssue({
        code: 'custom',
        path: ['params'],
        message: 'params grid size must match the map grid size',
      });
    }
    // Room ids must be unique across the whole map: the renderer
    // resolves selectedRoomId with rooms.find and placement operations
    // resolve their room through findRoom (also a first-match find),
    // so a duplicate id makes the second room uninspectable and
    // mis-targets its placements; movePlacement also compares room
    // ids, so moves between same-id rooms become successful no-ops.
    const seenRoomIds = new Set<string>();
    const duplicateRoomIds = new Set<string>();
    for (const room of map.rooms) {
      if (seenRoomIds.has(room.id)) {
        duplicateRoomIds.add(room.id);
      } else {
        seenRoomIds.add(room.id);
      }
    }
    if (duplicateRoomIds.size > 0) {
      ctx.addIssue({
        code: 'custom',
        path: ['rooms'],
        message: `room ids must be unique across the map; duplicate room id(s): ${[...duplicateRoomIds].join(', ')}`,
      });
    }
    // Placement ids must be unique across the whole map, not just within
    // a room: removePlacement deletes every placement with the given id
    // and findPlacement operates on the first match, so a duplicate id
    // in another room would corrupt unrelated placements.
    const seenPlacementIds = new Set<string>();
    const duplicatePlacementIds = new Set<string>();
    for (const room of map.rooms) {
      for (const placement of room.placements) {
        if (seenPlacementIds.has(placement.id)) {
          duplicatePlacementIds.add(placement.id);
        } else {
          seenPlacementIds.add(placement.id);
        }
      }
    }
    if (duplicatePlacementIds.size > 0) {
      ctx.addIssue({
        code: 'custom',
        path: ['rooms'],
        message: `placement ids must be unique across the map; duplicate placement id(s): ${[...duplicatePlacementIds].join(', ')}`,
      });
    }
  });

export const placementOpSchema = z
  .object({
    roomId: z.string().trim().min(1).max(100),
    kind: placementKindSchema,
    key: z.string().trim().min(1).max(100),
  })
  .strict();

export const dungeonNameSchema = z.string().trim().min(1).max(120);

export const saveInputSchema = z
  .object({
    name: dungeonNameSchema,
    map: dungeonMapSchema,
  })
  .strict();

export const idSchema = z.string().trim().min(1).max(500);
export const placementIdSchema = z.string().trim().min(1).max(100);
export const roomIdSchema = z.string().trim().min(1).max(100);

// Tuple wrappers, one per IPC method (arguments arrive as an args array).
export const themesListSchema = z.tuple([]);
export const generateSchema = z.tuple([genParamsSchema]);
export const validateMapSchema = z.tuple([dungeonMapSchema]);
export const dungeonsSaveSchema = z.tuple([saveInputSchema]);
export const dungeonsListSchema = z.tuple([]);
export const dungeonsGetSchema = z.tuple([idSchema]);
export const dungeonsDeleteSchema = z.tuple([idSchema]);
export const placementsAddSchema = z.tuple([idSchema, placementOpSchema]);
export const placementsRemoveSchema = z.tuple([idSchema, placementIdSchema]);
export const placementsMoveSchema = z.tuple([idSchema, placementIdSchema, roomIdSchema]);
export const exportJsonSchema = z.tuple([idSchema]);
export const exportMarkdownSchema = z.tuple([idSchema]);
export const importJsonSchema = z.tuple([z.string()]);
