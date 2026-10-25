/**
 * Simple invoice template — original design authored for this project.
 * No copied designs, no trademarked assets.
 */
import type { TemplateManifest } from '../../../shared/types';

function deepFreeze<T>(obj: T): T {
  if (obj !== null && typeof obj === 'object' && !Object.isFrozen(obj)) {
    for (const value of Object.values(obj as Record<string, unknown>)) {
      deepFreeze(value);
    }
    Object.freeze(obj);
  }
  return obj;
}

export const invoiceManifest: TemplateManifest = deepFreeze({
  manifestVersion: '1.0.0',
  templateId: 'invoice-1.0.0',
  name: 'Simple Invoice',
  description:
    'A clean one-page invoice with line items, tax calculation and notes.',
  version: '1.0.0',
  fields: [
    { key: 'businessName', label: 'Business name', type: 'text', required: true },
    { key: 'clientName', label: 'Client name', type: 'text', required: true },
    { key: 'invoiceNumber', label: 'Invoice number', type: 'text', required: true },
    { key: 'issueDate', label: 'Issue date', type: 'date', required: true },
    {
      key: 'lineItems',
      label: 'Line items',
      type: 'list',
      required: true,
      minItems: 1,
      itemSchema: [
        { key: 'desc', label: 'Description', type: 'text', required: true },
        { key: 'qty', label: 'Quantity', type: 'number', required: true, min: 0 },
        { key: 'price', label: 'Unit price', type: 'number', required: true, min: 0 },
      ],
      prefill: [{ desc: '', qty: 1, price: 0 }],
    },
    {
      key: 'taxRate',
      label: 'Tax rate (%)',
      type: 'number',
      required: false,
      min: 0,
      max: 100,
      default: 0,
    },
    { key: 'notes', label: 'Notes', type: 'text', required: false },
  ],
  defaultTokens: {
    bg: '#ffffff',
    text: '#1a1a1a',
    accent: '#1d4ed8',
    headingFont: 'Georgia, serif',
    bodyFont: 'Arial, Helvetica, sans-serif',
    spacing: 16,
  },
} as TemplateManifest);
