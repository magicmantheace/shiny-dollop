// Zod validation for IPC inputs arriving from the renderer.

import { z } from 'zod';
import { SpectatorError } from '../../shared/errors.js';

export const BaseUrlInput = z.string().min(1).max(300);
export const DescenderIdInput = z.string().min(1).max(120);
export const LimitInput = z.number().int().min(1).max(1000).optional();
export const SearchQueryInput = z.string().min(1).max(120);
export const ReplayQueryInput = z.object({
  afterTick: z.number().int().min(0).nullable().optional(),
  limit: z.number().int().min(1).max(1000).optional(),
  eventType: z.string().min(1).max(80).nullable().optional(),
});

export function parseInput<T>(schema: z.ZodType<T>, value: unknown, what: string): T {
  const result = schema.safeParse(value);
  if (!result.success) {
    throw new SpectatorError('INPUT_INVALID', `Invalid ${what}: ${result.error.issues[0]?.message ?? 'malformed input'}.`);
  }
  return result.data;
}
