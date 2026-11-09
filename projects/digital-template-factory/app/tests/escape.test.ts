/**
 * escapeHtml + render injection tests. Malicious input must be inert.
 */
import { describe, expect, it } from 'vitest';
import { escapeHtml } from '../electron/main/util/escape';
import { renderInvoice } from '../electron/main/templates/invoice-render';
import { renderChecklist } from '../electron/main/templates/checklist-render';
import { getBundledManifest } from '../electron/main/templates';
import type { TemplateManifest } from '../shared/types';

const invoice = getBundledManifest('invoice-1.0.0') as TemplateManifest;

describe('escapeHtml', () => {
  it('escapes the five special characters', () => {
    expect(escapeHtml('&<>"\'')).toBe('&amp;&lt;&gt;&quot;&#39;');
  });

  it('renders an <img onerror> injection inert', () => {
    const evil = '<img src=x onerror=alert(1)>';
    const escaped = escapeHtml(evil);
    expect(escaped).toBe('&lt;img src=x onerror=alert(1)&gt;');
    expect(escaped).not.toContain('<img');
  });

  it('handles non-string inputs', () => {
    expect(escapeHtml(undefined)).toBe('');
    expect(escapeHtml(null)).toBe('');
    expect(escapeHtml(42)).toBe('42');
  });
});

describe('render injection resistance', () => {
  it('invoice render neutralizes markup in every text field', () => {
    const evil = '<img src=x onerror=alert(1)>';
    const html = renderInvoice(
      {
        businessName: evil,
        clientName: evil,
        invoiceNumber: evil,
        issueDate: '2026-10-23',
        lineItems: [{ desc: evil, qty: 1, price: 1 }],
        taxRate: 0,
        notes: evil,
      },
      invoice.defaultTokens,
      'html',
    );
    expect(html).not.toContain('<img src=x');
    expect(html).not.toContain('onerror=alert(1)>');
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;');
  });

  it('checklist render escapes item labels and the title', () => {
    const evil = '"><script>alert(1)</script>';
    const checklist = getBundledManifest('checklist-1.0.0') as TemplateManifest;
    const html = renderChecklist(
      { title: evil, items: [{ label: evil, done: false }], footerNote: '' },
      checklist.defaultTokens,
      'html',
    );
    expect(html).not.toContain('<script>alert(1)');
    expect(html).toContain('&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;');
  });

  it('does not interpolate unescaped values into style attributes', () => {
    const evil = '"; color: red; x="';
    const html = renderInvoice(
      {
        businessName: 'B',
        clientName: 'C',
        invoiceNumber: '1',
        issueDate: '2026-10-23',
        lineItems: [{ desc: 'd', qty: 1, price: 1 }],
        taxRate: 0,
        notes: evil,
      },
      invoice.defaultTokens,
      'html',
    );
    // The payload appears only in escaped text form, never raw.
    expect(html).not.toContain(evil);
    expect(html).toContain(escapeHtml(evil));
  });
});
