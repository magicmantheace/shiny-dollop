/**
 * HTML escaping for all user-supplied content rendered into theme pages.
 * Every theme renderer must pass ALL profile text through escapeHtml before
 * interpolating it into HTML. Attribute values included.
 */
export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
