import { describe, expect, it } from 'vitest';
import {
  consumptionAddSchema,
  customerAddSchema,
  pourAddSchema,
  pourSetDeliveredSchema,
  receiptAddSchema,
  settingsSetSchema,
} from '../../shared/schemas';

describe('customerAddSchema', () => {
  it('accepts a minimal customer', () => {
    expect(customerAddSchema.parse({ name: 'Acme Paving' }).name).toBe('Acme Paving');
  });
  it('rejects blank names and oversized fields', () => {
    expect(() => customerAddSchema.parse({ name: '   ' })).toThrow();
    expect(() => customerAddSchema.parse({ name: 'x'.repeat(201) })).toThrow();
  });
  it('rejects negative money and absurd rates', () => {
    expect(() => customerAddSchema.parse({ name: 'A', concreteRateCentsPerM3: -1 })).toThrow();
    expect(() => customerAddSchema.parse({ name: 'A', concreteRateCentsPerM3: 1.5 })).toThrow();
  });
  it('trims whitespace and normalizes empty strings to null', () => {
    const c = customerAddSchema.parse({ name: '  Acme  ', phone: '' });
    expect(c.name).toBe('Acme');
    expect(c.phone).toBeNull();
  });
});

describe('pourAddSchema', () => {
  it('accepts a valid pour', () => {
    expect(pourAddSchema.parse({ jobId: 1, mixDesignId: 'C25/30', quotedLiters: 2500 }).quotedLiters).toBe(2500);
  });
  it('rejects zero/negative volumes and oversized mixes', () => {
    expect(() => pourAddSchema.parse({ jobId: 1, mixDesignId: 'C25/30', quotedLiters: 0 })).toThrow();
    expect(() => pourAddSchema.parse({ jobId: 1, mixDesignId: 'C25/30', quotedLiters: -100 })).toThrow();
    expect(() => pourAddSchema.parse({ jobId: 1, mixDesignId: 'C25/30', quotedLiters: 2_000_000 })).toThrow();
    expect(() => pourAddSchema.parse({ jobId: 1, mixDesignId: 'x'.repeat(41), quotedLiters: 100 })).toThrow();
  });
});

describe('pourSetDeliveredSchema', () => {
  it('rejects zero delivered volumes', () => {
    expect(() => pourSetDeliveredSchema.parse({ id: 1, deliveredLiters: 0 })).toThrow();
  });
});

describe('receiptAddSchema', () => {
  it('rejects bad dates and zero quantities', () => {
    expect(() =>
      receiptAddSchema.parse({ materialId: 1, supplier: 'S', receivedDate: '2026-13-40', qtyKg: 100, costCents: 0 }),
    ).toThrow();
    expect(() =>
      receiptAddSchema.parse({ materialId: 1, supplier: 'S', receivedDate: '2026-10-23', qtyKg: 0, costCents: 0 }),
    ).toThrow();
  });
});

describe('consumptionAddSchema', () => {
  it('rejects zero quantities', () => {
    expect(() => consumptionAddSchema.parse({ pourId: 1, materialId: 1, qtyKg: 0 })).toThrow();
  });
});

describe('settingsSetSchema', () => {
  it('rejects unknown setting keys', () => {
    expect(() => settingsSetSchema.parse({ key: 'drop_tables', value: '1' })).toThrow();
  });
  it('rejects oversized values', () => {
    expect(() =>
      settingsSetSchema.parse({ key: 'company_name', value: 'x'.repeat(501) }),
    ).toThrow();
  });
});
