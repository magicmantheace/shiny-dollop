/**
 * Hermetic window.inv mock for UI tests. Every method is a vi.fn with a
 * harmless default; individual tests override what they need.
 */
import { vi } from 'vitest';

export function makeInvMock() {
  return {
    items: {
      list: vi.fn(async () => []),
      get: vi.fn(async () => null),
      create: vi.fn(async (input: unknown) => ({ id: 'item-1', ...(input as object) })),
      update: vi.fn(async (_id: string, input: unknown) => ({ id: _id, ...(input as object) })),
      remove: vi.fn(async () => ({ deletedAttachments: 0 })),
    },
    categories: {
      list: vi.fn(async () => [] as string[]),
    },
    attachments: {
      add: vi.fn(async (_itemId: string, input: unknown) => ({ id: 'att-1', ...(input as object) })),
      get: vi.fn(async () => null),
      remove: vi.fn(async () => undefined),
    },
    maintenance: {
      list: vi.fn(async () => []),
      add: vi.fn(async (_itemId: string, input: unknown) => ({ id: 'm-1', ...(input as object) })),
      remove: vi.fn(async () => undefined),
    },
    warranties: {
      expiring: vi.fn(async () => []),
    },
    backup: {
      export: vi.fn(async () => ({ filePath: '/tmp/backup.inv', itemCount: 0, attachmentCount: 0 })),
      import: vi.fn(async () => ({ filePath: '/tmp/backup.inv', itemCount: 0, attachmentCount: 0 })),
    },
  };
}

export type InvMock = ReturnType<typeof makeInvMock>;

/** Installs the mock as window.inv and returns it. */
export function installInvMock(): InvMock {
  const mock = makeInvMock();
  (window as unknown as { inv: unknown }).inv = mock;
  return mock;
}

export function itemFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: 'item-1',
    name: 'Washing Machine',
    category: 'Appliances',
    location: 'Laundry Room',
    purchasePriceCents: 89900,
    purchaseDate: '2024-03-15',
    serialNumber: 'WM-12345',
    notes: '',
    warrantyStart: '2024-03-15',
    warrantyEnd: '2026-03-15',
    createdAt: '2024-03-15T00:00:00Z',
    updatedAt: '2024-03-15T00:00:00Z',
    ...overrides,
  };
}
