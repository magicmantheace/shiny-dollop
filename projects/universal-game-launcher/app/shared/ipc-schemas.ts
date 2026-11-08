/** zod schemas validating every IPC payload at the main-process boundary. */
import { z } from 'zod';

const nonEmptyString = z.string().min(1).max(1024);
const uuidLike = z.string().min(1).max(64);

export const libraryListSchema = z
  .object({
    search: z.string().max(256).optional(),
    source: z.enum(['manual', 'steam', 'epic', 'battlenet']).optional(),
    favoritesOnly: z.boolean().optional(),
    sort: z.enum(['title', 'added', 'lastPlayed', 'playtime']).optional(),
  })
  .strict()
  .optional();

export const libraryAddManualSchema = z
  .object({
    path: nonEmptyString.max(32767),
    /** Optional custom title. Empty/whitespace falls back to the exe filename. */
    title: z.string().max(256).optional(),
    workingDir: z.string().max(32767).optional(),
    args: z.array(z.string().max(4096)).max(64).optional(),
  })
  .strict();

export const coverPathSchema = z
  .string()
  .regex(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(png|jpg|jpeg|webp|gif|bmp)$/);

export const filesCoverDataSchema = z.object({ id: uuidLike }).strict();

export const libraryUpdateSchema = z
  .object({
    id: uuidLike,
    title: z.string().min(1).max(256).optional(),
    workingDir: z.string().max(32767).nullable().optional(),
    args: z.array(z.string().max(4096)).max(64).optional(),
    hidden: z.boolean().optional(),
    coverPath: coverPathSchema.nullable().optional(),
  })
  .strict();

export const libraryRemoveSchema = z.object({ id: uuidLike }).strict();

export const librarySetFavoriteSchema = z
  .object({ id: uuidLike, favorite: z.boolean() })
  .strict();

export const gamesLaunchSchema = z.object({ id: uuidLike }).strict();

export const sessionsListSchema = z
  .object({
    gameId: uuidLike.optional(),
    limit: z.number().int().min(1).max(500).optional(),
  })
  .strict()
  .optional();

export const settingsUpdateSchema = z
  .object({
    trackingEnabled: z.boolean().optional(),
    minimizeOnLaunch: z.boolean().optional(),
    theme: z.enum(['dark', 'light', 'system']).optional(),
  })
  .strict();

export const sourcesScanSchema = z
  .object({ source: z.enum(['manual', 'steam', 'epic', 'battlenet']) })
  .strict();

export const sourcesOpenClientSchema = z
  .object({ source: z.enum(['epic', 'battlenet']) })
  .strict();

