/**
 * MVP acceptance walkthrough: add item + receipt, warranty dates,
 * expiring-warranty finder, maintenance log, backup export -> import
 * into a fresh dir with byte-identical attachments.
 */
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { openDatabase, closeDatabase, getAttachmentsDir } from '../../db/store';
import { createItem, getItemDetail, listItems, addAttachment, addMaintenanceEvent } from '../../db/records';
import { saveAttachmentFile } from '../../db/attachmentFiles';
import { expiringWarranties, todayUtc } from '../../engine/inventory';
import { createBackupArchive, extractBackupArchive, restoreBackupToDir } from '../../engine/backup';

function future(days: number): string {
  const d = new Date(Date.now() + days * 86400000);
  return d.toISOString().slice(0, 10);
}

describe('MVP acceptance walkthrough', () => {
  it('add item + receipt, warranties, maintenance, backup round-trip', () => {
    const dir = mkdtempSync(join(tmpdir(), 'hi-acc-'));
    const dbs: { db: ReturnType<typeof openDatabase> }[] = [];
    try {
      const db = openDatabase(dir);
      dbs.push({ db });
      // 1. Add items with warranty dates.
      const fridge = createItem(db, {
        name: 'Fridge XZ-2000', category: 'Appliance', location: 'Kitchen',
        purchasePriceCents: 129999, purchaseDate: '2024-03-01', serialNumber: 'SN-123',
        notes: '', warrantyStart: '2024-03-01', warrantyEnd: future(20),
      });
      const washer = createItem(db, {
        name: 'Washer W-9', category: 'Appliance', location: 'Laundry',
        purchasePriceCents: null, purchaseDate: null, serialNumber: null,
        notes: '', warrantyStart: null, warrantyEnd: future(-5), // expired
      });
      expect(listItems(db, {}).length).toBe(2);

      // 2. Add a receipt attachment (synthetic bytes).
      const bytes = Buffer.from('FAKE-RECEIPT-BYTES-' + 'x'.repeat(100));
      const saved = saveAttachmentFile(getAttachmentsDir(dir), {
        fileName: 'receipt.pdf', mime: 'application/pdf', bytes, kind: 'receipt',
      });
      const att = addAttachment(db, {
        itemId: fridge.id, originalName: saved.originalName, storedName: saved.storedName,
        mime: 'application/pdf', sizeBytes: saved.sizeBytes, sha256: saved.sha256, kind: 'receipt',
      });
      expect(getItemDetail(db, fridge.id)?.attachments.length).toBe(1);

      // 3. Maintenance event.
      addMaintenanceEvent(db, fridge.id, {
        eventDate: '2025-01-15', description: 'Replaced water filter', costCents: 4999,
      });
      expect(getItemDetail(db, fridge.id)?.maintenance.length).toBe(1);

      // 4. Expiring-warranty finder (90-day window).
      const exp = expiringWarranties(listItems(db, {}), 90, todayUtc());
      expect(exp.map((e) => e.item.name).sort()).toEqual(['Fridge XZ-2000', 'Washer W-9']);
      expect(exp.find((e) => e.item.id === fridge.id)?.status).toBe('expiring');
      expect(exp.find((e) => e.item.id === washer.id)?.status).toBe('expired');

      // 5. Backup export -> import into a fresh dir.
      const { data: zipBytes } = createBackupArchive({ db, attachmentsDir: getAttachmentsDir(dir), appVersion: '0.1.0-test' });
      const extracted = extractBackupArchive(zipBytes);
      expect(extracted.manifest.itemCount).toBe(2);
      expect(extracted.manifest.attachmentCount).toBe(1);
      const fresh = mkdtempSync(join(tmpdir(), 'hi-acc-fresh-'));
      restoreBackupToDir(extracted, fresh);
      closeDatabase(db);
      dbs.pop();
      const db2 = openDatabase(fresh);
      dbs.push({ db: db2 });
      expect(listItems(db2, {}).length).toBe(2);
      const d2 = getItemDetail(db2, fridge.id);
      expect(d2?.item.serialNumber).toBe('SN-123');
      expect(d2?.maintenance[0]?.description).toBe('Replaced water filter');
      const attBytes = readFileSync(join(fresh, 'attachments', att.storedName));
      expect(Buffer.from(attBytes).equals(bytes)).toBe(true);
      closeDatabase(db2);
      dbs.pop();
      rmSync(fresh, { recursive: true, force: true });
    } finally {
      for (const { db } of dbs) {
        try { closeDatabase(db); } catch { /* already closed */ }
      }
      rmSync(dir, { recursive: true, force: true });
    }
  });
});
