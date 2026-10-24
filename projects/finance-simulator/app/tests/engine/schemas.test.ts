/**
 * IPC contract tests: zod schemas must accept the valid shapes the preload
 * sends and reject malformed payloads before they reach the DB or engine.
 */
import { describe, expect, it } from 'vitest';
import {
  debtUpsertSchema,
  emptySchema,
  incomeUpsertSchema,
  reportSaveSchema,
  simulateRunSchema,
} from '../../shared/schemas';

describe('debtUpsertSchema', () => {
  it('accepts a create payload without id', () => {
    const parsed = debtUpsertSchema.parse({
      name: 'Card',
      balanceCents: 500000,
      aprPercent: 19.99,
      minPaymentCents: 12500,
    });
    expect(parsed.id).toBeUndefined();
  });

  it('rejects APR above 100 and negative cents', () => {
    expect(() =>
      debtUpsertSchema.parse({
        name: 'Card',
        balanceCents: 500000,
        aprPercent: 100.01,
        minPaymentCents: 12500,
      }),
    ).toThrow();
    expect(() =>
      debtUpsertSchema.parse({
        name: 'Card',
        balanceCents: -5,
        aprPercent: 19.99,
        minPaymentCents: 12500,
      }),
    ).toThrow();
  });

  it('rejects empty and over-long names', () => {
    expect(() =>
      debtUpsertSchema.parse({
        name: '',
        balanceCents: 1,
        aprPercent: 1,
        minPaymentCents: 1,
      }),
    ).toThrow();
    expect(() =>
      debtUpsertSchema.parse({
        name: 'x'.repeat(101),
        balanceCents: 1,
        aprPercent: 1,
        minPaymentCents: 1,
      }),
    ).toThrow();
  });
});

describe('incomeUpsertSchema', () => {
  it('accepts every documented frequency and rejects unknown ones', () => {
    for (const frequency of ['monthly', 'biweekly', 'weekly', 'once'] as const) {
      expect(() =>
        incomeUpsertSchema.parse({ name: 'Pay', amountCents: 100, frequency }),
      ).not.toThrow();
    }
    expect(() =>
      incomeUpsertSchema.parse({ name: 'Pay', amountCents: 100, frequency: 'yearly' }),
    ).toThrow();
  });
});

describe('simulateRunSchema and reportSaveSchema', () => {
  it('rejects negative extra payments', () => {
    expect(() => simulateRunSchema.parse({ extraPaymentCents: -1 })).toThrow();
    expect(() => reportSaveSchema.parse({
      format: 'csv',
      extraPaymentCents: -1,
      defaultName: 'report',
    })).toThrow();
  });

  it('rejects unknown report formats', () => {
    expect(() =>
      reportSaveSchema.parse({ format: 'xml', extraPaymentCents: 0, defaultName: 'r' }),
    ).toThrow();
  });

  it('accepts empty payload objects', () => {
    expect(() => emptySchema.parse({})).not.toThrow();
  });
});
