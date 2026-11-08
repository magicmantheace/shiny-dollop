/**
 * Application settings (key/value). Integer and enum settings are validated
 * by the caller against the zod schemas in shared/schemas.ts.
 */
import type { DatabaseSync } from 'node:sqlite';

export const DEFAULTS: Record<string, string> = {
  company_name: 'Concrete Operations',
  company_address: '',
  default_concrete_rate_cents_per_m3: '18000',
  default_small_load_charge_cents: '15000',
  small_load_threshold_liters: '3000',
  default_delivery_mode: 'flat',
  default_delivery_flat_cents: '7500',
  default_delivery_per_km_cents: '350',
};

export function getSetting(db: DatabaseSync, key: string): string {
  const row = db.prepare('SELECT value FROM app_settings WHERE key = ?').get(key) as
    | { value: string }
    | undefined;
  if (row) return row.value;
  const fallback = DEFAULTS[key];
  if (fallback === undefined) throw new Error(`unknown setting: ${key}`);
  return fallback;
}

export function getAllSettings(db: DatabaseSync): Record<string, string> {
  const rows = db.prepare('SELECT key, value FROM app_settings').all() as {
    key: string;
    value: string;
  }[];
  const out: Record<string, string> = { ...DEFAULTS };
  for (const r of rows) out[r.key] = r.value;
  return out;
}

export function setSetting(db: DatabaseSync, key: string, value: string): void {
  if (DEFAULTS[key] === undefined) throw new Error(`unknown setting: ${key}`);
  db.prepare(
    'INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value',
  ).run(key, value);
}

export function getIntSetting(db: DatabaseSync, key: string): number {
  const n = Number(getSetting(db, key));
  if (!Number.isSafeInteger(n)) throw new Error(`setting ${key} is not an integer: ${getSetting(db, key)}`);
  return n;
}
