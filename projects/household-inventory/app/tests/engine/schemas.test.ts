import { describe, expect, it } from 'vitest';
import {
  attachmentInputSchema,
  itemInputSchema,
  maintenanceInputSchema,
} from '../../shared/schemas';

const validItem = {
  name: 'Fridge',
  category: 'Appliances',
  location: 'Kitchen',
  purchasePriceCents: 129900,
  purchaseDate: '2024-02-29',
  serialNumber: 'SN-1',
  notes: 'notes',
  warrantyStart: '2024-02-29',
  warrantyEnd: '2027-02-28',
};

describe('itemInputSchema', () => {
  it('accepts a full valid payload and fills defaults', () => {
    const parsed = itemInputSchema.parse({ name: 'Lamp', category: 'Lighting' });
    expect(parsed.name).toBe('Lamp');
    expect(parsed.location).toBe('');
    expect(parsed.purchasePriceCents).toBeNull();
    expect(parsed.notes).toBe('');
  });

  it('rejects an empty name', () => {
    expect(() => itemInputSchema.parse({ ...validItem, name: '' })).toThrow();
    expect(() => itemInputSchema.parse({ ...validItem, name: '   ' })).toThrow();
  });

  it('rejects warrantyEnd before warrantyStart', () => {
    expect(() =>
      itemInputSchema.parse({
        ...validItem,
        warrantyStart: '2025-01-01',
        warrantyEnd: '2024-12-31',
      }),
    ).toThrow(/warranty end/i);
  });

  it('accepts warrantyEnd equal to warrantyStart', () => {
    const parsed = itemInputSchema.parse({
      ...validItem,
      warrantyStart: '2025-01-01',
      warrantyEnd: '2025-01-01',
    });
    expect(parsed.warrantyEnd).toBe('2025-01-01');
  });

  it('rejects impossible dates', () => {
    expect(() =>
      itemInputSchema.parse({ ...validItem, purchaseDate: '2023-02-29' }),
    ).toThrow();
    expect(() =>
      itemInputSchema.parse({ ...validItem, warrantyEnd: 'not-a-date' }),
    ).toThrow();
  });

  it('rejects negative prices', () => {
    expect(() =>
      itemInputSchema.parse({ ...validItem, purchasePriceCents: -1 }),
    ).toThrow();
  });
});

describe('attachmentInputSchema', () => {
  const valid = {
    fileName: 'receipt.png',
    mime: 'image/png' as const,
    dataBase64: 'aGVsbG8=',
    kind: 'receipt' as const,
  };

  it('accepts allowlisted mimes', () => {
    for (const mime of ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'] as const) {
      expect(attachmentInputSchema.parse({ ...valid, mime }).mime).toBe(mime);
    }
  });

  it('rejects disallowed mimes', () => {
    expect(() => attachmentInputSchema.parse({ ...valid, mime: 'application/zip' })).toThrow();
    expect(() => attachmentInputSchema.parse({ ...valid, mime: 'text/html' })).toThrow();
  });

  it('rejects path-traversal file names', () => {
    expect(() => attachmentInputSchema.parse({ ...valid, fileName: '../evil.png' })).toThrow();
    expect(() =>
      attachmentInputSchema.parse({ ...valid, fileName: '..\\evil.png' }),
    ).toThrow();
    expect(() => attachmentInputSchema.parse({ ...valid, fileName: '/etc/passwd' })).toThrow();
    expect(() => attachmentInputSchema.parse({ ...valid, fileName: '' })).toThrow();
  });
});

describe('maintenanceInputSchema', () => {
  it('rejects empty descriptions and bad dates', () => {
    expect(() =>
      maintenanceInputSchema.parse({ eventDate: '2026-10-01', description: '   ' }),
    ).toThrow();
    expect(() =>
      maintenanceInputSchema.parse({ eventDate: '2023-02-29', description: 'oil change' }),
    ).toThrow();
  });

  it('accepts a valid event', () => {
    const parsed = maintenanceInputSchema.parse({
      eventDate: '2026-10-01',
      description: 'Replaced filter',
      costCents: 1299,
    });
    expect(parsed.costCents).toBe(1299);
  });
});
