import { z } from 'zod';

export const schemas = {
  'lib:importRoots': z.object({ roots: z.array(z.string().min(1)).min(1).max(50) }),
  'lib:list': z.object({}),
  'lib:rescan': z.object({}),
  'game:update': z.object({
    gameId: z.string().min(1),
    patch: z
      .object({
        title: z.string().min(1).max(200).optional(),
        description: z.string().max(5000).optional(),
        artworkId: z.string().min(1).nullable().optional(),
        tagIds: z.array(z.string().min(1)).max(100).optional(),
        collectionIds: z.array(z.string().min(1)).max(100).optional(),
      })
      .refine((p) => Object.keys(p).length > 0, { message: 'patch must not be empty' }),
  }),
  'artwork:add': z.object({
    sourcePath: z.string().min(1),
    provenance: z.string().max(120).default('file'),
  }),
  'artwork:list': z.object({}),
  'artwork:fileUrl': z.object({ artworkId: z.string().min(1) }),
  'tags:list': z.object({}),
  'tags:add': z.object({ name: z.string().min(1).max(80) }),
  'tags:remove': z.object({ id: z.string().min(1) }),
  'collections:list': z.object({}),
  'collections:add': z.object({ name: z.string().min(1).max(80) }),
  'collections:remove': z.object({ id: z.string().min(1) }),
  'bundle:export': z.object({}),
  'bundle:import': z.object({ jsonText: z.string().min(1) }),
  'changes:list': z.object({ gameId: z.string().min(1) }),
  'changes:undo': z.object({}),
} as const;

export type Channel = keyof typeof schemas;
