import { isAbsolute } from 'node:path';
import { z } from 'zod';

function isLoopbackUrl(value: string): boolean {
  try {
    const u = new URL(value);
    const host = u.hostname.replace(/^\[|\]$/g, '').toLowerCase();
    return host === 'localhost' || host === '127.0.0.1' || host === '::1';
  } catch { return false; }
}

export const endpointConfigSchema = z.object({
  mode: z.enum(['live', 'mock']),
  baseUrl: z.string().url().refine(isLoopbackUrl, { message: 'baseUrl must be a loopback URL (localhost, 127.0.0.1, or ::1)' }),
  model: z.string().trim().min(1).max(200),
  timeoutMs: z.number().int().min(100).max(120000),
  workspaceRoot: z.string().trim().min(1).refine((v) => isAbsolute(v), { message: 'workspaceRoot must be an absolute path' }),
}).strict();

export const configSaveSchema = z.tuple([endpointConfigSchema]);
export const configGetSchema = z.tuple([]);
export const endpointHealthSchema = z.tuple([]);
export const endpointModelsSchema = z.tuple([]);

export const tasksSubmitSchema = z.tuple([
  z.object({ prompt: z.string(), model: z.string().trim().min(1).max(200).optional() }).strict(),
]);
const idSchema = z.string().trim().min(1).max(500);
export const tasksGetSchema = z.tuple([idSchema]);
export const tasksCancelSchema = z.tuple([idSchema]);
export const tasksLogsSchema = z.tuple([idSchema]);
export const tasksListSchema = z.tuple([]);
export const proposalsListSchema = z.tuple([]);
export const proposalsGetSchema = z.tuple([idSchema]);
export const proposalsApproveSchema = z.tuple([idSchema]);
export const proposalsRejectSchema = z.tuple([idSchema]);
export const auditListSchema = z.tuple([z.number().int().min(1).max(500).optional()]);
export const resourcesSnapshotSchema = z.tuple([]);
export const pickDirectorySchema = z.tuple([]);
// aliases
export const idArgSchema = idSchema;
