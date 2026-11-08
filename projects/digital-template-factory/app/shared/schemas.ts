/**
 * Zod schemas for every IPC payload. Main handlers validate inbound
 * payloads against these before touching business logic.
 */
import { z } from 'zod';

export const exportFormatSchema = z.enum(['html', 'print']);

export const templatesGetSchema = z.object({
  templateId: z.string().min(1),
});

export const templatesImportSchema = z.object({
  bundleJson: z.string().min(1),
});

export const documentsCreateSchema = z.object({
  templateId: z.string().min(1),
});

export const documentsGetSchema = z.object({
  id: z.string().min(1),
});

export const documentsUpdateFieldSchema = z.object({
  id: z.string().min(1),
  key: z.string().min(1),
  value: z.unknown(),
});

const partialTokensSchema = z.object({
  bg: z.string().optional(),
  text: z.string().optional(),
  accent: z.string().optional(),
  headingFont: z.string().optional(),
  bodyFont: z.string().optional(),
  spacing: z.number().optional(),
});

export const documentsUpdateTokensSchema = z.object({
  id: z.string().min(1),
  tokens: partialTokensSchema,
});

export const documentsDeleteSchema = z.object({
  id: z.string().min(1),
});

export const exportGenerateSchema = z.object({
  id: z.string().min(1),
  format: exportFormatSchema,
});

export const exportSaveSchema = z.object({
  html: z.string().min(1),
  suggestedName: z.string().min(1),
});
