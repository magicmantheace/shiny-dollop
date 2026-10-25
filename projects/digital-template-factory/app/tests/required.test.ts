/**
 * Required-field validator tests, including nested list walking.
 */
import { describe, expect, it } from 'vitest';
import { validateRequiredFields } from '../electron/main/validators/required';
import { getBundledManifest } from '../electron/main/templates';
import type { TemplateManifest } from '../shared/types';

const invoice = getBundledManifest('invoice-1.0.0') as TemplateManifest;
const checklist = getBundledManifest('checklist-1.0.0') as TemplateManifest;

function validInvoiceData(): Record<string, unknown> {
  return {
    businessName: 'Acme Widgets',
    clientName: 'Globex',
    invoiceNumber: 'INV-001',
    issueDate: '2026-10-23',
    lineItems: [{ desc: 'Widget', qty: 2, price: 25 }],
    taxRate: 5,
    notes: '',
  };
}

describe('validateRequiredFields', () => {
  it('passes on fully-filled invoice data', () => {
    expect(validateRequiredFields(invoice, validInvoiceData())).toEqual([]);
  });

  it('reports missing top-level required fields', () => {
    const missing = validateRequiredFields(invoice, {
      ...validInvoiceData(),
      businessName: '',
      clientName: '   ',
    });
    expect(missing).toContain('businessName');
    expect(missing).toContain('clientName');
    expect(missing).not.toContain('notes'); // optional
  });

  it('reports an empty required list', () => {
    const missing = validateRequiredFields(invoice, {
      ...validInvoiceData(),
      lineItems: [],
    });
    expect(missing).toEqual(['lineItems']);
  });

  it('walks nested line items with dotted paths', () => {
    const missing = validateRequiredFields(invoice, {
      ...validInvoiceData(),
      lineItems: [
        { desc: 'Widget', qty: 2, price: 25 },
        { desc: '', qty: 1, price: 10 },
      ],
    });
    expect(missing).toEqual(['lineItems[1].desc']);
  });

  it('treats taxRate default 0 as present (not required anyway)', () => {
    const data = validInvoiceData();
    delete data.taxRate;
    expect(validateRequiredFields(invoice, data)).toEqual([]);
  });

  it('reports missing checklist items', () => {
    expect(
      validateRequiredFields(checklist, { title: 'Groceries', items: [] }),
    ).toEqual(['items']);
    expect(
      validateRequiredFields(checklist, {
        title: '',
        items: [{ label: 'Milk', done: false }],
      }),
    ).toEqual(['title']);
  });
});
