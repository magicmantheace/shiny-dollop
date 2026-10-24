/**
 * Pure validators for business profiles and rendered static sites.
 *
 * Error codes (stable; surfaced to the renderer):
 * - FIELD_REQUIRED:<field>   missing required profile content
 * - LINK_BROKEN:<href>        internal link target not among exported files
 * - ASSET_MISSING:<path>      referenced local image not among exported files
 * - CONTRAST_FAIL:<token>     theme color token below WCAG AA 4.5:1
 * - HTML_INVALID:<reason>     structural HTML problem
 *
 * Export is BLOCKED (ok:false) when any issue has severity "error".
 */
import type { BusinessProfile, ValidationIssue } from '../../shared/types.js';
import type { ContrastToken, ThemeModule } from './themes/common.js';

export type Severity = 'error' | 'warning';

export interface Issue extends ValidationIssue {
  severity: Severity;
}

function err(code: string, message: string, field?: string): Issue {
  return { code, message, field, severity: 'error' };
}

/** Required-field checks on the profile. */
export function validateProfile(profile: BusinessProfile): Issue[] {
  const issues: Issue[] = [];
  if (!profile.name.trim()) {
    issues.push(err('FIELD_REQUIRED:name', 'The business name is required.', 'name'));
  }
  if (!profile.contact.email.trim() && !profile.contact.phone.trim()) {
    issues.push(
      err(
        'FIELD_REQUIRED:contact.email-or-phone',
        'At least one contact method is required: an email address or a phone number.',
        'contact.email-or-phone',
      ),
    );
  }
  if (!profile.services.length) {
    issues.push(err('FIELD_REQUIRED:services', 'At least one service (or work) is required.', 'services'));
  }
  if (!profile.seo.title.trim()) {
    issues.push(err('FIELD_REQUIRED:seo.title', 'The SEO title is required.', 'seo.title'));
  }
  if (!profile.seo.description.trim()) {
    issues.push(
      err('FIELD_REQUIRED:seo.description', 'The SEO meta description is required.', 'seo.description'),
    );
  }
  return issues;
}

/** WCAG relative luminance for a #rgb / #rrggbb hex color. */
export function luminance(hex: string): number {
  let h = hex.replace('#', '');
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  const r = parseInt(h.slice(0, 2), 16) / 255;
  const g = parseInt(h.slice(2, 4), 16) / 255;
  const b = parseInt(h.slice(4, 6), 16) / 255;
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** WCAG contrast ratio between two hex colors, e.g. 4.5. */
export function contrastRatio(fg: string, bg: string): number {
  const l1 = luminance(fg);
  const l2 = luminance(bg);
  const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

/** Theme color tokens must meet WCAG AA 4.5:1. */
export function validateContrast(tokens: ContrastToken[]): Issue[] {
  return tokens
    .filter((t) => contrastRatio(t.fg, t.bg) < 4.5)
    .map((t) =>
      err(
        `CONTRAST_FAIL:${t.name}`,
        `Color token "${t.name}" has contrast ${contrastRatio(t.fg, t.bg).toFixed(2)}:1, below WCAG AA 4.5:1 (${t.fg} on ${t.bg}).`,
      ),
    );
}

const VOID_ELEMENTS = new Set([
  'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
  'link', 'meta', 'param', 'source', 'track', 'wbr',
]);

/** Structural checks: html/head/body/main present, tag balance, no <script>. */
export function validateHtml(path: string, html: string): Issue[] {
  const issues: Issue[] = [];
  const lower = html.toLowerCase();
  if (!/<html[\s>]/.test(lower)) issues.push(err(`HTML_INVALID:missing-html`, `${path}: missing <html> element.`));
  if (!/<head[\s>]/.test(lower)) issues.push(err(`HTML_INVALID:missing-head`, `${path}: missing <head> element.`));
  if (!/<body[\s>]/.test(lower)) issues.push(err(`HTML_INVALID:missing-body`, `${path}: missing <body> element.`));
  if (!/<main[\s>]/.test(lower)) issues.push(err(`HTML_INVALID:missing-main`, `${path}: missing <main> landmark.`));
  if (/<script[\s>]/.test(lower)) {
    issues.push(err('HTML_INVALID:script-present', `${path}: exported pages must not contain <script> tags.`));
  }

  // Tag balance: strip comments, doctype, and CDATA-ish XML declarations.
  const stripped = html
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<![A-Z][^>]*>/gi, '')
    .replace(/<\?[\s\S]*?\?>/g, '');
  const tagRe = /<\/?([a-zA-Z][a-zA-Z0-9-]*)\b[^>]*?>/g;
  const stack: string[] = [];
  let m: RegExpExecArray | null;
  while ((m = tagRe.exec(stripped)) !== null) {
    const full = m[0] ?? '';
    const name = (m[1] ?? '').toLowerCase();
    const isClose = full.startsWith('</');
    const selfClosing = full.endsWith('/>') || VOID_ELEMENTS.has(name);
    if (isClose) {
      const idx = stack.lastIndexOf(name);
      if (idx === -1) {
        issues.push(err(`HTML_INVALID:unbalanced-${name}`, `${path}: closing </${name}> without a matching open tag.`));
      } else {
        // Tags left open above the match were never closed properly.
        for (let i = stack.length - 1; i > idx; i--) {
          const unclosed = stack.pop() as string;
          issues.push(
            err(`HTML_INVALID:unbalanced-${unclosed}`, `${path}: <${unclosed}> was never closed before </${name}>.`),
          );
        }
        stack.pop(); // the matching open tag
      }
    } else if (!selfClosing) {
      stack.push(name);
    }
  }
  for (const name of stack.reverse()) {
    issues.push(err(`HTML_INVALID:unbalanced-${name}`, `${path}: <${name}> was never closed.`));
  }
  return issues;
}

/** True for links we must resolve inside the export (not external/mailto/etc). */
export function isInternalHref(href: string): boolean {
  const h = href.trim();
  if (!h) return false;
  return !/^(https?:|mailto:|tel:|data:|#)/i.test(h) && !h.startsWith('//');
}

/** Resolve a relative href against the page path it appears on. */
export function resolveHref(pagePath: string, href: string): string {
  const clean = (href.split('#')[0] ?? '').split('?')[0] ?? '';
  if (clean.startsWith('/')) return clean.slice(1);
  const dir = pagePath.includes('/') ? pagePath.slice(0, pagePath.lastIndexOf('/') + 1) : '';
  const parts: string[] = [];
  for (const seg of (dir + clean).split('/')) {
    if (seg === '' || seg === '.') continue;
    if (seg === '..') parts.pop();
    else parts.push(seg);
  }
  return parts.join('/');
}

function extractAttrs(html: string, attr: 'href' | 'src'): string[] {
  const re = new RegExp(`${attr}\\s*=\\s*("([^"]*)"|'([^']*)')`, 'gi');
  const out: string[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(html)) !== null) out.push(m[2] ?? m[3] ?? '');
  return out;
}

const IMAGE_EXT = /\.(png|jpe?g|gif|webp|svg|ico|avif)$/i;

/** Internal <a href> targets must exist among the exported files. */
export function validateLinks(files: Record<string, string>): Issue[] {
  const issues: Issue[] = [];
  for (const [path, content] of Object.entries(files)) {
    if (!path.endsWith('.html')) continue;
    for (const href of extractAttrs(content, 'href')) {
      if (!isInternalHref(href)) continue;
      if (IMAGE_EXT.test(href)) continue; // handled by validateAssets
      const target = resolveHref(path, href);
      if (!(target in files)) {
        issues.push(err(`LINK_BROKEN:${href}`, `${path}: link target "${href}" does not resolve to an exported file.`));
      }
    }
  }
  return issues;
}

/** Referenced local images must exist among the exported files. */
export function validateAssets(files: Record<string, string>): Issue[] {
  const issues: Issue[] = [];
  const seen = new Set<string>();
  const check = (from: string, ref: string) => {
    if (!isInternalHref(ref) || seen.has(ref)) return;
    seen.add(ref);
    const target = resolveHref(from, ref);
    if (!(target in files)) {
      issues.push(err(`ASSET_MISSING:${ref}`, `${from}: referenced asset "${ref}" is not in the export.`));
    }
  };
  for (const [path, content] of Object.entries(files)) {
    if (path.endsWith('.html')) {
      for (const src of extractAttrs(content, 'src')) if (IMAGE_EXT.test(src) || isInternalHref(src)) check(path, src);
      for (const href of extractAttrs(content, 'href')) if (IMAGE_EXT.test(href)) check(path, href);
    } else if (path.endsWith('.css')) {
      const re = /url\(\s*("([^"]*)"|'([^']*)'|([^)"']+))\s*\)/gi;
      let m: RegExpExecArray | null;
      while ((m = re.exec(content)) !== null) {
        const ref = m[2] ?? m[3] ?? m[4] ?? '';
        if (IMAGE_EXT.test(ref)) check(path, ref);
      }
    }
  }
  return issues;
}

/** Full export validation: profile fields, HTML structure, links, assets, contrast. */
export function validateExport(
  profile: BusinessProfile,
  files: Record<string, string>,
  theme: ThemeModule,
): Issue[] {
  const issues: Issue[] = [...validateProfile(profile)];
  for (const [path, content] of Object.entries(files)) {
    if (path.endsWith('.html')) issues.push(...validateHtml(path, content));
  }
  issues.push(...validateLinks(files));
  issues.push(...validateAssets(files));
  issues.push(...validateContrast(theme.tokens));
  return issues;
}

/** Export is blocked when any issue has severity "error". */
export function hasBlockingErrors(issues: Issue[]): boolean {
  return issues.some((i) => i.severity === 'error');
}
