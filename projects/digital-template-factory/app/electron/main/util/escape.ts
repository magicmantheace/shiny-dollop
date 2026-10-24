/**
 * HTML escaping. Every user-supplied value interpolated into generated
 * HTML must pass through escapeHtml so injected markup stays inert.
 */
const ESCAPE_MAP: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

export function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ESCAPE_MAP[ch] ?? ch);
}
