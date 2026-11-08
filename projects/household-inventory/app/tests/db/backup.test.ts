import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { strToU8, unzipSync, zipSync } from 'fflate';
import { runMigrations } from '../../db/migrations';
import * as records from '../../db/records';
import { saveAttachmentFile } from '../../db/attachmentFiles';
import { DB_FILE_NAME, ATTACHMENTS_DIR_NAME } from '../../db/paths';
import {
  BACKUP_FORMAT,
  BACKUP_FORMAT_VERSION,
  createBackupArchive,
  extractBackupArchive,
  restoreBackupToDir,
} from '../../engine/backup';
import type { ItemDetail } from '../../shared/types';

interface Fixture {
  dir: string;
  db: DatabaseSync;
  attachmentsDir: string;
  details: ItemDetail[];
  attachmentBytes: Map<string, Buffer>; // storedName -> bytes
}

function openTestDb(dir: string): DatabaseSync {
  fs.mkdirSync(dir, { recursive: true });
  const db = new DatabaseSync(path.join(dir, DB_FILE_NAME));
  runMigrations(db);
  return db;
}

/** Build a populated source directory with synthetic fixtures only. */
function buildFixture(): Fixture {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hi-src-'));
  const attachmentsDir = path.join(dir, ATTACHMENTS_DIR_NAME);
  const db = openTestDb(dir);
  const attachmentBytes = new Map<string, Buffer>();

  const seedFiles: { name: string; mime: string; kind: 'receipt' | 'photo' | 'manual'; bytes: Buffer }[] = [
    { name: 'receipt.png', mime: 'image/png', kind: 'receipt', bytes: Buffer.from([1, 2, 3, 4, 5]) },
    { name: 'manual.pdf', mime: 'application/pdf', kind: 'manual', bytes: Buffer.from([9, 8, 7, 6]) },
    { name: 'photo.webp', mime: 'image/webp', kind: 'photo', bytes: Buffer.from([0, 1, 0, 1, 0, 1]) },
  ];

  const itemDefs = [
    {
      name: 'Washer',
      category: 'Appliances',
      location: 'Laundry',
      purchasePriceCents: 89900,
      purchaseDate: '2024-02-29',
      serialNumber: 'W-1',
      notes: 'front load',
      warrantyStart: '2024-02-29',
      warrantyEnd: '2027-02-28',
      files: [0, 1],
      events: [{ eventDate: '2026-01-15', description: 'Cleaned filter', costCents: 0 }],
    },
    {
      name: 'Lamp',
      category: 'Lighting',
      location: 'Office',
      purchasePriceCents: null,
      purchaseDate: null,
      serialNumber: null,
      notes: '',
      warrantyStart: null,
      warrantyEnd: null,
      files: [2],
      events: [],
    },
  ];

  const details: ItemDetail[] = [];
  for (const def of itemDefs) {
    const item = records.createItem(db, {
      name: def.name,
      category: def.category,
      location: def.location,
      purchasePriceCents: def.purchasePriceCents,
      purchaseDate: def.purchaseDate,
      serialNumber: def.serialNumber,
      notes: def.notes,
      warrantyStart: def.warrantyStart,
      warrantyEnd: def.warrantyEnd,
    });
    for (const fi of def.files) {
      const f = seedFiles[fi];
      const saved = saveAttachmentFile(attachmentsDir, {
        fileName: f.name,
        mime: f.mime,
        bytes: f.bytes,
        kind: f.kind,
      });
      attachmentBytes.set(saved.storedName, f.bytes);
      records.addAttachment(db, {
        itemId: item.id,
        originalName: saved.originalName,
        storedName: saved.storedName,
        mime: f.mime,
        sizeBytes: saved.sizeBytes,
        sha256: saved.sha256,
        kind: saved.kind,
      });
    }
    for (const e of def.events) {
      records.addMaintenanceEvent(db, item.id, {
        eventDate: e.eventDate,
        description: e.description,
        costCents: e.costCents,
      });
    }
    const detail = records.getItemDetail(db, item.id);
    if (!detail) throw new Error('fixture detail missing');
    details.push(detail);
  }
  return { dir, db, attachmentsDir, details, attachmentBytes };
}

let fixtures: Fixture[] = [];

beforeEach(() => {
  fixtures = [];
});

afterEach(() => {
  for (const f of fixtures) {
    try {
      f.db.close();
    } catch {
      // ignore
    }
    fs.rmSync(f.dir, { recursive: true, force: true });
  }
  fixtures = [];
});

function track(f: Fixture): Fixture {
  fixtures.push(f);
  return f;
}

function canonicalDetails(db: DatabaseSync): string {
  const items = records.listItems(db);
  const details = items
    .map((i) => records.getItemDetail(db, i.id))
    .filter((d): d is ItemDetail => d !== null)
    .sort((a, b) => a.item.id.localeCompare(b.item.id));
  return JSON.stringify(details);
}

describe('backup export -> import round-trip', () => {
  it('restores identical item rows and byte-identical attachments into a fresh dir', () => {
    const src = track(buildFixture());

    const archive = createBackupArchive({
      db: src.db,
      attachmentsDir: src.attachmentsDir,
      appVersion: '0.1.0-test',
    });
    expect(archive.itemCount).toBe(2);
    expect(archive.attachmentCount).toBe(3);
    expect(archive.manifest.format).toBe(BACKUP_FORMAT);
    expect(archive.manifest.formatVersion).toBe(BACKUP_FORMAT_VERSION);
    expect(archive.manifest.files.some((f) => f.path === DB_FILE_NAME)).toBe(true);
    expect(archive.manifest.files.filter((f) => f.path.startsWith('attachments/'))).toHaveLength(3);

    // Every manifest entry carries a real sha256 + size.
    for (const f of archive.manifest.files) {
      expect(f.sha256).toMatch(/^[0-9a-f]{64}$/);
      expect(f.sizeBytes).toBeGreaterThan(0);
    }

    const extracted = extractBackupArchive(archive.data);
    expect(extracted.manifest.itemCount).toBe(2);

    const destDir = fs.mkdtempSync(path.join(os.tmpdir(), 'hi-dst-'));
    fixtures.push({ dir: destDir, db: null as unknown as DatabaseSync, attachmentsDir: '', details: [], attachmentBytes: new Map() });
    restoreBackupToDir(extracted, destDir);

    const destDb = openTestDb(destDir);
    fixtures[fixtures.length - 1].db = destDb;

    // Identical item/attachment/maintenance rows.
    expect(canonicalDetails(destDb)).toBe(canonicalDetails(src.db));

    // Byte-identical attachment files.
    for (const [storedName, original] of src.attachmentBytes) {
      const restored = fs.readFileSync(path.join(destDir, ATTACHMENTS_DIR_NAME, storedName));
      expect(restored.equals(original)).toBe(true);
    }
    expect(records.countItems(destDb)).toBe(2);
    expect(records.countAttachments(destDb)).toBe(3);
  });
});

describe('backup integrity verification', () => {
  it('rejects a tampered file (sha256 mismatch)', () => {
    const src = track(buildFixture());
    const archive = createBackupArchive({
      db: src.db,
      attachmentsDir: src.attachmentsDir,
      appVersion: '0.1.0-test',
    });
    const entries = unzipSync(archive.data);
    const attKey = Object.keys(entries).find((k) => k.startsWith('attachments/'));
    expect(attKey).toBeTruthy();
    const tampered = Buffer.from(entries[attKey as string]);
    tampered[0] = tampered[0] ^ 0xff;
    entries[attKey as string] = tampered;
    const tamperedZip = zipSync(entries);
    expect(() => extractBackupArchive(tamperedZip)).toThrow(/integrity/i);
  });

  it('rejects a missing listed file', () => {
    const src = track(buildFixture());
    const archive = createBackupArchive({
      db: src.db,
      attachmentsDir: src.attachmentsDir,
      appVersion: '0.1.0-test',
    });
    const entries = unzipSync(archive.data);
    const attKey = Object.keys(entries).find((k) => k.startsWith('attachments/'));
    delete entries[attKey as string];
    expect(() => extractBackupArchive(zipSync(entries))).toThrow(/missing/i);
  });

  it('rejects garbage, non-zip input and wrong manifest formats', () => {
    expect(() => extractBackupArchive(Buffer.from([1, 2, 3, 4]))).toThrow();
    const foreign = zipSync({
      'manifest.json': strToU8(JSON.stringify({ format: 'other-app', formatVersion: 1, files: [] })),
    });
    expect(() => extractBackupArchive(foreign)).toThrow(/unrecognized format/i);
  });

  it('refuses to restore unexpected paths (zip-slip guard)', () => {
    const evil = { path: '../../evil.sh', sha256: 'x', sizeBytes: 1 };
    const manifest = {
      format: BACKUP_FORMAT,
      formatVersion: BACKUP_FORMAT_VERSION,
      exportedAt: new Date().toISOString(),
      appVersion: '0.1.0-test',
      itemCount: 0,
      attachmentCount: 0,
      files: [
        {
          path: DB_FILE_NAME,
          sha256: createHash('sha256').update(Buffer.from('db')).digest('hex'),
          sizeBytes: 2,
        },
        { ...evil, sha256: createHash('sha256').update(Buffer.from('e')).digest('hex') },
      ],
    };
    const zip = zipSync({
      'manifest.json': strToU8(JSON.stringify(manifest)),
      [DB_FILE_NAME]: Buffer.from('db'),
      [evil.path]: Buffer.from('e'),
    });
    const extracted = extractBackupArchive(zip);
    const destDir = fs.mkdtempSync(path.join(os.tmpdir(), 'hi-evil-'));
    fixtures.push({ dir: destDir, db: null as unknown as DatabaseSync, attachmentsDir: '', details: [], attachmentBytes: new Map() });
    expect(() => restoreBackupToDir(extracted, destDir)).toThrow(/refusing/i);
  });
});
