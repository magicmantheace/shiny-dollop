/**
 * "Ironline" — original theme for trades businesses.
 *
 * Bold workmanlike design: dark slate header, services grid, service-area
 * list, and a prominent quote call-to-action. Mobile-first, semantic HTML,
 * no external assets, no stock imagery. All CSS written from scratch.
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
  id: 'trades',
  name: 'Ironline',
  description: 'Bold, workmanlike theme for tradespeople: services grid, service-area list and a quote call-to-action.',
  businessTypes: ['trades'],
  pages: ['index.html', 'services.html', 'contact.html', 'style.css', 'sitemap.xml', 'robots.txt'],
};

export const tokens: ContrastToken[] = [
  { name: 'ink-on-paper', fg: '#22262c', bg: '#faf7f1' },
  { name: 'accent-on-paper', fg: '#9a3f16', bg: '#faf7f1' },
  { name: 'muted-on-paper', fg: '#5b6068', bg: '#faf7f1' },
  { name: 'paper-on-ink', fg: '#faf7f1', bg: '#22262c' },
  { name: 'white-on-accent', fg: '#ffffff', bg: '#9a3f16' },
];

const CSS = `:root {
  --paper: #faf7f1;
  --ink: #22262c;
  --accent: #9a3f16;
  --accent-dark: #7c3312;
  --muted: #5b6068;
  --line: #e3dccf;
  --card: #ffffff;
  --radius: 0.5rem;
  --max: 68rem;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  font-family: var(--font);
  background: var(--paper);
  color: var(--ink);
  line-height: 1.6;
}
.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  background: var(--ink);
  color: var(--paper);
  padding: 0.75rem 1rem;
  z-index: 100;
}
.skip-link:focus { left: 0; }
.site-header {
  background: var(--ink);
  color: var(--paper);
  border-bottom: 0.35rem solid var(--accent);
}
.site-header .wrap {
  max-width: var(--max);
  margin: 0 auto;
  padding: 1rem 1.25rem;
}
.brand { margin: 0; font-size: 1.6rem; letter-spacing: 0.02em; }
.brand a { color: var(--paper); text-decoration: none; }
.tagline { margin: 0.25rem 0 0; color: #d8d3c8; font-size: 0.95rem; }
.site-header nav ul {
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem 1.25rem;
}
.site-header nav a {
  color: var(--paper);
  text-decoration: none;
  padding: 0.25rem 0;
  border-bottom: 2px solid transparent;
}
.site-header nav a:hover { border-bottom-color: var(--accent); }
.site-header nav a[aria-current="page"] { border-bottom-color: var(--accent); font-weight: 700; }
main { max-width: var(--max); margin: 0 auto; padding: 1.5rem 1.25rem 3rem; }
.hero {
  background: var(--card);
  border: 1px solid var(--line);
  border-left: 0.5rem solid var(--accent);
  border-radius: var(--radius);
  padding: 1.75rem 1.5rem;
  margin-bottom: 2rem;
}
.hero h2 { margin: 0 0 0.5rem; font-size: 1.9rem; line-height: 1.25; }
.hero p { margin: 0.5rem 0 0; color: var(--muted); max-width: 44rem; }
.cta-row { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 1.25rem; }
.btn {
  display: inline-block;
  background: var(--accent);
  color: #ffffff;
  text-decoration: none;
  font-weight: 700;
  padding: 0.7rem 1.4rem;
  border-radius: var(--radius);
}
.btn:hover { background: var(--accent-dark); }
.btn-ghost {
  background: transparent;
  color: var(--accent);
  border: 2px solid var(--accent);
}
.btn-ghost:hover { background: var(--accent); color: #ffffff; }
.grid { display: grid; gap: 1.25rem; grid-template-columns: 1fr; }
@media (min-width: 40rem) { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 60rem) { .grid { grid-template-columns: repeat(3, 1fr); } }
.card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.25rem;
}
.card h3 { margin: 0 0 0.5rem; font-size: 1.15rem; }
.card h3 a { color: var(--ink); text-decoration: none; }
.card h3 a:hover { color: var(--accent); text-decoration: underline; }
.card p { margin: 0; color: var(--muted); }
.section-title { font-size: 1.5rem; margin: 2.5rem 0 1rem; padding-bottom: 0.4rem; border-bottom: 2px solid var(--line); }
.service-area {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.25rem 1.5rem;
}
.service-area ul { margin: 0.5rem 0 0; padding-left: 1.25rem; color: var(--muted); }
.quote-band {
  margin-top: 2.5rem;
  background: var(--ink);
  color: var(--paper);
  border-radius: var(--radius);
  padding: 2rem 1.5rem;
  text-align: center;
}
.quote-band h2 { margin: 0 0 0.5rem; }
.quote-band p { margin: 0 0 1.25rem; color: #d8d3c8; }
.hours { list-style: none; padding: 0; margin: 0.5rem 0 0; }
.hours li { padding: 0.35rem 0; border-bottom: 1px dotted var(--line); }
.label { font-weight: 700; }
.site-footer {
  background: var(--ink);
  color: #d8d3c8;
  margin-top: 2rem;
}
.site-footer .wrap { max-width: var(--max); margin: 0 auto; padding: 1.75rem 1.25rem; }
.site-footer .site-name { margin: 0 0 0.5rem; font-weight: 700; color: var(--paper); }
.site-footer .social { list-style: none; margin: 0 0 0.75rem; padding: 0; display: flex; flex-wrap: wrap; gap: 0.25rem 1rem; }
.site-footer a { color: var(--paper); }
.site-footer .fine { margin: 0.75rem 0 0; font-size: 0.85rem; }
.contact-grid { display: grid; gap: 1.5rem; grid-template-columns: 1fr; }
@media (min-width: 48rem) { .contact-grid { grid-template-columns: 1fr 1fr; } }
`;

function header(profile: BusinessProfile, active: string): string {
  const name = escapeHtml(profile.name);
  const tagline = profile.tagline.trim()
    ? `<p class="tagline">${escapeHtml(profile.tagline)}</p>`
    : '';
  return `<header class="site-header">
      <div class="wrap">
        <p class="brand"><a href="index.html">${name}</a></p>
        ${tagline}
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

function serviceCards(profile: BusinessProfile, limit?: number): string {
  const services = limit ? profile.services.slice(0, limit) : profile.services;
  if (!services.length) return '<p>No services listed yet.</p>';
  return `<div class="grid" role="list">\n${services
    .map(
      (s) => `      <article class="card" role="listitem">
        <h3>${escapeHtml(s.title)}</h3>
        <p>${escapeHtml(s.description)}</p>
      </article>`,
    )
    .join('\n')}\n    </div>`;
}

function serviceArea(profile: BusinessProfile): string {
  const address = profile.contact.address.trim();
  return `<section class="service-area" aria-label="Service area">
      <h2 class="section-title" style="margin-top:0">Where we work</h2>
      ${
        address
          ? `<p>Based at ${escapeHtml(address)} and serving the surrounding area.</p>
      <ul>
        <li>${escapeHtml(address)}</li>
        <li>Surrounding communities — call for travel details</li>
      </ul>`
          : '<p>Service area varies by project — contact us for availability in your area.</p>'
      }
    </section>`;
}

function quoteBand(profile: BusinessProfile): string {
  const phone = profile.contact.phone.trim();
  return `<section class="quote-band" aria-label="Request a quote">
      <h2>Get a free quote</h2>
      <p>Tell us about your project and we will get back to you with a fair, honest price.</p>
      <div class="cta-row" style="justify-content:center">
        ${
          phone
            ? `<a class="btn" href="tel:${escapeHtml(phone.replace(/[^+\d]/g, ''))}">Call ${escapeHtml(phone)}</a>`
            : ''
        }
        <a class="btn btn-ghost" href="contact.html">Contact us</a>
      </div>
    </section>`;
}

function renderSite(profile: BusinessProfile, opts?: RenderOptions) {
  const baseUrl = baseUrlOf(profile, opts);
  const siteName = profile.name;
  const seoTitle = profile.seo.title.trim() || siteName;
  const seoDesc = profile.seo.description.trim() || profile.tagline.trim() || `Official website of ${siteName}.`;

  const about = profile.about.trim()
    ? `<section aria-label="About">\n      <h2 class="section-title">About us</h2>\n      <p>${escapeHtml(profile.about)}</p>\n    </section>`
    : '';

  const indexHtml = buildPage({
    head: { title: seoTitle, description: seoDesc, baseUrl, pagePath: 'index.html', siteName },
    header: header(profile, 'index.html'),
    main: `      <section class="hero" aria-label="Introduction">
        <h2>${escapeHtml(profile.tagline.trim() || siteName)}</h2>
        ${profile.about.trim() ? `<p>${escapeHtml(profile.about.split('\n')[0] ?? '')}</p>` : ''}
        <div class="cta-row">
          <a class="btn" href="services.html">View services</a>
          <a class="btn btn-ghost" href="contact.html">Request a quote</a>
        </div>
      </section>
      <h2 class="section-title">Our services</h2>
      ${serviceCards(profile, 6)}
      <h2 class="section-title">Service area</h2>
      ${serviceArea(profile)}
      ${quoteBand(profile)}`,
    footer: footer(profile),
  });

  const servicesHtml = buildPage({
    head: {
      title: `Services — ${seoTitle}`,
      description: seoDesc,
      baseUrl,
      pagePath: 'services.html',
      siteName,
    },
    header: header(profile, 'services.html'),
    main: `      <h2 class="section-title" style="margin-top:0">Services</h2>
      ${serviceCards(profile)}
      ${about}
      ${quoteBand(profile)}`,
    footer: footer(profile),
  });

  const contactHtml = buildPage({
    head: {
      title: `Contact — ${seoTitle}`,
      description: seoDesc,
      baseUrl,
      pagePath: 'contact.html',
      siteName,
    },
    header: header(profile, 'contact.html'),
    main: `      <h2 class="section-title" style="margin-top:0">Contact</h2>
      <div class="contact-grid">
        <section aria-label="Contact details">
          ${contactBlock(profile)}
        </section>
        ${hoursBlock(profile)}
      </div>
      ${quoteBand(profile)}`,
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
