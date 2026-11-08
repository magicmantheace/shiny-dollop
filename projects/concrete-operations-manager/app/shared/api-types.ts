/**
 * Typed renderer-facing API, shared between preload and the React app.
 * Every method returns the uniform IpcResult envelope.
 */
import type {
  AuditEntry,
  CalibrationProfile,
  Customer,
  InventoryConsumption,
  InventoryMaterial,
  InventoryReceipt,
  Invoice,
  IpcResult,
  Job,
  Pour,
  Quote,
  StockEntry,
  TaxRate,
} from './types';
import type {
  CustomerAddInput,
  CustomerUpdateInput,
  JobAddInput,
  JobUpdateInput,
  PourAddInput,
} from './schemas';

export interface IdInput {
  id: number;
}

export interface JobIdInput {
  jobId: number;
}

export interface PourUpdateInput {
  id: number;
  mixDesignId?: string;
  quotedLiters?: number;
}

export interface PourDeliveredInput {
  id: number;
  deliveredLiters: number;
}

export interface QuoteDraftUpdateInput {
  id: number;
  notes?: string | null;
  rateOverrideCentsPerM3?: number | null;
  smallLoadChargeOverrideCents?: number | null;
}

export interface TaxRateAddInput {
  name: string;
  rateBps: number;
  enabled?: boolean;
}

export interface TaxRateUpdateInput {
  id: number;
  name?: string;
  rateBps?: number;
  enabled?: boolean;
}

export interface ReceiptAddInput {
  materialId: number;
  supplier: string;
  receivedDate: string;
  qtyKg: number;
  costCents: number;
  notes?: string | null;
}

export interface ConsumptionAddInput {
  pourId: number;
  materialId: number;
  qtyKg: number;
}

export interface ConcreteOpsApi {
  customers: {
    list: () => Promise<IpcResult<Customer[]>>;
    get: (input: IdInput) => Promise<IpcResult<Customer>>;
    add: (input: CustomerAddInput) => Promise<IpcResult<Customer>>;
    update: (input: CustomerUpdateInput) => Promise<IpcResult<Customer>>;
    remove: (input: IdInput) => Promise<IpcResult<{ removed: boolean }>>;
  };
  jobs: {
    list: (input?: { customerId?: number }) => Promise<IpcResult<Job[]>>;
    get: (input: IdInput) => Promise<IpcResult<Job>>;
    add: (input: JobAddInput) => Promise<IpcResult<Job>>;
    update: (input: JobUpdateInput) => Promise<IpcResult<Job>>;
    remove: (input: IdInput) => Promise<IpcResult<{ removed: boolean }>>;
  };
  pours: {
    listByJob: (input: JobIdInput) => Promise<IpcResult<Pour[]>>;
    add: (input: PourAddInput) => Promise<IpcResult<Pour>>;
    update: (input: PourUpdateInput) => Promise<IpcResult<Pour>>;
    setDelivered: (input: PourDeliveredInput) => Promise<IpcResult<Pour>>;
    remove: (input: IdInput) => Promise<IpcResult<{ removed: boolean }>>;
  };
  quotes: {
    listByJob: (input: JobIdInput) => Promise<IpcResult<Quote[]>>;
    get: (input: IdInput) => Promise<IpcResult<Quote>>;
    create: (input: { jobId: number; notes?: string | null }) => Promise<IpcResult<Quote>>;
    updateDraft: (input: QuoteDraftUpdateInput) => Promise<IpcResult<Quote>>;
    issue: (input: IdInput) => Promise<IpcResult<Quote>>;
    revise: (input: IdInput) => Promise<IpcResult<Quote>>;
    deleteDraft: (input: IdInput) => Promise<IpcResult<{ removed: boolean }>>;
  };
  invoices: {
    list: () => Promise<IpcResult<Invoice[]>>;
    get: (input: IdInput) => Promise<IpcResult<Invoice>>;
    create: (input: { quoteId: number }) => Promise<IpcResult<Invoice>>;
    markPaid: (input: IdInput) => Promise<IpcResult<Invoice>>;
    void: (input: IdInput) => Promise<IpcResult<Invoice>>;
  };
  settings: {
    get: () => Promise<IpcResult<Record<string, string>>>;
    set: (input: { key: string; value: string }) => Promise<IpcResult<Record<string, string>>>;
  };
  taxRates: {
    list: () => Promise<IpcResult<TaxRate[]>>;
    add: (input: TaxRateAddInput) => Promise<IpcResult<TaxRate>>;
    update: (input: TaxRateUpdateInput) => Promise<IpcResult<TaxRate>>;
    remove: (input: IdInput) => Promise<IpcResult<{ removed: boolean }>>;
  };
  inventory: {
    materials: () => Promise<IpcResult<InventoryMaterial[]>>;
    materialAdd: (input: { name: string; unit?: string }) => Promise<IpcResult<InventoryMaterial>>;
    receipts: (input?: { materialId?: number }) => Promise<IpcResult<InventoryReceipt[]>>;
    receiptAdd: (input: ReceiptAddInput) => Promise<IpcResult<InventoryReceipt>>;
    consumption: (input?: { pourId?: number }) => Promise<IpcResult<InventoryConsumption[]>>;
    consumptionAdd: (input: ConsumptionAddInput) => Promise<IpcResult<InventoryConsumption>>;
    stock: () => Promise<IpcResult<StockEntry[]>>;
  };
  audit: {
    list: (input?: { entityType?: string; entityId?: number; limit?: number }) => Promise<IpcResult<AuditEntry[]>>;
  };
  exports: {
    csv: () => Promise<IpcResult<{ written: string[] }>>;
    invoicePdf: (input: IdInput) => Promise<IpcResult<{ written: string | null }>>;
  };
  backup: {
    create: () => Promise<IpcResult<{ written: string | null }>>;
    restore: () => Promise<IpcResult<{ restored: boolean; rollbackPath: string | null }>>;
  };
  calibration: {
    list: () => Promise<IpcResult<{ id: number; name: string; formatVersion: string; importedAt: string }[]>>;
    export: (input: IdInput) => Promise<IpcResult<{ written: string | null }>>;
    import: () => Promise<IpcResult<{ imported: { id: number; name: string; formatVersion: string } | null }>>;
    remove: (input: IdInput) => Promise<IpcResult<{ removed: boolean }>>;
  };
}

export type { CalibrationProfile };
