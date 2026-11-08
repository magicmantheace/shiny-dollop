/**
 * Zod schemas for every IPC payload. Main validates with these before
 * anything touches the database or the engine — the renderer is untrusted.
 * The engine re-validates defensively (it throws Error on invalid input).
 */
import { z } from 'zod';

const idSchema = z.string().min(1).max(128);
const nameSchema = z.string().min(1).max(100);
const centsSchema = z.number().int().min(0);
const aprSchema = z.number().min(0).max(100);

export const debtUpsertSchema = z.object({
  id: idSchema.optional(),
  name: nameSchema,
  balanceCents: centsSchema,
  aprPercent: aprSchema,
  minPaymentCents: centsSchema,
});

export const idOnlySchema = z.object({
  id: idSchema,
});

export const incomeUpsertSchema = z.object({
  id: idSchema.optional(),
  name: nameSchema,
  amountCents: centsSchema,
  frequency: z.enum(['monthly', 'biweekly', 'weekly', 'once']),
});

export const simulateRunSchema = z.object({
  extraPaymentCents: centsSchema,
});

export const reportSaveSchema = z.object({
  format: z.enum(['csv', 'json']),
  extraPaymentCents: centsSchema,
  defaultName: z.string().min(1).max(255),
});

/** Payload-less calls (sim:debts/list, sim:income/list). */
export const emptySchema = z.object({});

export type DebtUpsertInput = z.infer<typeof debtUpsertSchema>;
export type IncomeUpsertInput = z.infer<typeof incomeUpsertSchema>;
export type SimulateRunInput = z.infer<typeof simulateRunSchema>;
export type ReportSaveInput = z.infer<typeof reportSaveSchema>;
