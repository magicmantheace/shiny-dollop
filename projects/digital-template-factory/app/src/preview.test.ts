import { describe, expect, it } from 'vitest';
import { escapeHtml, renderPreviewHtml, resolveTokens } from './preview';
import { fixtureTokens, invoiceManifest, makeDoc } from './test-utils';

describe('escapeHtml', () => {
  it('escapes markup-significant characters', () => {
    expect(escapeHtml('<script>alert("x")</script>')).toBe(
      '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;',
    );
    expect(escapeHtml("it's & that")).toBe('it&#39;s &amp; that');
  });

  it('stringifies nullish and non-string values safely', () => {
    expect(escapeHtml(null)).toBe('');
    expect(escapeHtml(undefined)).toBe('');
    expect(escapeHtml(42)).toBe('42');
  });
});

describe('resolveTokens', () => {
  it('passes through valid tokens', () => {
    expect(resolveTokens({ bg: '#112233' }, fixtureTokens)).toMatchObject({
      bg: '#112233',
    });
  });

  it('falls back for invalid colours, fonts and spacing', () => {
    const resolved = resolveTokens(
      {
        bg: 'red',
        text: '#zzz',
        accent: 'javascript:alert(1)',
        headingFont: 'Evil Font',
        bodyFont: 'Evil Font',
        spacing: Number.NaN,
      },
      fixtureTokens,
    );
    expect(resolved).toEqual(fixtureTokens);
  });

  it('clamps spacing into the 0..64 range', () => {
    expect(resolveTokens({ spacing: 999 }, fixtureTokens).spacing).toBe(64);
    expect(resolveTokens({ spacing: -5 }, fixtureTokens).spacing).toBe(0);
  });
});

describe('renderPreviewHtml', () => {
  it('renders template name, fields and list rows', () => {
    const html = renderPreviewHtml(invoiceManifest, makeDoc());
    expect(html).toContain('Simple Invoice');
    expect(html).toContain('Acme Corp');
    expect(html).toContain('Widgets');
    expect(html).toContain('<table');
  });

  it('escapes untrusted document data', () => {
    const doc = makeDoc({ data: { clientName: '<img src=x onerror=alert(1)>' } });
    const html = renderPreviewHtml(invoiceManifest, doc);
    expect(html).not.toContain('<img src=x');
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;');
  });

  it('marks empty fields as not set instead of crashing', () => {
    const html = renderPreviewHtml(invoiceManifest, makeDoc({ data: {} }));
    expect(html).toContain('not set');
  });

  it('labels itself as an approximate preview', () => {
    const html = renderPreviewHtml(invoiceManifest, makeDoc());
    expect(html).toContain('approximate');
  });

  it('applies sanitized tokens to the stylesheet', () => {
    const doc = makeDoc({ tokens: { ...fixtureTokens, bg: '#123456', spacing: 24 } });
    const html = renderPreviewHtml(invoiceManifest, doc);
    expect(html).toContain('background: #123456');
    expect(html).toContain('padding: 48px');
  });
});
