/**
 * Theme rendering tests: determinism, file contract, SEO, semantics,
 * no-external-assets, and internal link integrity.
 */
import { describe, expect, it } from 'vitest';
import { getTheme, listThemes } from '../../electron/main/themes/index.js';
import { DEFAULT_BASE_URL } from '../../electron/main/themes/common.js';
import { isInternalHref, resolveHref } from '../../electron/main/validate.js';
import { makeProfile } from './fixtures.js';

const THEME_IDS = ['trades', 'author', 'restaurant', 'localbiz'] as const;

describe('theme registry', () => {
  it('lists exactly the four original themes', () => {
    const infos = listThemes();
    expect(infos.map((i) => i.id).sort()).toEqual([...THEME_IDS].sort());
    for (const info of infos) {
      expect(info.name.length).toBeGreaterThan(0);
      expect(info.description.length).toBeGreaterThan(0);
      expect(info.businessTypes.length).toBe(1);
      expect(info.businessTypes[0]).toBe(info.id);
      expect(info.pages).toContain('index.html');
      expect(info.pages).toContain('contact.html');
      expect(info.pages).toContain('style.css');
      expect(info.pages).toContain('sitemap.xml');
      expect(info.pages).toContain('robots.txt');
    }
  });

  it('uses the business-type-specific detail page per theme', () => {
    expect(getTheme('trades')!.info.pages).toContain('services.html');
    expect(getTheme('localbiz')!.info.pages).toContain('services.html');
    expect(getTheme('restaurant')!.info.pages).toContain('menu.html');
    expect(getTheme('author')!.info.pages).toContain('books.html');
  });
});

describe.each(THEME_IDS)('theme %s', (themeId) => {
  it('renders byte-identical output for the same profile (deterministic)', () => {
    const theme = getTheme(themeId)!;
    const profile = makeProfile();
    const a = theme.renderSite(profile, { baseUrl: 'https://shop.example' });
    const b = theme.renderSite(profile, { baseUrl: 'https://shop.example' });
    expect(a.files).toEqual(b.files);
    expect(Object.keys(a.files).sort()).toEqual([...theme.info.pages].sort());
  });

  it('renders different content for different profiles', () => {
    const theme = getTheme(themeId)!;
    const a = theme.renderSite(makeProfile()).files['index.html'];
    const b = theme.renderSite(makeProfile({ name: 'Totally Different Name LLC' })).files['index.html'];
    expect(a).not.toBe(b);
  });

  it('emits SEO tags on every page', () => {
    const theme = getTheme(themeId)!;
    const profile = makeProfile();
    const { files } = theme.renderSite(profile, { baseUrl: 'https://shop.example' });
    for (const page of theme.info.pages.filter((p) => p.endsWith('.html'))) {
      const html = files[page];
      expect(html).toContain('<title>');
      expect(html).toMatch(/<meta name="description" content="[^"]+"/);
      expect(html).toContain('<meta property="og:title"');
      expect(html).toContain('<meta property="og:description"');
      expect(html).toContain('<meta property="og:type" content="website"');
      expect(html).toContain('<meta property="og:url" content="https://shop.example/' + page + '"');
    }
  });

  it('uses semantic landmarks, a skip link and labelled nav', () => {
    const theme = getTheme(themeId)!;
    const { files } = theme.renderSite(makeProfile());
    for (const page of theme.info.pages.filter((p) => p.endsWith('.html'))) {
      const html = files[page];
      expect(html).toContain('<header');
      expect(html).toContain('<nav aria-label="Primary">');
      expect(html).toContain('<main id="main">');
      expect(html).toContain('<footer');
      expect(html).toContain('<a class="skip-link" href="#main">Skip to main content</a>');
      expect(html).toContain('aria-current="page"');
    }
  });

  it('loads no external assets and no scripts', () => {
    const theme = getTheme(themeId)!;
    const { files } = theme.renderSite(makeProfile());
    for (const page of theme.info.pages.filter((p) => p.endsWith('.html'))) {
      const html = files[page];
      expect(html).not.toContain('<script');
      expect(html).not.toContain('<img');
      expect(html).not.toMatch(/<(link|source|video|audio)[^>]*\s(src|href)="https?:/);
      expect(html).not.toContain('src="http');
    }
    const css = files['style.css'];
    expect(css).not.toContain('@import');
    expect(css).not.toMatch(/url\(\s*["']?https?:/);
  });

  it('has no broken internal links', () => {
    const theme = getTheme(themeId)!;
    const { files } = theme.renderSite(makeProfile());
    const hrefRe = /href\s*=\s*"([^"]*)"/gi;
    for (const page of theme.info.pages.filter((p) => p.endsWith('.html'))) {
      const html = files[page];
      let m: RegExpExecArray | null;
      while ((m = hrefRe.exec(html)) !== null) {
        const href = m[1];
        if (!isInternalHref(href)) continue;
        if (/\.(png|jpe?g|gif|webp|svg|ico|avif)$/i.test(href)) continue;
        expect(files, `broken link ${href} on ${page}`).toHaveProperty(resolveHref(page, href));
      }
    }
  });

  it('emits sitemap.xml (no lastmod) and robots.txt', () => {
    const theme = getTheme(themeId)!;
    const { files } = theme.renderSite(makeProfile(), { baseUrl: 'https://shop.example' });
    const sitemap = files['sitemap.xml'];
    expect(sitemap).toContain('<urlset');
    for (const page of theme.info.pages.filter((p) => p.endsWith('.html'))) {
      expect(sitemap).toContain(`<loc>https://shop.example/${page}</loc>`);
    }
    expect(sitemap).not.toContain('lastmod');
    expect(files['robots.txt']).toContain('Sitemap: https://shop.example/sitemap.xml');
  });

  it('falls back to a placeholder base URL when the profile has no website', () => {
    const theme = getTheme(themeId)!;
    const { files } = theme.renderSite(makeProfile({ contact: { phone: '', email: '', address: '', website: '' } }));
    expect(files['sitemap.xml']).toContain(DEFAULT_BASE_URL);
  });

  it('escapes the business name in the title', () => {
    const theme = getTheme(themeId)!;
    const { files } = theme.renderSite(makeProfile({ name: 'A & B <Co>' }));
    expect(files['index.html']).toContain('A &amp; B &lt;Co&gt;');
  });
});

describe('restaurant theme', () => {
  it('renders menu sections with prices', () => {
    const { files } = getTheme('restaurant')!.renderSite(makeProfile());
    expect(files['menu.html']).toContain('Starters');
    expect(files['menu.html']).toContain('Test Soup');
    expect(files['menu.html']).toContain('$9.99');
  });
});

describe('author theme', () => {
  it('renders the bookshelf from services and a placeholder newsletter form', () => {
    const { files } = getTheme('author')!.renderSite(makeProfile());
    expect(files['books.html']).toContain('Service One');
    expect(files['index.html']).toContain('<form');
    expect(files['index.html']).toContain('does not send anywhere');
    expect(files['index.html']).not.toContain('mailto:');
  });
});

describe('trades theme', () => {
  it('renders a services grid, service area and quote CTA', () => {
    const { files } = getTheme('trades')!.renderSite(makeProfile());
    expect(files['services.html']).toContain('Service One');
    expect(files['index.html']).toContain('Where we work');
    expect(files['index.html']).toContain('Get a free quote');
  });
});
