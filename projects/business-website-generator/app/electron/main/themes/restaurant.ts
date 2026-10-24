/**
 * "Hearth" — original theme for restaurants.
 *
 * Warm, appetizing design: menu sections with prices, an hours table and a
 * location block. Mobile-first, semantic HTML, no external assets, no stock
 * imagery. All CSS written from scratch.
 */
import type { BusinessProfile, ThemeInfo } from '../../../shared/types.js';
import {
  baseUrlOf,
  buildPage,
  contactBlock,
  footerInner,
  navList,
  robotsTxt,
  sitemapXml,
  escapeHtml,
  type ContrastToken,
  type RenderOptions,
  type ThemeModule,
} from './common.js';

export const info: ThemeInfo = {
  id: 'restaurant',
  name: 'Hearth',
  description: 'Warm theme for restaurants: menu sections with prices, an hours table and a location block.',
  businessTypes: ['restaurant'],
  pages: ['index.html', 'menu.html', 'contact.html', 'style.css', 'sitemap.xml', 'robots.txt'],
};

export const tokens: ContrastToken[] = [
  { name: 'ink-on-cream', fg: '#2b2118', bg: '#fbf6ec' },
  { name: 'accent-on-cream', fg: '#7c2d12', bg: '#fbf6ec' },
  { name: 'cream-on-ink', fg: '#fbf6ec', bg: '#2b2118' },
  { name: 'white-on-accent', fg: '#ffffff', bg: '#7c2d12' },
];

const CSS = `:root {
  --cream: #fbf6ec;
  --ink: #2b2118;
  --accent: #7c2d12;
  --accent-dark: #5f220d;
  --muted: #6b5d4d;
  --line: #e8dcc4;
  --card: #ffffff;
  --radius: 0.6rem;
  --max: 64rem;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  font-family: var(--font);
  background: var(--cream);
  color: var(--ink);
  line-height: 1.6;
}
.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  background: var(--ink);
  color: var(--cream);
  padding: 0.75rem 1rem;
  z-index: 100;
}
.skip-link:focus { left: 0; }
.site-header {
  background: var(--ink);
  color: var(--cream);
}
.site-header .wrap { max-width: var(--max); margin: 0 auto; padding: 1.75rem 1.25rem 1.25rem; text-align: center; }
.brand { margin: 0; font-size: 2rem; }
.brand a { color: var(--cream); text-decoration: none; }
.tagline { margin: 0.3rem 0 0; color: #e0d5bd; font-style: italic; }
.site-header nav ul {
  list-style: none;
  margin: 1rem 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.25rem 1.5rem;
}
.site-header nav a { color: var(--cream); text-decoration: none; padding: 0.25rem 0.1rem; }
.site-header nav a:hover { text-decoration: underline; }
.site-header nav a[aria-current="page"] { font-weight: 700; text-decoration: underline; text-underline-offset: 0.3rem; }
main { max-width: var(--max); margin: 0 auto; padding: 1.75rem 1.25rem 3rem; }
.hero {
  text-align: center;
  padding: 2.5rem 1.5rem;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  margin-bottom: 2rem;
}
.hero h2 { margin: 0 0 0.5rem; font-size: 1.8rem; color: var(--accent); }
.hero p { margin: 0.5rem auto 0; color: var(--muted); max-width: 40rem; }
.btn {
  display: inline-block;
  background: var(--accent);
  color: #ffffff;
  text-decoration: none;
  font-weight: 700;
  padding: 0.7rem 1.5rem;
  border-radius: 999px;
  margin-top: 1.25rem;
}
.btn:hover { background: var(--accent-dark); }
.menu-section { margin-bottom: 2.5rem; }
.menu-section > h3 {
  font-size: 1.5rem;
  color: var(--accent);
  border-bottom: 3px double var(--line);
  padding-bottom: 0.4rem;
  margin: 0 0 1rem;
}
.dish { margin: 0 0 1.1rem; }
.dish .row { display: flex; align-items: baseline; gap: 0.75rem; }
.dish .name { font-weight: 700; font-size: 1.08rem; }
.dish .dots { flex: 1; border-bottom: 2px dotted var(--line); transform: translateY(-0.25rem); }
.dish .price { font-weight: 700; color: var(--accent); white-space: nowrap; }
.dish .desc { margin: 0.25rem 0 0; color: var(--muted); }
.two-col { display: grid; gap: 1.5rem; grid-template-columns: 1fr; }
@media (min-width: 48rem) { .two-col { grid-template-columns: 1fr 1fr; } }
.panel {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.5rem;
}
.panel h3 { margin: 0 0 0.75rem; font-size: 1.25rem; }
table.hours { width: 100%; border-collapse: collapse; }
table.hours caption { text-align: left; font-weight: 700; font-size: 1.25rem; padding-bottom: 0.5rem; }
table.hours th, table.hours td { text-align: left; padding: 0.45rem 0.25rem; border-bottom: 1px solid var(--line); }
table.hours th { font-weight: 600; }
.location p { margin: 0.4rem 0; }
.label { font-weight: 700; }
.site-footer { background: var(--ink); color: #e0d5bd; margin-top: 2rem; }
.site-footer .wrap { max-width: var(--max); margin: 0 auto; padding: 1.75rem 1.25rem; text-align: center; }
.site-footer .site-name { margin: 0 0 0.5rem; font-weight: 700; color: var(--cream); }
.site-footer .social { list-style: none; margin: 0 0 0.75rem; padding: 0; display: flex; flex-wrap: wrap; justify-content: center; gap: 0.25rem 1rem; }
.site-footer a { color: var(--cream); }
.site-footer .fine { margin: 0.75rem 0 0; font-size: 0.85rem; }
ul.hours-list { list-style: none; padding: 0; margin: 0.5rem 0 0; }
ul.hours-list li { padding: 0.35rem 0; border-bottom: 1px dotted var(--line); }
`;

function header(profile: BusinessProfile, active: string): string {
  return `<header class="site-header">
      <div class="wrap">
        <p class="brand"><a href="index.html">${escapeHtml(profile.name)}</a></p>
        ${profile.tagline.trim() ? `<p class="tagline">${escapeHtml(profile.tagline)}</p>` : ''}
        ${navList(
          [
            { href: 'index.html', label: 'Home' },
            { href: 'menu.html', label: 'Menu' },
            { href: 'contact.html', label: 'Visit Us' },
          ],
          active,
        )}
      </div>
    </header>`;
}

function footer(profile: BusinessProfile): string {
  return `<footer class="site-footer">
      <div class="wrap">
${footerInner(profile, '<p class="fine">Built with the Small Business Website Generator.</p>')}
      </div>
    </footer>`;
}

function menuSections(profile: BusinessProfile): string {
  if (!profile.menuSections.length) return '<p>Our menu is coming soon — please call ahead.</p>';
  return profile.menuSections
    .map((section) => {
      const items = section.items
        .map(
          (item) => `        <div class="dish">
          <div class="row">
            <span class="name">${escapeHtml(item.name)}</span>
            <span class="dots" aria-hidden="true"></span>
            ${item.price.trim() ? `<span class="price">${escapeHtml(item.price)}</span>` : ''}
          </div>
          ${item.description.trim() ? `<p class="desc">${escapeHtml(item.description)}</p>` : ''}
        </div>`,
        )
        .join('\n');
      return `      <section class="menu-section" aria-label="${escapeHtml(section.name)}">
        <h3>${escapeHtml(section.name)}</h3>
${items}
      </section>`;
    })
    .join('\n');
}

function hoursTable(profile: BusinessProfile): string {
  const label = profile.hours.label.trim() || 'Hours';
  const lines = profile.hours.lines.filter((l) => l.trim());
  if (!lines.length) return `<section aria-label="${escapeHtml(label)}"><p>Hours coming soon.</p></section>`;
  const rows = lines
    .map((line) => {
      const parts = line.split(/[:—–-]/);
      const day = (parts[0] ?? line).trim();
      const time = parts.slice(1).join(':').trim();
      return `          <tr><th scope="row">${escapeHtml(day || line)}</th><td>${escapeHtml(time || '—')}</td></tr>`;
    })
    .join('\n');
  return `<table class="hours">
        <caption>${escapeHtml(label)}</caption>
        <tbody>
${rows}
        </tbody>
      </table>`;
}

function locationBlock(profile: BusinessProfile): string {
  return `<section class="panel location" aria-label="Location">
        <h3>Find us</h3>
        ${contactBlock(profile)}
      </section>`;
}

function renderSite(profile: BusinessProfile, opts?: RenderOptions) {
  const baseUrl = baseUrlOf(profile, opts);
  const siteName = profile.name;
  const seoTitle = profile.seo.title.trim() || siteName;
  const seoDesc = profile.seo.description.trim() || profile.tagline.trim() || `Official website of ${siteName}.`;

  const indexHtml = buildPage({
    head: { title: seoTitle, description: seoDesc, baseUrl, pagePath: 'index.html', siteName },
    header: header(profile, 'index.html'),
    main: `      <section class="hero" aria-label="Welcome">
        <h2>${escapeHtml(profile.tagline.trim() || siteName)}</h2>
        ${profile.about.trim() ? `<p>${escapeHtml(profile.about.split('\n')[0] ?? '')}</p>` : ''}
        <a class="btn" href="menu.html">View our menu</a>
      </section>
      <div class="two-col">
        <section class="panel" aria-label="About">
          <h3>About us</h3>
          ${profile.about.trim() ? `<p>${escapeHtml(profile.about)}</p>` : '<p>Details coming soon.</p>'}
        </section>
        <section class="panel" aria-label="Hours">
          ${hoursTable(profile)}
        </section>
      </div>`,
    footer: footer(profile),
  });

  const menuHtml = buildPage({
    head: { title: `Menu — ${seoTitle}`, description: seoDesc, baseUrl, pagePath: 'menu.html', siteName },
    header: header(profile, 'menu.html'),
    main: `      ${menuSections(profile)}`,
    footer: footer(profile),
  });

  const contactHtml = buildPage({
    head: { title: `Visit Us — ${seoTitle}`, description: seoDesc, baseUrl, pagePath: 'contact.html', siteName },
    header: header(profile, 'contact.html'),
    main: `      <div class="two-col">
        ${locationBlock(profile)}
        <section class="panel" aria-label="Hours">
          ${hoursTable(profile)}
        </section>
      </div>`,
    footer: footer(profile),
  });

  const pages = ['index.html', 'menu.html', 'contact.html'];
  return {
    files: {
      'index.html': indexHtml,
      'menu.html': menuHtml,
      'contact.html': contactHtml,
      'style.css': CSS,
      'sitemap.xml': sitemapXml(baseUrl, pages),
      'robots.txt': robotsTxt(baseUrl),
    },
  };
}

export const theme: ThemeModule = { info, tokens, renderSite };
export default theme;
