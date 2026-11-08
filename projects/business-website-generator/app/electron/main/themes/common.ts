/**
 * Shared helpers for the four original BWG themes.
 *
 * Every theme renders a complete static site as a map of relative file paths
 * to file contents. Rendering is pure and deterministic: the same
 * BusinessProfile + options always produce byte-identical output (no
 * timestamps; sitemap omits lastmod).
 */
import type { BusinessProfile, ThemeInfo } from '../../../shared/types.js';
import { escapeHtml } from '../../../shared/escape.js';

export interface RenderOptions {
  /** Absolute base URL used for og:url and sitemap locs. Defaults to a placeholder. */
  baseUrl?: string;
}

export interface ContrastToken {
  /** Stable token name, e.g. "accent-on-paper". */
  name: string;
  /** Foreground hex color, e.g. "#9a3f16". */
  fg: string;
  /** Background hex color, e.g. "#faf7f1". */
  bg: string;
}

export interface ThemeModule {
  info: ThemeInfo;
  /** Foreground/background pairs that must meet WCAG AA 4.5:1. */
  tokens: ContrastToken[];
  renderSite: (profile: BusinessProfile, opts?: RenderOptions) => { files: Record<string, string> };
}

export const DEFAULT_BASE_URL = 'https://example.com';

export function baseUrlOf(profile: BusinessProfile, opts?: RenderOptions): string {
  if (opts?.baseUrl && opts.baseUrl.trim()) return opts.baseUrl.replace(/\/+$/, '');
  const w = profile.contact.website.trim();
  if (/^https?:\/\//i.test(w)) return w.replace(/\/+$/, '');
  return DEFAULT_BASE_URL;
}

export interface NavLink {
  href: string;
  label: string;
}

/** Primary nav list; `active` is the href of the current page. */
export function navList(links: NavLink[], active: string): string {
  const items = links
    .map((l) => {
      const current = l.href === active ? ' aria-current="page"' : '';
      return `<li><a href="${escapeHtml(l.href)}"${current}>${escapeHtml(l.label)}</a></li>`;
    })
    .join('\n          ');
  return `<nav aria-label="Primary">\n          <ul>\n          ${items}\n          </ul>\n        </nav>`;
}

export interface HeadOpts {
  title: string;
  description: string;
  baseUrl: string;
  pagePath: string;
  siteName: string;
}

/** <head> with SEO title, meta description and Open Graph tags. */
export function buildHead(o: HeadOpts): string {
  const title = escapeHtml(o.title);
  const description = escapeHtml(o.description);
  const url = escapeHtml(`${o.baseUrl}/${o.pagePath}`);
  const siteName = escapeHtml(o.siteName);
  return `<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${title}</title>
    <meta name="description" content="${description}" />
    <meta property="og:type" content="website" />
    <meta property="og:title" content="${title}" />
    <meta property="og:description" content="${description}" />
    <meta property="og:url" content="${url}" />
    <meta property="og:site_name" content="${siteName}" />
    <link rel="stylesheet" href="style.css" />
  </head>`;
}

export interface PageOpts {
  head: HeadOpts;
  header: string;
  main: string;
  footer: string;
}

/** Full HTML document shell: skip link, header, <main id="main">, footer. */
export function buildPage(o: PageOpts): string {
  return `<!DOCTYPE html>
<html lang="en">
  ${buildHead(o.head)}
  <body>
    <a class="skip-link" href="#main">Skip to main content</a>
    ${o.header}
    <main id="main">
${o.main}
    </main>
    ${o.footer}
  </body>
</html>
`;
}

/** Shared, unobtrusive footer block; themes wrap it in their own styling. */
export function footerInner(profile: BusinessProfile, extra: string): string {
  const name = escapeHtml(profile.name);
  const social = profile.social
    .filter((s) => s.url.trim())
    .map(
      (s) =>
        `<li><a href="${escapeHtml(s.url)}" rel="noopener">${escapeHtml(s.label.trim() || s.url)}</a></li>`,
    )
    .join('\n        ');
  const socialHtml = social ? `\n      <ul class="social">\n        ${social}\n      </ul>` : '';
  return `      <p class="site-name">${name}</p>${socialHtml}\n      ${extra}`;
}

/** Contact block reused on contact pages and footers. */
export function contactBlock(profile: BusinessProfile): string {
  const c = profile.contact;
  const rows: string[] = [];
  if (c.phone.trim())
    rows.push(
      `<p><span class="label">Phone</span> <a href="tel:${escapeHtml(c.phone.replace(/[^+\d]/g, ''))}">${escapeHtml(c.phone)}</a></p>`,
    );
  if (c.email.trim())
    rows.push(
      `<p><span class="label">Email</span> <a href="mailto:${escapeHtml(c.email)}">${escapeHtml(c.email)}</a></p>`,
    );
  if (c.address.trim())
    rows.push(`<p><span class="label">Address</span> ${escapeHtml(c.address)}</p>`);
  if (c.website.trim()) {
    const href = /^https?:\/\//i.test(c.website.trim()) ? c.website.trim() : `https://${c.website.trim()}`;
    rows.push(
      `<p><span class="label">Website</span> <a href="${escapeHtml(href)}" rel="noopener">${escapeHtml(c.website)}</a></p>`,
    );
  }
  return rows.length ? rows.join('\n      ') : '<p>Contact details coming soon.</p>';
}

/** Hours definition list. */
export function hoursBlock(profile: BusinessProfile): string {
  const label = profile.hours.label.trim() || 'Hours';
  const lines = profile.hours.lines.filter((l) => l.trim());
  const items = lines.map((l) => `<li>${escapeHtml(l)}</li>`).join('\n        ');
  return `<section aria-label="${escapeHtml(label)}">\n      <h2>${escapeHtml(label)}</h2>\n      ${
        items ? `<ul class="hours">\n        ${items}\n      </ul>` : '<p>Hours coming soon.</p>'
      }\n    </section>`;
}

export function sitemapXml(baseUrl: string, pages: string[]): string {
  const urls = pages
    .filter((p) => p.endsWith('.html'))
    .map((p) => `  <url>\n    <loc>${escapeHtml(`${baseUrl}/${p}`)}</loc>\n  </url>`)
    .join('\n');
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
}

export function robotsTxt(baseUrl: string): string {
  return `User-agent: *\nAllow: /\nSitemap: ${baseUrl}/sitemap.xml\n`;
}

export { escapeHtml };
