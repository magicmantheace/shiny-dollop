/** Zod schemas validating every IPC payload at the main-process boundary. */
import { z } from 'zod';
import { ENTITY_TYPES, MAX_BACKUP_BYTES } from './types';

const orderKey = z.number().int().nullable().optional();

export const entityTypeSchema = z.enum(ENTITY_TYPES);

export const entityInputSchema = z.object({
  type: entityTypeSchema,
  name: z.string().min(1).max(200),
  role: z.string().max(80).optional(),
  description: z.string().max(50_000).optional(),
  body: z.string().max(200_000).optional(),
  storyDate: z.string().max(80).nullable().optional(),
  orderKey,
  bornOrder: orderKey,
  diedOrder: orderKey,
  tags: z.array(z.string().max(40)).max(20).optional(),
});

export const entityPatchSchema = entityInputSchema.omit({ type: true }).partial();

export const idSchema = z.object({ id: z.string().min(1).max(100) });

export const listSchema = z.object({ type: entityTypeSchema.optional() }).optional();

export const updateSchema = idSchema.extend({ patch: entityPatchSchema });

export const linkAddSchema = z.object({
  sourceId: z.string().min(1).max(100),
  targetId: z.string().min(1).max(100),
  label: z.string().max(80).optional(),
});

export const searchSchema = z.object({
  text: z.string().max(500),
  type: entityTypeSchema.optional(),
});

// Character count here, byte count in the engine: a backup within the
// engine's byte limit never exceeds this many characters (UTF-8 uses at
// least one byte per code unit), and the engine check stays authoritative.
export const importSchema = z.object({ json: z.string().max(MAX_BACKUP_BYTES) });
