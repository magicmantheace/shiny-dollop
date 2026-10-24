/** Pure presentation helpers for the Household Inventory renderer. */

/** Integer cents -> "$X.XX" (or "—" when null). */
export function formatCents(cents: number | null): string {
  if (cents === null || cents === undefined) return '—';
  const sign = cents < 0 ? '-' : '';
  const abs = Math.abs(cents);
  return `${sign}$${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`;
}

/**
 * Dollars.cents text input -> integer cents (or null for blank).
 * Throws with a user-facing message when the input is malformed.
 */
export function parseDollarsToCents(raw: string): number | null {
  const t = raw.trim();
  if (t === '') return null;
  if (!/^\d+(\.\d{1,2})?$/.test(t)) {
    throw new Error('price must look like 19.99 (dollars and cents)');
  }
  const [whole, frac = ''] = t.split('.');
  return Number(whole) * 100 + Number((frac + '00').slice(0, 2));
}

/** Format a Date as YYYY-MM-DD in local time. */
export function toDateString(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** Today's local date as YYYY-MM-DD. */
export function todayISO(): string {
  return toDateString(new Date());
}

/** Whole days from today until `date` (YYYY-MM-DD). Negative = past. */
export function daysUntil(date: string | null): number | null {
  if (!date) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!m) return null;
  const target = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const now = new Date();
  const todayMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((target.getTime() - todayMidnight.getTime()) / 86_400_000);
}

/** Human phrasing for a warranty day count. */
export function describeDaysLeft(daysLeft: number): string {
  if (daysLeft < 0) {
    const n = Math.abs(daysLeft);
    return n === 1 ? 'expired 1 day ago' : `expired ${n} days ago`;
  }
  if (daysLeft === 0) return 'expires today';
  return daysLeft === 1 ? 'expires in 1 day' : `expires in ${daysLeft} days`;
}

/** Short integrity label for a sha256 hex digest. */
export function shortHash(sha256: string): string {
  return sha256.length > 16 ? `${sha256.slice(0, 16)}…` : sha256;
}

/** Max attachment size mirrors shared/schemas.ts MAX_ATTACHMENT_BYTES. */
export const MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024;

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** True when the item's warrantyEnd is in the past. */
export function isWarrantyExpired(warrantyEnd: string | null): boolean {
  const d = daysUntil(warrantyEnd);
  return d !== null && d < 0;
}
