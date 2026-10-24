/** Small formatting helpers shared by renderer components. */

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return '—';
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ['KB', 'MB', 'GB', 'TB'] as const;
  let value = bytes / 1024;
  let unit: string = 'KB';
  for (const u of units) {
    unit = u;
    if (value < 1024 || u === 'TB') {
      break;
    }
    value /= 1024;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${unit}`;
}

/** "2026-10-23 14:05" in the user's locale. */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return iso;
  }
  const pad = (n: number): string => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** "never", "5 min ago", "2 h ago", "3 d ago" for last-run displays. */
export function timeAgo(iso: string | null): string {
  if (!iso) {
    return 'never';
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return iso;
  }
  const mins = Math.max(0, Math.round((Date.now() - d.getTime()) / 60000));
  if (mins < 1) {
    return 'just now';
  }
  if (mins < 60) {
    return `${mins} min ago`;
  }
  const hours = Math.round(mins / 60);
  if (hours < 48) {
    return `${hours} h ago`;
  }
  return `${Math.round(hours / 24)} d ago`;
}
