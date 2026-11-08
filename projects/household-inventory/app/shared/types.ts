/**
 * Shared domain types for Household Inventory and Warranty Tracker.
 *
 * Conventions:
 * - Dates are calendar dates as `YYYY-MM-DD` strings (no timezones).
 * - Money is integer cents (never floats).
 * - IDs are UUID v4 strings generated in the main process.
 * - Timestamps are ISO-8601 strings in UTC.
 */

export type DateString = string; // YYYY-MM-DD

export type AttachmentKind = 'receipt' | 'photo' | 'manual' | 'other';

export interface Item {
  id: string;
  name: string;
  category: string;
  location: string;
  purchasePriceCents: number | null;
  purchaseDate: DateString | null;
  serialNumber: string | null;
  notes: string;
  warrantyStart: DateString | null;
  warrantyEnd: DateString | null;
  createdAt: string;
  updatedAt: string;
}

export interface Attachment {
  id: string;
  itemId: string;
  originalName: string;
  storedName: string; // uuid + extension, inside the app-owned attachments dir
  mime: string;
  sizeBytes: number;
  sha256: string;
  kind: AttachmentKind;
  createdAt: string;
}

export interface MaintenanceEvent {
  id: string;
  itemId: string;
  eventDate: DateString;
  description: string;
  costCents: number | null;
  createdAt: string;
}

export interface ItemDetail {
  item: Item;
  attachments: Attachment[];
  maintenance: MaintenanceEvent[];
}

export type WarrantyState = 'none' | 'active' | 'expiring' | 'expired';

export interface WarrantyExpiry {
  item: Item;
  /** Whole days from today until warrantyEnd. Negative = already expired. */
  daysLeft: number;
  status: Extract<WarrantyState, 'expired' | 'expiring' | 'active'>;
}

export interface ItemFilter {
  search?: string;
  category?: string;
  location?: string;
}

export interface BackupSummary {
  filePath: string;
  itemCount: number;
  attachmentCount: number;
}

/** Standard IPC envelope: every handler returns this shape. */
export interface IpcError {
  code: string;
  message: string;
}

export type IpcResult<T> = { ok: true; data: T } | { ok: false; error: IpcError };
