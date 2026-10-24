/**
 * Typed renderer API exposed through preload as `window.inv`.
 * Every method maps 1:1 to an InvChannels entry and unwraps the
 * IpcResult envelope (throwing on !ok) — see electron/preload.ts.
 */
import type {
  Attachment,
  AttachmentKind,
  BackupSummary,
  Item,
  ItemDetail,
  ItemFilter,
  MaintenanceEvent,
  WarrantyExpiry,
} from './types';
import type { AttachmentInput, ItemInput, MaintenanceInput } from './schemas';

export interface AttachmentFile {
  name: string;
  mime: string;
  dataBase64: string;
}

export interface InvApi {
  items: {
    list(filter?: ItemFilter): Promise<Item[]>;
    get(id: string): Promise<ItemDetail | null>;
    create(input: ItemInput): Promise<Item>;
    update(id: string, input: ItemInput): Promise<Item>;
    remove(id: string): Promise<{ deletedAttachments: number }>;
  };
  categories: {
    list(): Promise<string[]>;
  };
  attachments: {
    add(itemId: string, input: AttachmentInput): Promise<Attachment>;
    get(id: string): Promise<AttachmentFile | null>;
    remove(id: string): Promise<void>;
  };
  maintenance: {
    list(itemId: string): Promise<MaintenanceEvent[]>;
    add(itemId: string, input: MaintenanceInput): Promise<MaintenanceEvent>;
    remove(id: string): Promise<void>;
  };
  warranties: {
    expiring(withinDays?: number): Promise<WarrantyExpiry[]>;
  };
  backup: {
    export(): Promise<BackupSummary>;
    import(): Promise<BackupSummary>;
  };
}

export type { AttachmentKind };

declare global {
  interface Window {
    inv: InvApi;
  }
}
