// Small formatting helpers for the renderer.

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return iso;
  }
  return d.toLocaleString();
}

export function sourceLabelText(title: string | undefined | null): string {
  return title && title.trim().length > 0 ? title : 'No source recorded';
}
