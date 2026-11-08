/**
 * Zod validation schemas for all untrusted input (renderer -> main).
 * The main process must parse every IPC payload with these before touching
 * the database or the filesystem.
 */
import { z } from 'zod';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

export const uuidSchema = z.string().regex(UUID_RE, 'must be a UUID v4');

/** Strict calendar date: correct shape AND a real calendar day. */
export const dateStringSchema = z
  .string()
  .regex(DATE_RE, 'must be YYYY-MM-DD')
  .refine(
    (s) => {
      const m = DATE_RE.exec(s);
      if (!m) return false;
      const y = Number(m[1]);
      const mo = Number(m[2]);
      const d = Number(m[3]);
      if (mo < 1 || mo > 12 || d < 1 || d > 31) return false;
      const dt = new Date(Date.UTC(y, mo - 1, d));
      return dt.getUTCFullYear() === y && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === d;
    },
    { message: 'must be a real calendar date' },
  );

export const attachmentKindSchema = z.enum(['receipt', 'photo', 'manual', 'other']);

/** Attachment allowlist: images and PDFs only. */
export const ALLOWED_ATTACHMENT_MIMES = [
  'image/jpeg',
  'image/png',
  'image/webp',
  'application/pdf',
] as const;

/** Hard per-file cap: 20 MiB. */
export const MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024;

export const itemInputSchema = z
  .object({
    name: z.string().trim().min(1, 'name is required').max(200),
    category: z.string().trim().min(1, 'category is required').max(80),
    location: z.string().trim().max(120).default(''),
    purchasePriceCents: z.number().int().min(0).nullable().default(null),
    purchaseDate: dateStringSchema.nullable().default(null),
    serialNumber: z.string().trim().max(100).nullable().default(null),
    notes: z.string().max(5000).default(''),
    warrantyStart: dateStringSchema.nullable().default(null),
    warrantyEnd: dateStringSchema.nullable().default(null),
  })
  .refine(
    (v) => v.warrantyStart === null || v.warrantyEnd === null || v.warrantyEnd >= v.warrantyStart,
    { message: 'warranty end must be on or after warranty start', path: ['warrantyEnd'] },
  );

export type ItemInput = z.infer<typeof itemInputSchema>;

export const itemFilterSchema = z.object({
  search: z.string().trim().max(200).optional(),
  category: z.string().trim().max(80).optional(),
  location: z.string().trim().max(120).optional(),
});

export type ItemFilterInput = z.infer<typeof itemFilterSchema>;

/** Payload for adding an attachment. The file bytes travel as base64. */
export const attachmentInputSchema = z.object({
  fileName: z
    .string()
    .trim()
    .min(1)
    .max(255)
    .refine((s) => !s.includes('/') && !s.includes('\\') && !s.includes('\0'), {
      message: 'fileName must be a plain file name, not a path',
    }),
  mime: z.enum(ALLOWED_ATTACHMENT_MIMES),
  dataBase64: z.string().min(1, 'file data is required'),
  kind: attachmentKindSchema,
});

export type AttachmentInput = z.infer<typeof attachmentInputSchema>;

export const maintenanceInputSchema = z.object({
  eventDate: dateStringSchema,
  description: z.string().trim().min(1, 'description is required').max(1000),
  costCents: z.number().int().min(0).nullable().default(null),
});

export type MaintenanceInput = z.infer<typeof maintenanceInputSchema>;

export const warrantyQuerySchema = z.object({
  withinDays: z.number().int().min(1).max(3650).default(90),
});

export type WarrantyQuery = z.infer<typeof warrantyQuerySchema>;
