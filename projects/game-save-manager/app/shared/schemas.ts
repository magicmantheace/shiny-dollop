/**
 * zod schemas for every IPC payload. Main validates each incoming payload
 * against these before touching the database or the filesystem; the preload
 * bridge and tests reuse them as the contract source of truth.
 */
import { z } from 'zod';

const gameSourceSchema = z.enum(['manual', 'steam', 'epic', 'battlenet', 'discovered']);

export const gameAddSchema = z.object({
  name: z.string().trim().min(1).max(200),
  savePath: z.string().trim().min(1).max(1024),
  source: gameSourceSchema.optional().default('manual'),
});

export const gameUpdateSchema = z.object({
  id: z.number().int().positive(),
  name: z.string().trim().min(1).max(200).optional(),
  savePath: z.string().trim().min(1).max(1024).optional(),
});

export const gameIdSchema = z.object({
  id: z.number().int().positive(),
});

export const backupCreateSchema = z.object({
  gameId: z.number().int().positive(),
  label: z.string().trim().min(1).max(200).optional(),
});

export const backupListSchema = z.object({
  gameId: z.number().int().positive(),
});

export const backupIdSchema = z.object({
  backupId: z.number().int().positive(),
});

export const backupRestoreSchema = z.object({
  backupId: z.number().int().positive(),
  /** Restore is destructive-ish: the flag must be literally true. */
  confirmed: z.literal(true),
});

export const scheduleSetSchema = z.object({
  gameId: z.number().int().positive(),
  /** 5 minutes … 30 days. */
  intervalMinutes: z.number().int().min(5).max(43200),
  enabled: z.boolean().optional().default(true),
});

export const scheduleDeleteSchema = z.object({
  gameId: z.number().int().positive(),
});

export const emptySchema = z.object({});

export type GameAddInput = z.infer<typeof gameAddSchema>;
export type GameUpdateInput = z.infer<typeof gameUpdateSchema>;
export type BackupCreateInput = z.infer<typeof backupCreateSchema>;
export type BackupRestoreInput = z.infer<typeof backupRestoreSchema>;
export type ScheduleSetInput = z.infer<typeof scheduleSetSchema>;
