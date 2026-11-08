/**
 * "Mainstreet" — original generic theme for local businesses.
 *
 * Clean, friendly design: hero, services, hours and contact. Mobile-first,
 * semantic HTML, no external assets, no stock imagery. All CSS written from
 * scratch.
 */
import type { BusinessProfile, ThemeInfo } from '../../../shared/types.js';
import {
  baseUrlOf,
  buildPage,
  contactBlock,
  footerInner,
  hoursBlock,
  navList,
  robotsTxt,
  sitemapXml,
  escapeHtml,
  type ContrastToken,
  type RenderOptions,
  type ThemeModule,
} from './common.js';

export const info: ThemeInfo = {
  id: 'localbiz',
  name: 'Mainstreet',
  description: 'Clean generic theme for local businesses: hero, services, hours and contact.',
  businessTypes: ['localbiz'],
  pages: ['index.html', 'services.html', 'contact.html', 'style.css', 'sitemap.xml', 'robots.txt'],
};

export const tokens: ContrastToken[] = [
  { name: 'ink-on-white', fg: '#1f2937', bg: '#ffffff' },
  { name: 'accent-on-white', fg: '#1d4ed8', bg: '#ffffff' },
  { name: 'muted-on-white', fg: '#4b5563', bg: '#ffffff' },
  { name: 'white-on-ink', fg: '#ffffff', bg: '#1f2937' },
  { name: 'white-on-accent', fg: '#ffffff', bg: '#1d4ed8' },
];

const CSS = `:root {
  --white: #ffffff;
  --ink: #1f2937;
  --accent: #1d4ed8;
  --accent-dark: #1a44b8;
  --muted: #4b5563;
  --line: #e5e7eb;
  --tint: #eff4ff;
  --radius: 0.75rem;
  --max: 66rem;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  font-family: var(--font);
  background: var(--white);
  color: var(--ink);
  line-height: 1.6;
}
.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  background: var(--ink);
  color: var(--white);
  padding: 0.75rem 1rem;
  z-index: 100;
}
.skip-link:focus { left: 0; }
.site-header { border-bottom: 1px solid var(--line); background: var(--white); }
.site-header .wrap {
  max-width: var(--max);
  margin: 0 auto;
  padding: 1rem 1.25rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 2rem;
}
.brand { margin: 0; font-size: 1.4rem; font-weight: 800; }
.brand a { color: var(--ink); text-decoration: none; }
.site-header nav ul { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 0.25rem 1.25rem; }
.site-header nav a { color: var(--ink); text-decoration: none; padding: 0.4rem 0.1rem; }
.site-header nav a:hover { color: var(--accent); }
.site-header nav a[aria-current="page"] { color: var(--accent); font-weight: 700; }
main { max-width: var(--max); margin: 0 auto; padding: 0 1.25rem 3rem; }
.hero {
  background: linear-gradient(180deg, var(--tint), var(--white));
  border-bottom: 1px solid var(--line);
  margin: 0 -1.25rem 2rem;
  padding: 3rem 1.25rem;
  text-align: center;
}
.hero h2 { margin: 0 0 0.75rem; font-size: 2rem; line-height: 1.25; }
.hero p { margin: 0 auto; max-width: 42rem; color: var(--muted); }
.btn {
  display: inline-block;
  background: var(--accent);
  color: #ffffff;
  text-decoration: none;
  font-weight: 700;
  padding: 0.7rem 1.5rem;
  border-radius: 999px;
  margin-top: 1.5rem;
}
.btn:hover { background: var(--accent-dark); }
h2.section-title { font-size: 1.5rem; margin: 2.5rem 0 1rem; }
.grid { display: grid; gap: 1.25rem; grid-template-columns: 1fr; }
@media (min-width: 40rem) { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 60rem) { .grid { grid-template-columns: repeat(3, 1fr); } }
.card {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.4rem;
  background: var(--white);
}
.card h3 { margin: 0 0 0.5rem; font-size: 1.15rem; color: var(--accent); }
.card p { margin: 0; color: var(--muted); }
.split { display: grid; gap: 1.5rem; grid-template-columns: 1fr; margin-top: 2.5rem; }
@media (min-width: 48rem) { .split { grid-template-columns: 1fr 1fr; } }
.panel {
  background: var(--tint);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.5rem;
}
.panel h3 { margin: 0 0 0.75rem; font-size: 1.2rem; }
.hours { list-style: none; padding: 0; margin: 0.5rem 0 0; }
.hours li { padding: 0.35rem 0; border-bottom: 1px dotted var(--line); }
.label { font-weight: 700; }
.about p { max-width: 46rem; color: var(--muted); }
.site-footer { border-top: 1px solid var(--line); margin-top: 2rem; background: var(--white); }
.site-footer .wrap { max-width: var(--max); margin: 0 auto; padding: 1.75rem 1.25rem; }
.site-footer .site-name { margin: 0 0 0.5rem; font-weight: 700; }
.site-footer .social { list-style: none; margin: 0 0 0.75rem; padding: 0; display: flex; flex-wrap: wrap; gap: 0.25rem 1rem; }
.site-footer a { color: var(--accent); }
.site-footer .fine { margin: 0.75rem 0 0; font-size: 0.85rem; color: var(--muted); }
`;

function header(profile: BusinessProfile, active: string): string {
  return `<header class="site-header">
      <div class="wrap">
        <p class="brand"><a href="index.html">${escapeHtml(profile.name)}</a></p>
        ${navList(
          [
            { href: 'index.html', label: 'Home' },
            { href: 'services.html', label: 'Services' },
            { href: 'contact.html', label: 'Contact' },
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

function serviceCards(profile: BusinessProfile): string {
  if (!profile.services.length) return '<p>No services listed yet.</p>';
  return `<div class="grid">\n${profile.services
    .map(
      (s) => `      <article class="card">
        <h3>${escapeHtml(s.title)}</h3>
        <p>${escapeHtml(s.description)}</p>
      </article>`,
    )
    .join('\n')}\n    </div>`;
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
        <a class="btn" href="services.html">Explore our services</a>
      </section>
      <h2 class="section-title">What we do</h2>
      ${serviceCards(profile)}
      <div class="split">
        <section class="panel about" aria-label="About">
          <h3>About us</h3>
          ${profile.about.trim() ? `<p>${escapeHtml(profile.about)}</p>` : '<p>Details coming soon.</p>'}
        </section>
        <section class="panel" aria-label="Hours">
          ${hoursBlock(profile)}
        </section>
      </div>`,
    footer: footer(profile),
  });

  const servicesHtml = buildPage({
    head: { title: `Services — ${seoTitle}`, description: seoDesc, baseUrl, pagePath: 'services.html', siteName },
    header: header(profile, 'services.html'),
    main: `      <h2 class="section-title" style="margin-top:2rem">Our services</h2>
      ${serviceCards(profile)}`,
    footer: footer(profile),
  });

  const contactHtml = buildPage({
    head: { title: `Contact — ${seoTitle}`, description: seoDesc, baseUrl, pagePath: 'contact.html', siteName },
    header: header(profile, 'contact.html'),
    main: `      <h2 class="section-title" style="margin-top:2rem">Get in touch</h2>
      <div class="split" style="margin-top:0">
        <section class="panel" aria-label="Contact details">
          ${contactBlock(profile)}
        </section>
        <section class="panel" aria-label="Hours">
          ${hoursBlock(profile)}
        </section>
      </div>`,
    footer: footer(profile),
  });

  const pages = ['index.html', 'services.html', 'contact.html'];
  return {
    files: {
      'index.html': indexHtml,
      'services.html': servicesHtml,
      'contact.html': contactHtml,
      'style.css': CSS,
      'sitemap.xml': sitemapXml(baseUrl, pages),
      'robots.txt': robotsTxt(baseUrl),
    },
  };
}

export const theme: ThemeModule = { info, tokens, renderSite };
export default theme;
