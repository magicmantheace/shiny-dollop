/** Human-readable byte formatting (base 1024). */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return '—';
  }
  if (bytes === 0) {
    return '0 B';
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const exp = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exp;
  const rounded = value >= 100 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded.toLocaleString('en-US')} ${units[exp]}`;
}

/** Locale-grouped integer. */
export function formatInt(n: number): string {
  if (!Number.isFinite(n)) {
    return '—';
  }
  return Math.round(n).toLocaleString('en-US');
}

/** Local date+time for scan timestamps. */
export function formatDateTime(iso: string | null): string {
  if (!iso) {
    return '—';
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return iso;
  }
  return d.toLocaleString();
}

/**
 * MVP protected-path heuristic. Scanning drive roots or well-known Windows
 * system folders is slow and can hit permission walls, so the UI warns first.
 * This is advisory only: the scanner itself stays read-only.
 */
export function isProtectedPath(rootPath: string): boolean {
  const p = rootPath.trim().toLowerCase().replace(/\//g, '\\');
  // Drive root, e.g. "C:\" or "C:"
  if (/^[a-z]:\\?$/.test(p)) {
    return true;
  }
  const segments = p.split('\\').filter(Boolean);
  return segments.some((seg) =>
    ['windows', 'system volume information', '$recycle.bin', 'program files', 'program files (x86)', 'programdata'].includes(seg),
  );
}

/** Potential duplicate savings: size * (n - 1). */
export function duplicateSavingsBytes(sizeBytes: number, fileCount: number): number {
  if (fileCount < 2) {
    return 0;
  }
  return sizeBytes * (fileCount - 1);
}

/**
 * Parse the exclusion editor's raw text (one pattern per line) into a clean
 * list, dropping blanks and deduping.
 */
export function parseExclusions(raw: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || seen.has(trimmed)) {
      continue;
    }
    seen.add(trimmed);
    out.push(trimmed);
  }
  return out;
}

export const DEFAULT_EXCLUSIONS = 'node_modules\n$RECYCLE.BIN\nSystem Volume Information';
