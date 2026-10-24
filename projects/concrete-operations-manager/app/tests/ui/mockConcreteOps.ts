/**
 * Mock of the preload-exposed window.concreteOps API for UI tests.
 * Every method returns the uniform IpcResult envelope with synthetic data.
 */
import { vi } from 'vitest';
import type { ConcreteOpsApi } from '../../shared/api-types';
import type { Customer, Invoice, Job } from '../../shared/types';

function ok<T>(data: T) {
  return { ok: true as const, data };
}

export const SYNTHETIC_CUSTOMER: Customer = {
  id: 1,
  name: 'Synthetic Test Customer',
  contactName: 'Test Contact',
  phone: '555-0100',
  email: 'test@example.com',
  address: '1234 Test Road',
  taxExempt: false,
  concreteRateCentsPerM3: null,
  smallLoadChargeCents: null,
  deliveryFeeMode: null,
  deliveryFlatCents: null,
  deliveryPerKmCents: null,
  notes: null,
  createdAt: '2026-10-23T10:00:00.000Z',
  updatedAt: '2026-10-23T10:00:00.000Z',
};

export const SYNTHETIC_JOB: Job = {
  id: 1,
  customerId: 1,
  jobDate: '2026-10-23',
  deliveryLocation: '1234 Test Road, Lethbridge AB',
  poNumber: 'PO-TEST-001',
  distanceTenthsKm: 185,
  status: 'scheduled',
  notes: null,
  createdAt: '2026-10-23T10:00:00.000Z',
};

export const SYNTHETIC_INVOICE: Invoice = {
  id: 1,
  quoteId: 1,
  invoiceNumber: 'INV-000001',
  status: 'issued',
  lines: [
    { kind: 'concrete', label: 'Concrete — mix C25/30 (nominal design ID)', detail: '2.480 m³ @ $180.00/m³', quantityLiters: 2480, rateCentsPerM3: 18000, amountCents: 44640 },
    { kind: 'small_load', label: 'Small-load charge', detail: 'under 3.000 m³ threshold (2.480 m³ ordered)', amountCents: 15000 },
    { kind: 'delivery', label: 'Delivery fee (flat)', amountCents: 7500 },
  ],
  subtotalCents: 67140,
  taxLines: [{ name: 'GST', rateBps: 500, taxableCents: 67140, taxCents: 3357 }],
  totalCents: 70497,
  taxExemptApplied: false,
  createdAt: '2026-10-23T12:00:00.000Z',
  paidAt: null,
  voidedAt: null,
};

export function installMockConcreteOps(overrides: Partial<ConcreteOpsApi> = {}): void {
  const base: ConcreteOpsApi = {
    customers: {
      list: vi.fn().mockResolvedValue(ok([SYNTHETIC_CUSTOMER])),
      get: vi.fn().mockResolvedValue(ok(SYNTHETIC_CUSTOMER)),
      add: vi.fn().mockResolvedValue(ok(SYNTHETIC_CUSTOMER)),
      update: vi.fn().mockResolvedValue(ok(SYNTHETIC_CUSTOMER)),
      remove: vi.fn().mockResolvedValue(ok({ removed: true })),
    },
    jobs: {
      list: vi.fn().mockResolvedValue(ok([SYNTHETIC_JOB])),
      get: vi.fn().mockResolvedValue(ok(SYNTHETIC_JOB)),
      add: vi.fn().mockResolvedValue(ok(SYNTHETIC_JOB)),
      update: vi.fn().mockResolvedValue(ok(SYNTHETIC_JOB)),
      remove: vi.fn().mockResolvedValue(ok({ removed: true })),
    },
    pours: {
      listByJob: vi.fn().mockResolvedValue(ok([])),
      add: vi.fn(),
      update: vi.fn(),
      setDelivered: vi.fn(),
      remove: vi.fn().mockResolvedValue(ok({ removed: true })),
    },
    quotes: {
      listByJob: vi.fn().mockResolvedValue(ok([])),
      get: vi.fn(),
      create: vi.fn(),
      updateDraft: vi.fn(),
      issue: vi.fn(),
      revise: vi.fn(),
      deleteDraft: vi.fn().mockResolvedValue(ok({ removed: true })),
    },
    invoices: {
      list: vi.fn().mockResolvedValue(ok([SYNTHETIC_INVOICE])),
      get: vi.fn().mockResolvedValue(ok(SYNTHETIC_INVOICE)),
      create: vi.fn().mockResolvedValue(ok(SYNTHETIC_INVOICE)),
      markPaid: vi.fn(),
      void: vi.fn(),
    },
    settings: {
      get: vi.fn().mockResolvedValue(ok({})),
      set: vi.fn().mockResolvedValue(ok({})),
    },
    taxRates: {
      list: vi.fn().mockResolvedValue(ok([])),
      add: vi.fn(),
      update: vi.fn(),
      remove: vi.fn().mockResolvedValue(ok({ removed: true })),
    },
    inventory: {
      materials: vi.fn().mockResolvedValue(ok([])),
      materialAdd: vi.fn(),
      receipts: vi.fn().mockResolvedValue(ok([])),
      receiptAdd: vi.fn(),
      consumption: vi.fn().mockResolvedValue(ok([])),
      consumptionAdd: vi.fn(),
      stock: vi.fn().mockResolvedValue(ok([])),
    },
    audit: {
      list: vi.fn().mockResolvedValue(ok([])),
    },
    exports: {
      csv: vi.fn().mockResolvedValue(ok({ written: [] })),
      invoicePdf: vi.fn().mockResolvedValue(ok({ written: null })),
    },
    backup: {
      create: vi.fn().mockResolvedValue(ok({ written: null })),
      restore: vi.fn().mockResolvedValue(ok({ restored: false, rollbackPath: null })),
    },
    calibration: {
      list: vi.fn().mockResolvedValue(ok([])),
      export: vi.fn().mockResolvedValue(ok({ written: null })),
      import: vi.fn().mockResolvedValue(ok({ imported: null })),
      remove: vi.fn().mockResolvedValue(ok({ removed: true })),
    },
  };
  (window as unknown as { concreteOps: ConcreteOpsApi }).concreteOps = {
    ...base,
    ...overrides,
  } as ConcreteOpsApi;
}
