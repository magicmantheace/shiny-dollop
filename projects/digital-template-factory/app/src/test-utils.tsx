/**
 * Hermetic test helpers: a fully mocked `window.dtf` plus fixture templates
 * and documents. No test in this file or any `*.test.tsx` may touch the
 * real backend.
 */
import { vi } from 'vitest';
import type {
  DocumentRecord,
  DtfApi,
  TemplateManifest,
  TemplateSummary,
  ThemeTokens,
} from '../shared/types';
import { FONT_STACKS } from './fonts';

export const fixtureTokens: ThemeTokens = {
  bg: '#ffffff',
  text: '#1a1a1a',
  accent: '#0f6cbd',
  headingFont: FONT_STACKS[0]!.value,
  bodyFont: FONT_STACKS[0]!.value,
  spacing: 16,
};

export const invoiceManifest: TemplateManifest = {
  manifestVersion: '1.0.0',
  templateId: 'simple-invoice',
  name: 'Simple Invoice',
  description: 'A one-page invoice with line items.',
  version: '1.0.0',
  fields: [
    { key: 'clientName', label: 'Client name', type: 'text', required: true },
    { key: 'invoiceNumber', label: 'Invoice number', type: 'text', required: true },
    { key: 'amount', label: 'Amount', type: 'number', required: true, min: 0, max: 1000000 },
    { key: 'dueDate', label: 'Due date', type: 'date', required: false },
    {
      key: 'lineItems',
      label: 'Line items',
      type: 'list',
      required: false,
      minItems: 0,
      itemSchema: [
        { key: 'desc', label: 'Description', type: 'text', required: true },
        { key: 'qty', label: 'Qty', type: 'number', required: true, min: 1 },
        { key: 'price', label: 'Price', type: 'number', required: true, min: 0 },
      ],
    },
  ],
  defaultTokens: fixtureTokens,
};

export const templateSummaries: TemplateSummary[] = [
  {
    templateId: 'simple-invoice',
    name: 'Simple Invoice',
    description: 'A one-page invoice with line items.',
    version: '1.0.0',
    fieldCount: 5,
    source: 'bundled',
  },
  {
    templateId: 'weekly-planner',
    name: 'Weekly Planner',
    description: 'Seven-day planning sheet.',
    version: '2.1.0',
    fieldCount: 4,
    source: 'bundled',
  },
  {
    templateId: 'checklist',
    name: 'Checklist',
    description: 'Simple printable checklist.',
    version: '1.2.0',
    fieldCount: 3,
    source: 'imported',
  },
];

export function makeDoc(overrides: Partial<DocumentRecord> = {}): DocumentRecord {
  return {
    id: 'doc-1',
    templateId: 'simple-invoice',
    data: {
      clientName: 'Acme Corp',
      invoiceNumber: 'INV-001',
      amount: 250,
      dueDate: '2026-11-01',
      lineItems: [{ desc: 'Widgets', qty: 2, price: 125 }],
    },
    tokens: { ...fixtureTokens },
    version: 1,
    updatedAt: '2026-10-23T15:00:00.000Z',
    ...overrides,
  };
}

export type MockDtf = {
  [K in keyof DtfApi]: {
    [M in keyof DtfApi[K]]: ReturnType<typeof vi.fn>;
  };
};

type MockDtfOverrides = {
  [K in keyof DtfApi]?: {
    [M in keyof DtfApi[K]]?: ReturnType<typeof vi.fn>;
  };
};

/** Install a fully mocked `window.dtf`; returns the mock for assertions. */
export function mockDtf(overrides: MockDtfOverrides = {}): MockDtf {
  const mock = {
    templates: {
      list: vi.fn().mockResolvedValue(templateSummaries),
      get: vi.fn().mockResolvedValue(invoiceManifest),
      import: vi.fn(),
      ...(overrides.templates ?? {}),
    },
    documents: {
      list: vi.fn().mockResolvedValue([]),
      create: vi.fn(),
      get: vi.fn(),
      updateField: vi.fn().mockImplementation(
        async (input: { id: string; key: string; value: unknown }) =>
          makeDoc({ id: input.id, data: { [input.key]: input.value } }),
      ),
      updateTokens: vi.fn().mockImplementation(
        async (input: { id: string; tokens: Partial<ThemeTokens> }) =>
          makeDoc({ id: input.id, tokens: { ...fixtureTokens, ...input.tokens } }),
      ),
      delete: vi.fn().mockResolvedValue({ deleted: true }),
      ...(overrides.documents ?? {}),
    },
    export: {
      generate: vi.fn(),
      save: vi.fn(),
      ...(overrides.export ?? {}),
    },
  } as MockDtf;
  Object.defineProperty(window, 'dtf', {
    value: mock,
    configurable: true,
    writable: true,
  });
  return mock;
}

export function unmockDtf(): void {
  // @ts-expect-error - removing the test double between tests
  delete window.dtf;
}
