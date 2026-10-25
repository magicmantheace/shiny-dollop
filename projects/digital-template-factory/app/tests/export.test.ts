/**
 * Export pipeline tests: determinism, named-error blocking, license record.
 * Synthetic fixtures only.
 */
import { describe, expect, it } from 'vitest';
import { generateExport, sha256Hex } from '../electron/main/export';
import { getBundledManifest } from '../electron/main/templates';
import { validateStructure } from '../electron/main/validators/structure';
import type { DocumentRecord, TemplateManifest } from '../shared/types';

const invoice = getBundledManifest('invoice-1.0.0') as TemplateManifest;

function validInvoiceDoc(overrides: Partial<DocumentRecord> = {}): DocumentRecord {
  return {
    id: 'doc-1',
    templateId: 'invoice-1.0.0',
    data: {
      businessName: 'Acme Widgets',
      clientName: 'Globex Corp',
      invoiceNumber: 'INV-2026-001',
      issueDate: '2026-10-23',
      lineItems: [
        { desc: 'Widget A', qty: 2, price: 25 },
        { desc: 'Widget B', qty: 1, price: 40.5 },
      ],
      taxRate: 5,
      notes: 'Net 30.',
    },
    tokens: { ...invoice.defaultTokens },
    version: 1,
    updatedAt: '2026-10-23T00:00:00.000Z',
    ...overrides,
  };
}

describe('generateExport', () => {
  it('is byte-identical across two runs with identical inputs', () => {
    const input = { document: validInvoiceDoc(), manifest: invoice, format: 'html' as const };
    const first = generateExport(input);
    const second = generateExport(input);
    expect(first.ok).toBe(true);
    expect(second.ok).toBe(true);
    expect(first.html).toBe(second.html);
    expect(first.licenseRecord?.contentHash).toBe(second.licenseRecord?.contentHash);
    expect(first.licenseRecord?.contentHash).toBe(sha256Hex(first.html as string));
  });

  it('computes invoice totals deterministically', () => {
    const result = generateExport({
      document: validInvoiceDoc(),
      manifest: invoice,
      format: 'html',
    });
    expect(result.ok).toBe(true);
    // subtotal 90.50, tax 5% = 4.525 -> 4.53, total 95.025 -> 95.03
    expect(result.html).toContain('90.50');
    expect(result.html).toContain('4.53');
    expect(result.html).toContain('95.03');
  });

  it('blocks export when required fields are missing, with named errors', () => {
    const doc = validInvoiceDoc({
      data: { ...validInvoiceDoc().data, businessName: '', lineItems: [] },
    });
    const result = generateExport({ document: doc, manifest: invoice, format: 'html' });
    expect(result.ok).toBe(false);
    expect(result.html).toBeUndefined();
    expect(result.errors).toContain('FIELD_REQUIRED:businessName');
    expect(result.errors).toContain('FIELD_REQUIRED:lineItems');
  });

  it('blocks export on contrast failure with CONTRAST_FAIL errors', () => {
    const doc = validInvoiceDoc({
      tokens: { ...invoice.defaultTokens, text: '#f0f0f0' },
    });
    const result = generateExport({ document: doc, manifest: invoice, format: 'html' });
    expect(result.ok).toBe(false);
    expect(result.errors).toContain('CONTRAST_FAIL:text');
  });

  it('emits a license record with hash and metadata on success', () => {
    const result = generateExport({
      document: validInvoiceDoc(),
      manifest: invoice,
      format: 'print',
    });
    expect(result.ok).toBe(true);
    const license = result.licenseRecord;
    expect(license?.templateId).toBe('invoice-1.0.0');
    expect(license?.templateVersion).toBe('1.0.0');
    expect(license?.manifestVersion).toBe('1.0.0');
    expect(license?.format).toBe('print');
    expect(license?.contentHash).toMatch(/^[0-9a-f]{64}$/);
    expect(typeof license?.exportedAt).toBe('string');
    // exportedAt stays out of the HTML: the HTML has no timestamps.
    expect(result.html).not.toContain(license?.exportedAt as string);
  });

  it('generated HTML passes the structure validator', () => {
    const result = generateExport({
      document: validInvoiceDoc(),
      manifest: invoice,
      format: 'html',
    });
    expect(result.ok).toBe(true);
    expect(validateStructure(result.html as string)).toEqual({ ok: true });
  });
});
