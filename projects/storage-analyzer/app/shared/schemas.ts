/**
 * Zod schemas for every IPC payload. Main validates with these before
 * anything touches the filesystem or database — the renderer is untrusted.
 */
import { z } from 'zod';

const MAX_PATH_LEN = 32768;

export const scanIdSchema = z.object({
  scanId: z.number().int().positive(),
});

export const scanStartSchema = z.object({
  rootPath: z.string().min(1).max(MAX_PATH_LEN),
  exclusions: z.array(z.string().max(256)).max(100).default([]),
});

export const scanSearchSchema = z.object({
  scanId: z.number().int().positive(),
  query: z.string().min(1).max(256),
});

export const exportReportSchema = z.object({
  scanId: z.number().int().positive(),
  format: z.enum(['csv', 'json']),
  outPath: z.string().min(1).max(MAX_PATH_LEN),
});

/** Payload-less calls (scan.list, dialog.chooseDirectory). */
export const emptySchema = z.object({});

export type ScanIdInput = z.infer<typeof scanIdSchema>;
export type ScanStartInput = z.infer<typeof scanStartSchema>;
export type ScanSearchInput = z.infer<typeof scanSearchSchema>;
export type ExportReportInput = z.infer<typeof exportReportSchema>;
