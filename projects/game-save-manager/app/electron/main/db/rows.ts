/**
 * Typed read helpers over node:sqlite's untyped row records.
 * DatabaseSync.prepare().all() returns Record<string, SQLOutputValue>[],
 * which does not structurally overlap our row interfaces — cast via unknown.
 */
export function allRows<T>(rows: unknown): T[] {
  return rows as T[];
}

export function oneRow<T>(row: unknown): T | null {
  return (row as T | undefined) ?? null;
}
