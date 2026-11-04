/**
 * Structural validation of generated HTML. Requires <html>, <head>,
 * <body> and <main>; forbids <script> tags; checks tag balance with a
 * simple stack over non-void elements.
 */

const VOID_ELEMENTS = new Set([
  'area',
  'base',
  'br',
  'col',
  'embed',
  'hr',
  'img',
  'input',
  'link',
  'meta',
  'param',
  'source',
  'track',
  'wbr',
]);

export interface StructureResult {
  ok: boolean;
  reason?: string;
}

const REQUIRED_MARKERS = ['<html', '<head', '<body', '<main'] as const;

/**
 * Validate the structure of generated export HTML.
 * Returns { ok: true } or { ok: false, reason } where reason is a
 * short machine-friendly code used in STRUCTURE_INVALID:<reason> errors.
 */
export function validateStructure(html: string): StructureResult {
  const lower = html.toLowerCase();

  for (const marker of REQUIRED_MARKERS) {
    if (!lower.includes(marker)) {
      return { ok: false, reason: `missing-${marker.slice(1)}` };
    }
  }

  if (/<script[\s>]/.test(lower)) {
    return { ok: false, reason: 'script-tag-forbidden' };
  }

  // Strip comments, doctype and CDATA so they don't confuse the stack.
  const cleaned = html
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<!DOCTYPE[^>]*>/gi, '')
    .replace(/<!\[CDATA\[[\s\S]*?\]\]>/gi, '');

  const tagPattern = /<\/?([a-zA-Z][a-zA-Z0-9-]*)\b[^>]*>/g;
  const stack: string[] = [];
  let match: RegExpExecArray | null;

  while ((match = tagPattern.exec(cleaned)) !== null) {
    const full = match[0];
    const name = match[1]?.toLowerCase() ?? '';
    if (name === '' || VOID_ELEMENTS.has(name)) continue;
    if (full.endsWith('/>')) continue; // self-closing

    if (full.startsWith('</')) {
      const open = stack.pop();
      if (open === undefined) {
        return { ok: false, reason: `stray-closing-${name}` };
      }
      if (open !== name) {
        return { ok: false, reason: `mismatched-close-expected-${open}-got-${name}` };
      }
    } else {
      stack.push(name);
    }
  }

  if (stack.length > 0) {
    return { ok: false, reason: `unclosed-${stack[stack.length - 1]}` };
  }

  return { ok: true };
}
