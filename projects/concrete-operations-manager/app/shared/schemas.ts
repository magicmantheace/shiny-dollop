/**
 * zod schemas for every IPC payload. Main validates each incoming payload
 * against these before touching the database or the filesystem; the preload
 * bridge and tests reuse them as the contract source of truth.
 */
import { z } from 'zod';

const MAX_NAME = 200;
const MAX_TEXT = 2000;
const MAX_LITERS = 1_000_000; // 1000 m³ per pour — sanity cap
const MAX_KG = 10_000_000;
const MAX_CENTS = 100_000_000_00; // $100M — sanity cap
const MAX_BPS = 100_000; // 1000%

const idSchema = z.number().int().positive();
const centsSchema = z.number().int().min(0).max(MAX_CENTS);
const litersSchema = z.number().int().min(0).max(MAX_LITERS);
const kgSchema = z.number().int().min(0).max(MAX_KG);
const nullableText = (max: number) =>
  z
    .string()
    .trim()
    .max(max)
    .nullable()
    .optional()
    .transform((v) => (v === '' ? null : (v ?? null)));

const dateSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, 'date must be YYYY-MM-DD')
  .refine((d) => {
    const [y, m, day] = d.split('-').map(Number);
    if (!y || !m || !day) return false;
    const dt = new Date(Date.UTC(y, m - 1, day));
    return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === day;
  }, 'not a real calendar date');

const deliveryFeeModeSchema = z.enum(['flat', 'mileage']);
const jobStatusSchema = z.enum(['scheduled', 'in_progress', 'completed', 'cancelled']);

export const idParam = z.object({ id: idSchema });

// ---- customers ----
export const customerAddSchema = z.object({
  name: z.string().trim().min(1).max(MAX_NAME),
  contactName: nullableText(MAX_NAME),
  phone: nullableText(40),
  email: nullableText(200),
  address: nullableText(500),
  taxExempt: z.boolean().optional().default(false),
  concreteRateCentsPerM3: centsSchema.nullable().optional(),
  smallLoadChargeCents: centsSchema.nullable().optional(),
  deliveryFeeMode: deliveryFeeModeSchema.nullable().optional(),
  deliveryFlatCents: centsSchema.nullable().optional(),
  deliveryPerKmCents: centsSchema.nullable().optional(),
  notes: nullableText(MAX_TEXT),
});

export const customerUpdateSchema = customerAddSchema.partial().extend({ id: idSchema });

// ---- jobs ----
export const jobAddSchema = z.object({
  customerId: idSchema,
  jobDate: dateSchema,
  deliveryLocation: z.string().trim().min(1).max(500),
  poNumber: nullableText(100),
  distanceTenthsKm: z.number().int().min(0).max(100000).nullable().optional(),
  status: jobStatusSchema.optional().default('scheduled'),
  notes: nullableText(MAX_TEXT),
});

export const jobUpdateSchema = jobAddSchema.partial().extend({ id: idSchema });

// ---- pours ----
export const pourAddSchema = z.object({
  jobId: idSchema,
  mixDesignId: z.string().trim().min(1).max(40),
  quotedLiters: litersSchema.refine((v) => v > 0, 'quoted volume must be positive'),
});

export const pourUpdateSchema = z.object({
  id: idSchema,
  mixDesignId: z.string().trim().min(1).max(40).optional(),
  quotedLiters: litersSchema.refine((v) => v > 0, 'quoted volume must be positive').optional(),
});

export const pourSetDeliveredSchema = z.object({
  id: idSchema,
  deliveredLiters: litersSchema.refine((v) => v > 0, 'delivered volume must be positive'),
});

export const jobIdParam = z.object({ jobId: idSchema });

// ---- quotes ----
export const quoteCreateSchema = z.object({
  jobId: idSchema,
  notes: nullableText(MAX_TEXT),
});

export const quoteUpdateDraftSchema = z.object({
  id: idSchema,
  notes: nullableText(MAX_TEXT),
  /** Manual rate override for this draft (cents per m³); audited. */
  rateOverrideCentsPerM3: centsSchema.nullable().optional(),
  /** Manual small-load charge override for this draft (cents); audited. */
  smallLoadChargeOverrideCents: centsSchema.nullable().optional(),
});

// ---- invoices ----
export const invoiceCreateSchema = z.object({
  quoteId: idSchema,
});

// ---- settings ----
export const KNOWN_SETTINGS = [
  'company_name',
  'company_address',
  'default_concrete_rate_cents_per_m3',
  'default_small_load_charge_cents',
  'small_load_threshold_liters',
  'default_delivery_mode',
  'default_delivery_flat_cents',
  'default_delivery_per_km_cents',
] as const;

export const settingsSetSchema = z.object({
  key: z.enum(KNOWN_SETTINGS),
  value: z.string().max(500),
});

export const intSettingSchema = (min: number, max: number) =>
  z
    .string()
    .regex(/^-?\d+$/, 'must be an integer')
    .transform(Number)
    .refine((n) => n >= min && n <= max, `must be between ${min} and ${max}`);

// ---- tax rates ----
export const taxRateAddSchema = z.object({
  name: z.string().trim().min(1).max(100),
  rateBps: z.number().int().min(0).max(MAX_BPS),
  enabled: z.boolean().optional().default(true),
});

export const taxRateUpdateSchema = taxRateAddSchema.partial().extend({ id: idSchema });

// ---- inventory ----
export const materialAddSchema = z.object({
  name: z.string().trim().min(1).max(MAX_NAME),
  unit: z.string().trim().min(1).max(20).optional().default('kg'),
});

export const receiptAddSchema = z.object({
  materialId: idSchema,
  supplier: z.string().trim().min(1).max(MAX_NAME),
  receivedDate: dateSchema,
  qtyKg: kgSchema.refine((v) => v > 0, 'quantity must be positive'),
  costCents: centsSchema,
  notes: nullableText(MAX_TEXT),
});

export const consumptionAddSchema = z.object({
  pourId: idSchema,
  materialId: idSchema,
  qtyKg: kgSchema.refine((v) => v > 0, 'quantity must be positive'),
});

export const materialIdParam = z.object({ materialId: idSchema });
export const pourIdParam = z.object({ pourId: idSchema });

export const emptySchema = z.object({});

export const auditListSchema = z.object({
  entityType: z.string().trim().max(60).optional(),
  entityId: idSchema.optional(),
  limit: z.number().int().min(1).max(500).optional().default(100),
});

export const calibrationRemoveSchema = z.object({ id: idSchema });

export type CustomerAddInput = z.infer<typeof customerAddSchema>;
export type CustomerUpdateInput = z.infer<typeof customerUpdateSchema>;
export type JobAddInput = z.infer<typeof jobAddSchema>;
export type JobUpdateInput = z.infer<typeof jobUpdateSchema>;
export type PourAddInput = z.infer<typeof pourAddSchema>;
export type QuoteUpdateDraftInput = z.infer<typeof quoteUpdateDraftSchema>;
export type SettingsSetInput = z.infer<typeof settingsSetSchema>;
