/**
 * Template bundle import validation tests. Synthetic bundles only.
 */
import { describe, expect, it } from 'vitest';
import { parseTemplateBundle } from '../electron/main/template-import';
import { DtfError } from '../electron/main/validation';

function validBundle(overrides: Record<string, unknown> = {}): string {
  return JSON.stringify({
    manifestVersion: '1.0.0',
    templateId: 'external-card-1.0.0',
    name: 'External Card',
    description: 'An imported card template.',
    version: '1.0.0',
    fields: [
      { key: 'heading', label: 'Heading', type: 'text', required: true },
      { key: 'count', label: 'Count', type: 'number', required: false, min: 0 },
    ],
    defaultTokens: {
      bg: '#ffffff',
      text: '#111111',
      accent: '#0f766e',
      headingFont: 'Georgia, serif',
      bodyFont: 'Arial, sans-serif',
      spacing: 12,
    },
    ...overrides,
  });
}

function expectImportError(fn: () => void, code: string): void {
  try {
    fn();
  } catch (err) {
    expect(err).toBeInstanceOf(DtfError);
    expect((err as DtfError).code).toBe(code);
    return;
  }
  throw new Error(`Expected DtfError(${code}) but nothing was thrown`);
}

describe('parseTemplateBundle', () => {
  it('accepts a well-formed bundle', () => {
    const manifest = parseTemplateBundle(validBundle());
    expect(manifest.templateId).toBe('external-card-1.0.0');
    expect(manifest.fields).toHaveLength(2);
  });

  it('accepts the "tokens" shorthand for defaultTokens', () => {
    const raw = JSON.parse(validBundle());
    raw.tokens = raw.defaultTokens;
    delete raw.defaultTokens;
    const manifest = parseTemplateBundle(JSON.stringify(raw));
    expect(manifest.defaultTokens.bg).toBe('#ffffff');
  });

  it('rejects an unknown manifestVersion with TEMPLATE_VERSION_UNSUPPORTED', () => {
    expectImportError(
      () => parseTemplateBundle(validBundle({ manifestVersion: '2.0.0' })),
      'TEMPLATE_VERSION_UNSUPPORTED',
    );
  });

  it('rejects a missing manifestVersion with TEMPLATE_INVALID', () => {
    const raw = JSON.parse(validBundle());
    delete raw.manifestVersion;
    expectImportError(
      () => parseTemplateBundle(JSON.stringify(raw)),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects missing fields[] with TEMPLATE_INVALID', () => {
    const raw = JSON.parse(validBundle());
    delete raw.fields;
    expectImportError(
      () => parseTemplateBundle(JSON.stringify(raw)),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects non-JSON input', () => {
    expectImportError(() => parseTemplateBundle('not json {'), 'TEMPLATE_INVALID');
  });

  it('rejects a field with an unknown type', () => {
    const raw = JSON.parse(validBundle());
    raw.fields[0].type = 'video';
    expectImportError(
      () => parseTemplateBundle(JSON.stringify(raw)),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects duplicate field keys', () => {
    const raw = JSON.parse(validBundle());
    raw.fields.push({ key: 'heading', label: 'H2', type: 'text', required: false });
    expectImportError(
      () => parseTemplateBundle(JSON.stringify(raw)),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects invalid token colors', () => {
    const raw = JSON.parse(validBundle());
    raw.defaultTokens.bg = 'white';
    expectImportError(
      () => parseTemplateBundle(JSON.stringify(raw)),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects missing templateId', () => {
    const raw = JSON.parse(validBundle());
    delete raw.templateId;
    expectImportError(
      () => parseTemplateBundle(JSON.stringify(raw)),
      'TEMPLATE_INVALID',
    );
  });
});

describe('parseTemplateBundle nested list itemSchema validation', () => {
  const validItemSchema = [
    { key: 'desc', label: 'Description', type: 'text', required: true },
    { key: 'qty', label: 'Quantity', type: 'number', required: true, min: 0 },
    { key: 'price', label: 'Unit price', type: 'number', required: true, min: 0 },
  ];

  function listBundle(field: Record<string, unknown>): string {
    return validBundle({
      fields: [
        { key: 'heading', label: 'Heading', type: 'text', required: true },
        {
          key: 'lineItems',
          label: 'Line items',
          type: 'list',
          required: true,
          minItems: 1,
          ...field,
        },
      ],
    });
  }

  it('accepts a well-formed list field with itemSchema and prefill', () => {
    const manifest = parseTemplateBundle(
      listBundle({
        itemSchema: validItemSchema,
        prefill: [{ desc: 'Widget', qty: 1, price: 10 }],
      }),
    );
    expect(manifest.fields).toHaveLength(2);
  });

  it('rejects itemSchema [null] with prefill [{}] (crashes ListEditor/preview)', () => {
    expectImportError(
      () => parseTemplateBundle(listBundle({ itemSchema: [null], prefill: [{}] })),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects a nested schema entry that is not an object', () => {
    expectImportError(
      () => parseTemplateBundle(listBundle({ itemSchema: ['desc'] })),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects a nested schema entry with an unsupported type', () => {
    expectImportError(
      () =>
        parseTemplateBundle(
          listBundle({
            itemSchema: [
              { key: 'clip', label: 'Clip', type: 'video', required: false },
            ],
          }),
        ),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects a nested schema entry missing its label', () => {
    expectImportError(
      () =>
        parseTemplateBundle(
          listBundle({
            itemSchema: [{ key: 'desc', type: 'text', required: true }],
          }),
        ),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects a nested schema entry missing boolean "required"', () => {
    expectImportError(
      () =>
        parseTemplateBundle(
          listBundle({
            itemSchema: [{ key: 'desc', label: 'Description', type: 'text' }],
          }),
        ),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects a nested schema entry missing its key', () => {
    expectImportError(
      () =>
        parseTemplateBundle(
          listBundle({
            itemSchema: [{ label: 'Description', type: 'text', required: true }],
          }),
        ),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects duplicate nested schema keys', () => {
    expectImportError(
      () =>
        parseTemplateBundle(
          listBundle({
            itemSchema: [
              { key: 'desc', label: 'Description', type: 'text', required: true },
              { key: 'desc', label: 'Again', type: 'text', required: false },
            ],
          }),
        ),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects a nested schema entry with a non-number min', () => {
    expectImportError(
      () =>
        parseTemplateBundle(
          listBundle({
            itemSchema: [
              { key: 'qty', label: 'Qty', type: 'number', required: true, min: '0' },
            ],
          }),
        ),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects prefill rows missing required nested fields', () => {
    expectImportError(
      () =>
        parseTemplateBundle(
          listBundle({ itemSchema: validItemSchema, prefill: [{}] }),
        ),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects prefill rows with values violating nested bounds', () => {
    expectImportError(
      () =>
        parseTemplateBundle(
          listBundle({
            itemSchema: validItemSchema,
            prefill: [{ desc: 'Widget', qty: -1, price: 10 }],
          }),
        ),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects a prefill row that is not an object', () => {
    expectImportError(
      () =>
        parseTemplateBundle(
          listBundle({ itemSchema: validItemSchema, prefill: [null] }),
        ),
      'TEMPLATE_INVALID',
    );
  });

  it('rejects prefill that is not an array', () => {
    expectImportError(
      () =>
        parseTemplateBundle(
          listBundle({ itemSchema: validItemSchema, prefill: 'nope' }),
        ),
      'TEMPLATE_INVALID',
    );
  });
});
