/**
 * WCAG 2.x contrast checking for theme tokens. Requires >= 4.5:1 for
 * `text` on `bg` and for `accent` when used as text (checked on `bg`).
 * Returns the token keys that fail.
 */
import type { ThemeTokens } from '../../../shared/types';

const HEX_COLOR = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

export function parseHexColor(hex: string): [number, number, number] | undefined {
  if (!HEX_COLOR.test(hex)) return undefined;
  let h = hex.slice(1);
  if (h.length === 3) {
    h = h
      .split('')
      .map((c) => c + c)
      .join('');
  }
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return [r / 255, g / 255, b / 255];
}

function linearize(channel: number): number {
  return channel <= 0.03928
    ? channel / 12.92
    : Math.pow((channel + 0.055) / 1.055, 2.4);
}

/** WCAG relative luminance of an sRGB hex color. */
export function relativeLuminance(hex: string): number | undefined {
  const rgb = parseHexColor(hex);
  if (!rgb) return undefined;
  const [r, g, b] = rgb;
  return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b);
}

/** WCAG contrast ratio between two hex colors, e.g. #000 on #fff = 21. */
export function contrastRatio(
  foreground: string,
  background: string,
): number | undefined {
  const l1 = relativeLuminance(foreground);
  const l2 = relativeLuminance(background);
  if (l1 === undefined || l2 === undefined) return undefined;
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

export const MIN_CONTRAST_RATIO = 4.5;

/**
 * Returns the token keys failing the contrast requirement:
 * `text` on `bg`, and `accent` on `bg` (accent is used as text).
 * Unparsable colors count as failures.
 */
export function checkContrast(tokens: ThemeTokens): string[] {
  const failing: string[] = [];
  const textRatio = contrastRatio(tokens.text, tokens.bg);
  if (textRatio === undefined || textRatio < MIN_CONTRAST_RATIO) {
    failing.push('text');
  }
  const accentRatio = contrastRatio(tokens.accent, tokens.bg);
  if (accentRatio === undefined || accentRatio < MIN_CONTRAST_RATIO) {
    failing.push('accent');
  }
  return failing;
}
