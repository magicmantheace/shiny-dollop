/**
 * Injection-safety tests: hostile markup in every text field must render
 * inert (escaped), never as live HTML, in all four themes.
 *
 * The check is entity-aware: we assert the RAW payload never appears while
 * its ESCAPED form does, and that no live <img>/<script> tags exist.
 */
import { describe, expect, it } from 'vitest';
import { getTheme } from '../../electron/main/themes/index.js';
import { escapeHtml } from '../../shared/escape.js';
import { makeInjectionProfile, INJECTION } from './fixtures.js';

const THEME_IDS = ['trades', 'author', 'restaurant', 'localbiz'] as const;

/** Second payload exercising quotes and a script vector in attribute contexts. */
const QUOTE_PAYLOAD = `'"><script>alert(2)</script>`;

describe.each(THEME_IDS)('injection safety — theme %s', (themeId) => {
  it('renders XSS payloads inert in every HTML page', () => {
    const theme = getTheme(themeId)!;
    const profile = makeInjectionProfile();
    profile.tagline = QUOTE_PAYLOAD;
    profile.about = `About ${QUOTE_PAYLOAD} text`;
    const { files } = theme.renderSite(profile);
    const pages = theme.info.pages.filter((p) => p.endsWith('.html'));
    expect(pages.length).toBeGreaterThan(0);
    for (const page of pages) {
      const html = files[page];
      // Raw payloads never appear on any page…
      expect(html, `${page}: raw img payload`).not.toContain(INJECTION);
      expect(html, `${page}: raw quote payload`).not.toContain(QUOTE_PAYLOAD);
      // …and no live tags are smuggled through.
      expect(html.toLowerCase(), `${page}: live <img`).not.toContain('<img');
      expect(html.toLowerCase(), `${page}: live <script`).not.toContain('<script');
    }
    // …while their escaped forms appear where the fields are rendered.
    const index = files['index.html'] ?? '';
    expect(index, 'index: escaped img payload').toContain(escapeHtml(INJECTION));
    expect(index, 'index: escaped quote payload').toContain(escapeHtml(QUOTE_PAYLOAD));
  });

  it('escapes the payload inside attribute values too', () => {
    const theme = getTheme(themeId)!;
    const { files } = theme.renderSite(makeInjectionProfile());
    for (const page of theme.info.pages.filter((p) => p.endsWith('.html'))) {
      const html = files[page];
      // A raw double-quote from the payload must never terminate an attribute.
      expect(html).not.toContain(`"${INJECTION}"`);
    }
  });
});
