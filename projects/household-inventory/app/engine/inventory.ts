/**
 * Pure inventory domain logic: strict date handling, warranty math and
 * search matching. No I/O, no Electron, no Date.now() inside the core
 * functions — callers pass `today` as a YYYY-MM-DD string so everything is
 * deterministic and unit-testable.
 */
import type { Item, WarrantyExpiry } from '../shared/types';

const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

/**
 * Strict calendar date: correct shape AND a real calendar day.
 * Returns the normalized string or null (never throws).
 */
export function parseDateStrict(value: string): string | null {
  if (typeof value !== 'string') return null;
  const m = DATE_RE.exec(value);
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;
  const dt = new Date(Date.UTC(y, mo - 1, d));
  if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) {
    return null; // e.g. 2023-02-29
  }
  return value;
}

/** Whole days from `a` to `b` (b - a), computed on UTC calendar dates. */
export function daysBetween(a: string, b: string): number {
  const da = parseDateStrict(a);
  const db = parseDateStrict(b);
  if (!da || !db) throw new Error(`daysBetween: invalid date(s): ${a}, ${b}`);
  const ms = Date.UTC(...dateParts(db)) - Date.UTC(...dateParts(da));
  return Math.round(ms / 86_400_000);
}

function dateParts(s: string): [number, number, number] {
  const m = DATE_RE.exec(s) as RegExpExecArray;
  return [Number(m[1]), Number(m[2]) - 1, Number(m[3])];
}

/** Whole days from `today` until the warranty end date (negative = expired). */
export function daysUntilWarrantyEnd(end: string, today: string): number {
  return daysBetween(today, end);
}

export type WarrantyStatus = 'none' | 'active' | 'expiring' | 'expired';

/**
 * Warranty status of one item relative to `today`.
 * - 'none'     — no warranty end recorded
 * - 'expired'  — end is before today
 * - 'expiring' — end is today or within `withinDays` days after today
 * - 'active'   — end is further out
 */
export function warrantyStatus(
  end: string | null,
  today: string,
  withinDays: number,
): WarrantyStatus {
  if (end === null) return 'none';
  const daysLeft = daysUntilWarrantyEnd(end, today);
  if (daysLeft < 0) return 'expired';
  if (daysLeft <= withinDays) return 'expiring';
  return 'active';
}

/**
 * Items whose warranty needs attention (expired or expiring within
 * `withinDays` days), sorted by daysLeft ascending, then name.
 * Items with no warranty end or an end further out are excluded.
 */
export function expiringWarranties(
  items: Item[],
  withinDays: number,
  today: string,
): WarrantyExpiry[] {
  const out: WarrantyExpiry[] = [];
  for (const item of items) {
    const status = warrantyStatus(item.warrantyEnd, today, withinDays);
    if (status === 'expired' || status === 'expiring') {
      out.push({
        item,
        daysLeft: daysUntilWarrantyEnd(item.warrantyEnd as string, today),
        status,
      });
    }
  }
  out.sort((x, y) => x.daysLeft - y.daysLeft || x.item.name.localeCompare(y.item.name));
  return out;
}

/**
 * Case-insensitive substring search over name, category, location,
 * serial number and notes. Empty/blank query matches everything.
 */
export function matchesSearch(item: Item, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (q.length === 0) return true;
  const haystacks = [item.name, item.category, item.location, item.serialNumber ?? '', item.notes];
  return haystacks.some((h) => h.toLowerCase().includes(q));
}

/** Current UTC calendar date as YYYY-MM-DD. */
export function todayUtc(): string {
  return new Date().toISOString().slice(0, 10);
}
