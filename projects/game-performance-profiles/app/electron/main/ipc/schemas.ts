/**
 * Zod schemas for every gpp:* IPC channel payload. Invalid input is rejected
 * here — before it reaches the engine, the OS layer, or the database.
 */

import { z } from 'zod';
import { CHANGE_KINDS } from '../../../shared/gpp-types.js';

export const changeSpecSchema = z.object({
  kind: z.enum(CHANGE_KINDS as unknown as [string, ...string[]]),
  params: z.record(z.string(), z.string()),
});

export const createProfileSchema = z.object({
  name: z.string().trim().min(1, 'Profile name is required.').max(120),
  changes: z.array(changeSpecSchema).min(1, 'A profile needs at least one change.').max(50),
});

export const updateProfileSchema = z.object({
  id: z.string().min(1),
  name: z.string().trim().min(1).max(120).optional(),
  changes: z.array(changeSpecSchema).min(1).max(50).optional(),
});

export const deleteProfileSchema = z.object({
  id: z.string().min(1),
});

export const previewProfileSchema = z.object({
  profileId: z.string().min(1),
});

export const activateProfileSchema = z.object({
  profileId: z.string().min(1),
  approved: z.boolean(),
});

export const rollbackProfileSchema = z.object({
  profileId: z.string().min(1),
});

export const takeSnapshotSchema = z.object({
  label: z.string().trim().min(1, 'Snapshot label is required.').max(120),
});

/** No payload. */
export const emptySchema = z.object({}).strict();

export function formatZodError(e: z.ZodError): string {
  return e.issues.map((i) => `${i.path.join('.') || 'input'}: ${i.message}`).join('; ');
}
