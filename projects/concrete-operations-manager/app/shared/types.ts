/**
 * Domain types shared by main, preload and renderer.
 *
 * Money convention: integer cents everywhere (e.g. 18000 = $180.00).
 * Volume convention: integer liters (1 m³ = 1000 L). The UI displays m³.
 * Distance convention: integer tenths of a kilometre (10 = 1.0 km).
 * Timestamps are ISO-8601 UTC strings.
 */

/** A concrete-delivery customer with their own pricing defaults. */
export interface Customer {
  id: number;
  name: string;
  contactName: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  /** When true, no tax is charged (tax lines are shown with $0 and "exempt"). */
  taxExempt: boolean;
  /** Null = fall back to the configured default rate. */
  concreteRateCentsPerM3: number | null;
  /** Null = fall back to the configured default small-load charge. */
  smallLoadChargeCents: number | null;
  /** Null = fall back to the configured default delivery mode. */
  deliveryFeeMode: 'flat' | 'mileage' | null;
  deliveryFlatCents: number | null;
  deliveryPerKmCents: number | null;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
}

export type JobStatus = 'scheduled' | 'in_progress' | 'completed' | 'cancelled';

export interface Job {
  id: number;
  customerId: number;
  /** YYYY-MM-DD (local calendar date of the delivery). */
  jobDate: string;
  deliveryLocation: string;
  poNumber: string | null;
  /** One-way distance, tenths of km; null = unknown. */
  distanceTenthsKm: number | null;
  status: JobStatus;
  notes: string | null;
  createdAt: string;
}

/**
 * One volumetric pour on a job.
 *
 * mixDesignId is a NOMINAL design identifier only (e.g. "C25/30") — it is
 * never a verified structural performance claim. quotedLiters is the
 * estimate given to the customer; deliveredLiters is the calibrated/measured
 * volume recorded after the pour. The two are deliberately separate fields.
 */
export interface Pour {
  id: number;
  jobId: number;
  mixDesignId: string;
  quotedLiters: number;
  /** Measured volume; null until the pour is finalized. */
  deliveredLiters: number | null;
  createdAt: string;
}

export type QuoteStatus = 'draft' | 'issued' | 'superseded';

export type LineItemKind = 'concrete' | 'small_load' | 'delivery' | 'adjustment';

export interface LineItem {
  kind: LineItemKind;
  label: string;
  detail?: string;
  /** Concrete lines only. */
  quantityLiters?: number;
  /** Concrete lines only. */
  rateCentsPerM3?: number;
  amountCents: number;
}

export interface TaxLine {
  name: string;
  rateBps: number;
  taxableCents: number;
  taxCents: number;
}

export interface DocumentTotals {
  lines: LineItem[];
  subtotalCents: number;
  taxLines: TaxLine[];
  totalCents: number;
  /** True when the customer is tax-exempt (tax lines present but $0). */
  taxExemptApplied: boolean;
}

/**
 * A price document for a job. Quotes are revisable; once issued they are
 * immutable — a revision creates a NEW quote row with an incremented
 * version and the previous issued row becomes 'superseded'.
 */
export interface Quote {
  id: number;
  jobId: number;
  version: number;
  status: QuoteStatus;
  /** Snapshot of the line items at issue time (JSON). */
  lines: LineItem[];
  subtotalCents: number;
  taxLines: TaxLine[];
  totalCents: number;
  taxExemptApplied: boolean;
  /** Snapshot of the pricing parameters used (JSON) — the audit basis. */
  params: QuoteParamsSnapshot;
  notes: string | null;
  createdAt: string;
  issuedAt: string | null;
}

/** Frozen copy of the inputs a quote was computed from. */
export interface QuoteParamsSnapshot {
  concreteRateCentsPerM3: number;
  smallLoadThresholdLiters: number;
  smallLoadChargeCents: number;
  smallLoadApplied: boolean;
  deliveryMode: 'flat' | 'mileage' | 'none';
  deliveryFlatCents: number;
  deliveryPerKmCents: number;
  distanceTenthsKm: number | null;
  taxes: { name: string; rateBps: number }[];
  taxExempt: boolean;
  /** Per-pour volumes the quote was computed from (quoted = estimate). */
  volumes: { pourId: number; mixDesignId: string; liters: number }[];
  /** True when the quote was computed from delivered (measured) volumes. */
  fromDelivered: boolean;
}

export type InvoiceStatus = 'issued' | 'paid' | 'voided';

/**
 * An issued invoice is IMMUTABLE. It is always computed from finalized
 * delivered volumes — never from estimates.
 */
export interface Invoice {
  id: number;
  quoteId: number;
  invoiceNumber: string;
  status: InvoiceStatus;
  lines: LineItem[];
  subtotalCents: number;
  taxLines: TaxLine[];
  totalCents: number;
  taxExemptApplied: boolean;
  createdAt: string;
  paidAt: string | null;
  voidedAt: string | null;
}

export interface TaxRate {
  id: number;
  name: string;
  /** Basis points: 500 = 5%. */
  rateBps: number;
  enabled: boolean;
}

/** A bulk material tracked in inventory (cement, sand, gravel...). */
export interface InventoryMaterial {
  id: number;
  name: string;
  /** Display unit, e.g. "kg". Quantities are stored in this unit as integers. */
  unit: string;
}

export interface InventoryReceipt {
  id: number;
  materialId: number;
  supplier: string;
  /** YYYY-MM-DD. */
  receivedDate: string;
  qtyKg: number;
  costCents: number;
  notes: string | null;
  createdAt: string;
}

export interface InventoryConsumption {
  id: number;
  pourId: number;
  materialId: number;
  qtyKg: number;
  createdAt: string;
}

export interface StockEntry {
  materialId: number;
  name: string;
  unit: string;
  receivedKg: number;
  consumedKg: number;
  onHandKg: number;
}

/** Audit-trail row: who changed what, when, before → after. */
export interface AuditEntry {
  id: number;
  entityType: string;
  entityId: number;
  action: string;
  actor: string;
  beforeJson: string | null;
  afterJson: string | null;
  createdAt: string;
}

/**
 * A versioned calibration profile exchanged with the Volumetric Mix
 * Calculator (Project 3). The payload is opaque to this app; see
 * docs/CALIBRATION_EXCHANGE.md for the format contract.
 */
export interface CalibrationProfile {
  id: number;
  name: string;
  formatVersion: string;
  payloadJson: string;
  importedAt: string;
}

/** Uniform IPC envelope. */
export type IpcResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string } };
