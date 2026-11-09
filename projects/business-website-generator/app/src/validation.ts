/**
 * Client-side validation for the profile editor.
 *
 * Rules (per the brief):
 *  - email: validated only when non-empty, must match a basic email pattern
 *  - website / social URLs: must start with http:// or https:// when non-empty
 *  - phone: loose pattern — only dialing-related characters and enough digits
 *  - name: required
 * SEO title/description have length *counters* only (guidance, not blockers).
 */

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const URL_RE = /^https?:\/\/.+/;
// Letters allowed for "ext. 123"; digits counted separately below.
const PHONE_ALLOWED_RE = /^[+\d(][\d\s().\-]*$/i;

export function isValidEmail(value: string): boolean {
  return EMAIL_RE.test(value.trim());
}

export function isValidUrl(value: string): boolean {
  return URL_RE.test(value.trim());
}

export function isValidPhone(value: string): boolean {
  const trimmed = value.trim();
  if (!PHONE_ALLOWED_RE.test(trimmed)) return false;
  const digits = trimmed.replace(/\D/g, '');
  return digits.length >= 7 && digits.length <= 15;
}

/** Error message for an optional field, or null when the value is acceptable. */
export function validateOptionalEmail(value: string): string | null {
  if (value.trim() === '') return null;
  return isValidEmail(value) ? null : 'Enter a valid email address, e.g. name@example.com.';
}

export function validateOptionalUrl(value: string): string | null {
  if (value.trim() === '') return null;
  return isValidUrl(value)
    ? null
    : 'URL must start with http:// or https://.';
}

export function validateOptionalPhone(value: string): string | null {
  if (value.trim() === '') return null;
  return isValidPhone(value)
    ? null
    : 'Enter a valid phone number (digits, spaces and + - ( ) . only).';
}

export function validateRequiredName(value: string): string | null {
  return value.trim() === '' ? 'Site name is required.' : null;
}

/** Recommended SEO length limits (guidance counters, not validation errors). */
export const SEO_TITLE_LIMIT = 60;
export const SEO_DESCRIPTION_LIMIT = 160;

/** Maps an export-validation issue `field` to a profile-editor section anchor. */
export function fieldToSectionId(field: string | undefined): string {
  const f = (field ?? '').toLowerCase();
  if (f.includes('seo')) return 'section-seo';
  if (f.includes('contact')) return 'section-contact';
  if (f.includes('hours')) return 'section-hours';
  if (f.includes('service')) return 'section-services';
  if (f.includes('menu')) return 'section-menu';
  if (f.includes('social')) return 'section-social';
  if (f.includes('tagline') || f.includes('about')) return 'section-identity';
  return 'section-identity';
}
