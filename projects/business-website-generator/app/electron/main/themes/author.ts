/**
 * "Folio" — original theme for authors.
 *
 * Quiet editorial design: a books/works shelf rendered from the services
 * list, an about section, and a newsletter signup form. The form is a
 * static-export placeholder — it posts nowhere and says so plainly (no
 * mailto links). All CSS written from scratch.
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
  id: 'author',
  name: 'Folio',
  description: 'Quiet editorial theme for authors: a bookshelf of works, an about page and a newsletter signup placeholder.',
  businessTypes: ['author'],
  pages: ['index.html', 'books.html', 'contact.html', 'style.css', 'sitemap.xml', 'robots.txt'],
};

export const tokens: ContrastToken[] = [
  { name: 'ink-on-paper', fg: '#26221c', bg: '#fdfcf8' },
  { name: 'accent-on-paper', fg: '#1f5c4d', bg: '#fdfcf8' },
  { name: 'muted-on-paper', fg: '#57503f', bg: '#fdfcf8' },
  { name: 'paper-on-ink', fg: '#fdfcf8', bg: '#26221c' },
  { name: 'white-on-accent', fg: '#ffffff', bg: '#1f5c4d' },
];

const CSS = `:root {
  --paper: #fdfcf8;
  --ink: #26221c;
  --accent: #1f5c4d;
  --accent-dark: #17463b;
  --muted: #57503f;
  --line: #e7e1d3;
  --card: #ffffff;
  --radius: 0.35rem;
  --max: 62rem;
  --serif: Georgia, "Times New Roman", Times, serif;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  font-family: var(--serif);
  background: var(--paper);
  color: var(--ink);
  line-height: 1.7;
  font-size: 1.05rem;
}
.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  background: var(--ink);
  color: var(--paper);
  padding: 0.75rem 1rem;
  z-index: 100;
  font-family: var(--sans);
}
.skip-link:focus { left: 0; }
.site-header { border-bottom: 1px solid var(--line); }
.site-header .wrap {
  max-width: var(--max);
  margin: 0 auto;
  padding: 2rem 1.25rem 1.25rem;
  text-align: center;
}
.brand { margin: 0; font-size: 2.1rem; letter-spacing: 0.04em; }
.brand a { color: var(--ink); text-decoration: none; }
.tagline { margin: 0.35rem 0 0; font-style: italic; color: var(--muted); }
.site-header nav ul {
  list-style: none;
  margin: 1.25rem 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.25rem 1.75rem;
  font-family: var(--sans);
  font-size: 0.95rem;
}
.site-header nav a { color: var(--ink); text-decoration: none; text-transform: uppercase; letter-spacing: 0.08em; }
.site-header nav a:hover { color: var(--accent); }
.site-header nav a[aria-current="page"] { color: var(--accent); font-weight: 700; }
main { max-width: var(--max); margin: 0 auto; padding: 2rem 1.25rem 3.5rem; }
.lede { font-size: 1.25rem; max-width: 42rem; margin: 0 auto 2.5rem; text-align: center; color: var(--muted); }
.bookshelf { display: grid; gap: 1.5rem; grid-template-columns: 1fr; }
@media (min-width: 44rem) { .bookshelf { grid-template-columns: repeat(2, 1fr); } }
.book {
  background: var(--card);
  border: 1px solid var(--line);
  border-top: 0.3rem solid var(--accent);
  border-radius: var(--radius);
  padding: 1.5rem;
}
.book h3 { margin: 0 0 0.6rem; font-size: 1.35rem; line-height: 1.3; }
.book p { margin: 0; color: var(--muted); font-size: 0.98rem; }
.rule { border: 0; border-top: 1px solid var(--line); margin: 2.5rem 0; }
h2.section { font-size: 1.4rem; letter-spacing: 0.03em; margin: 2.5rem 0 1rem; font-family: var(--sans); text-transform: uppercase; font-size: 1rem; color: var(--accent); }
.about p { max-width: 44rem; }
.newsletter {
  background: var(--ink);
  color: var(--paper);
  border-radius: var(--radius);
  padding: 2rem 1.75rem;
  margin-top: 3rem;
  font-family: var(--sans);
  font-size: 0.95rem;
}
.newsletter h2 { margin: 0 0 0.5rem; font-size: 1.3rem; }
.newsletter p { margin: 0.5rem 0; color: #d9d2c0; }
.newsletter form { display: flex; flex-wrap: wrap; gap: 0.6rem; margin-top: 1rem; }
.newsletter label { position: absolute; left: -9999px; }
.newsletter input[type="email"] {
  flex: 1 1 14rem;
  padding: 0.65rem 0.9rem;
  border: 1px solid #6b6353;
  border-radius: var(--radius);
  font-size: 1rem;
  background: var(--paper);
  color: var(--ink);
}
.newsletter button {
  padding: 0.65rem 1.3rem;
  background: var(--accent);
  color: #ffffff;
  border: 0;
  border-radius: var(--radius);
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
}
.newsletter button:hover { background: var(--accent-dark); }
.newsletter .note { font-size: 0.85rem; color: #b9b09a; }
.hours { list-style: none; padding: 0; margin: 0.5rem 0 0; }
.hours li { padding: 0.35rem 0; border-bottom: 1px dotted var(--line); }
.label { font-weight: 700; }
.site-footer { border-top: 1px solid var(--line); margin-top: 2rem; font-family: var(--sans); font-size: 0.9rem; }
.site-footer .wrap { max-width: var(--max); margin: 0 auto; padding: 1.75rem 1.25rem; text-align: center; }
.site-footer .site-name { margin: 0 0 0.5rem; font-weight: 700; }
.site-footer .social { list-style: none; margin: 0 0 0.75rem; padding: 0; display: flex; flex-wrap: wrap; justify-content: center; gap: 0.25rem 1rem; }
.site-footer a { color: var(--accent); }
.site-footer .fine { margin: 0.75rem 0 0; color: var(--muted); font-size: 0.82rem; }
`;

function header(profile: BusinessProfile, active: string): string {
  return `<header class="site-header">
      <div class="wrap">
        <p class="brand"><a href="index.html">${escapeHtml(profile.name)}</a></p>
        ${profile.tagline.trim() ? `<p class="tagline">${escapeHtml(profile.tagline)}</p>` : ''}
        ${navList(
          [
            { href: 'index.html', label: 'Home' },
            { href: 'books.html', label: 'Books' },
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

function bookList(profile: BusinessProfile): string {
  if (!profile.services.length) return '<p>No works listed yet.</p>';
  return `<div class="bookshelf">\n${profile.services
    .map(
      (s) => `      <article class="book">
        <h3>${escapeHtml(s.title)}</h3>
        <p>${escapeHtml(s.description)}</p>
      </article>`,
    )
    .join('\n')}\n    </div>`;
}

function newsletter(): string {
  return `<section class="newsletter" aria-label="Newsletter signup">
      <h2>Newsletter</h2>
      <p>New releases, readings and behind-the-scenes notes — straight to your inbox.</p>
      <form action="#newsletter" method="get" aria-describedby="newsletter-note">
        <label for="newsletter-email">Email address</label>
        <input type="email" id="newsletter-email" name="email" placeholder="you@example.com" autocomplete="email" />
        <button type="submit">Subscribe</button>
      </form>
      <p class="note" id="newsletter-note">This is a static website export: the signup form is a placeholder and does not send anywhere. Connect your newsletter provider to activate it.</p>
    </section>`;
}

function renderSite(profile: BusinessProfile, opts?: RenderOptions) {
  const baseUrl = baseUrlOf(profile, opts);
  const siteName = profile.name;
  const seoTitle = profile.seo.title.trim() || siteName;
  const seoDesc = profile.seo.description.trim() || profile.tagline.trim() || `Official website of ${siteName}.`;

  const about = profile.about.trim()
    ? `<section class="about" aria-label="About">\n      <h2 class="section">About</h2>\n      <p>${escapeHtml(profile.about)}</p>\n    </section>`
    : '';

  const indexHtml = buildPage({
    head: { title: seoTitle, description: seoDesc, baseUrl, pagePath: 'index.html', siteName },
    header: header(profile, 'index.html'),
    main: `      <p class="lede">${escapeHtml(profile.tagline.trim() || `Welcome to the official website of ${siteName}.`)}</p>
      <h2 class="section">Latest works</h2>
      ${bookList(profile)}
      <hr class="rule" />
      ${about}
      ${newsletter()}`,
    footer: footer(profile),
  });

  const booksHtml = buildPage({
    head: { title: `Books — ${seoTitle}`, description: seoDesc, baseUrl, pagePath: 'books.html', siteName },
    header: header(profile, 'books.html'),
    main: `      <h2 class="section" style="margin-top:0">Books &amp; works</h2>
      ${bookList(profile)}
      ${newsletter()}`,
    footer: footer(profile),
  });

  const contactHtml = buildPage({
    head: { title: `Contact — ${seoTitle}`, description: seoDesc, baseUrl, pagePath: 'contact.html', siteName },
    header: header(profile, 'contact.html'),
    main: `      <h2 class="section" style="margin-top:0">Contact</h2>
      ${contactBlock(profile)}
      <hr class="rule" />
      ${hoursBlock(profile)}`,
    footer: footer(profile),
  });

  const pages = ['index.html', 'books.html', 'contact.html'];
  return {
    files: {
      'index.html': indexHtml,
      'books.html': booksHtml,
      'contact.html': contactHtml,
      'style.css': CSS,
      'sitemap.xml': sitemapXml(baseUrl, pages),
      'robots.txt': robotsTxt(baseUrl),
    },
  };
}

export const theme: ThemeModule = { info, tokens, renderSite };
export default theme;
