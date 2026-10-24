/**
 * Typed preload API exposed as `window.sim`.
 * The preload unwraps the { ok, data } IPC envelope and throws Error on
 * failure, so the renderer sees exactly the contract below — never the
 * envelope, never raw ipcRenderer, never Node APIs.
 */
import type { SimulationResult, DebtInput } from '../engine/simulator';
import type { DebtRecord, IncomeRecord, IncomeFrequency } from './types';

export interface SimDebtsApi {
  /** List all persisted debts. */
  list(): Promise<DebtRecord[]>;
  /** Create (no id) or update (with id) a debt. */
  upsert(input: DebtInput & { id?: string }): Promise<DebtRecord>;
  /** Delete a debt. Throws if the id does not exist. */
  remove(id: string): Promise<{ ok: true }>;
}

export interface SimIncomeApi {
  /** List all persisted income sources. */
  list(): Promise<IncomeRecord[]>;
  /** Create or update an income source. */
  upsert(input: {
    id?: string;
    name: string;
    amountCents: number;
    frequency: IncomeFrequency;
  }): Promise<IncomeRecord>;
  /** Delete an income source. Throws if the id does not exist. */
  remove(id: string): Promise<{ ok: true }>;
}

export interface SimSimulateApi {
  /**
   * Run the simulation for BOTH strategies against the persisted debts,
   * with the given extra monthly payment (cents).
   */
  run(extraPaymentCents: number): Promise<{
    avalanche: SimulationResult;
    snowball: SimulationResult;
  }>;
}

export type ReportSaveResult = { savedPath: string } | { cancelled: true };

export interface SimReportApi {
  /**
   * Open the native save dialog and write a scenario report (CSV or JSON)
   * for both strategies. Returns the saved path, or { cancelled: true }.
   */
  save(input: {
    format: 'csv' | 'json';
    extraPaymentCents: number;
    defaultName: string;
  }): Promise<ReportSaveResult>;
}

export interface SimApi {
  debts: SimDebtsApi;
  income: SimIncomeApi;
  simulate: SimSimulateApi;
  report: SimReportApi;
}

declare global {
  interface Window {
    sim: SimApi;
  }
}
