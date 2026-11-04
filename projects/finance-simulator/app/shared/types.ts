/** Shared persisted-record types. Single source of truth for main, preload, and tests. */
import type { DebtInput } from '../engine/simulator';

export type IncomeFrequency = 'monthly' | 'biweekly' | 'weekly' | 'once';

export interface DebtRecord {
  id: string;
  name: string;
  balanceCents: number;
  aprPercent: number;
  minPaymentCents: number;
  createdAt: string;
}

export interface IncomeRecord {
  id: string;
  name: string;
  amountCents: number;
  frequency: IncomeFrequency;
  createdAt: string;
}

/** A debt record as engine input. */
export function debtRecordToInput(record: DebtRecord): DebtInput {
  return {
    id: record.id,
    name: record.name,
    balanceCents: record.balanceCents,
    aprPercent: record.aprPercent,
    minPaymentCents: record.minPaymentCents,
  };
}

/** Uniform IPC envelope: { ok: true, data } or { ok: false, error }. */
export interface IpcError {
  code: string;
  message: string;
}

export type IpcResult<T> = { ok: true; data: T } | { ok: false; error: IpcError };
