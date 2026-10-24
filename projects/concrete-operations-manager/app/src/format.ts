/** Display helpers. Money stays in integer cents until the last step. */

export function formatCents(cents: number): string {
  const sign = cents < 0 ? '-' : '';
  const abs = Math.abs(Math.round(cents));
  return `${sign}$${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`;
}

/** Liters → "2.500 m³". */
export function formatM3(liters: number): string {
  return `${(liters / 1000).toFixed(3)} m³`;
}

/** m³ string → liters, or null when invalid. */
export function parseM3ToLiters(input: string): number | null {
  const t = input.trim().replace(',', '.');
  if (!/^\d+(\.\d{1,3})?$/.test(t)) return null;
  const liters = Math.round(parseFloat(t) * 1000);
  if (!Number.isSafeInteger(liters) || liters <= 0) return null;
  return liters;
}

/** Tenths of km → "12.5 km". */
export function formatKm(tenths: number | null): string {
  if (tenths === null) return '—';
  return `${(tenths / 10).toFixed(1)} km`;
}

/** "12.5" km string → tenths of km, or null when blank/invalid. */
export function parseKmToTenths(input: string): number | null {
  const t = input.trim().replace(',', '.');
  if (t === '') return null;
  if (!/^\d+(\.\d)?$/.test(t)) return null;
  return Math.round(parseFloat(t) * 10);
}

/** "$180.00" → 18000 cents, or null when invalid. */
export function parseDollarsToCents(input: string): number | null {
  const t = input.trim().replace('$', '').replace(',', '');
  if (!/^\d+(\.\d{1,2})?$/.test(t)) return null;
  const cents = Math.round(parseFloat(t) * 100);
  if (!Number.isSafeInteger(cents) || cents < 0) return null;
  return cents;
}

export function formatDate(iso: string): string {
  return iso.slice(0, 10);
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}
