import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  deleteAttachmentFile,
  readAttachmentFile,
  sanitizeFileName,
  saveAttachmentFile,
  sha256Hex,
} from '../../db/attachmentFiles';
import { MAX_ATTACHMENT_BYTES } from '../../shared/schemas';

let dir: string;

beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hi-att-'));
});

afterEach(() => {
  fs.rmSync(dir, { recursive: true, force: true });
});

const PNG_BYTES = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2, 3, 4]);

describe('sanitizeFileName', () => {
  it('strips directories and unsafe characters', () => {
    expect(sanitizeFileName('../../evil.png')).toBe('evil.png');
    // Backslash is not a separator on POSIX, so it becomes a safe '_' instead.
    // Either way the result must carry no traversal and stay usable.
    const winStyle = sanitizeFileName('..\\evil.png');
    expect(winStyle).not.toContain('/');
    expect(winStyle).not.toContain('\\');
    expect(winStyle.startsWith('.')).toBe(false);
    expect(winStyle.length).toBeGreaterThan(0);
    expect(sanitizeFileName('my receipt (1).png')).toBe('my_receipt__1_.png');
    expect(sanitizeFileName('ok-file_name.2.webp')).toBe('ok-file_name.2.webp');
  });

  it('throws when nothing usable remains', () => {
    expect(() => sanitizeFileName('...')).toThrow();
    expect(() => sanitizeFileName('')).toThrow();
  });
});

describe('saveAttachmentFile', () => {
  it('round-trips bytes with a matching sha256 and a uuid stored name', () => {
    const saved = saveAttachmentFile(dir, {
      fileName: 'receipt.png',
      mime: 'image/png',
      bytes: PNG_BYTES,
      kind: 'receipt',
    });
    expect(saved.originalName).toBe('receipt.png');
    expect(saved.storedName).toMatch(/^[0-9a-f-]{36}\.png$/);
    expect(saved.sizeBytes).toBe(PNG_BYTES.byteLength);
    expect(saved.sha256).toBe(sha256Hex(PNG_BYTES));

    const back = readAttachmentFile(dir, saved.storedName);
    expect(back).not.toBeNull();
    expect(Buffer.from(back as Buffer).equals(PNG_BYTES)).toBe(true);
  });

  it('rejects oversized files', () => {
    const tooBig = Buffer.alloc(MAX_ATTACHMENT_BYTES + 1, 0);
    expect(() =>
      saveAttachmentFile(dir, {
        fileName: 'big.png',
        mime: 'image/png',
        bytes: tooBig,
        kind: 'photo',
      }),
    ).toThrow(/exceeds/i);
  });

  it('rejects disallowed mimes', () => {
    expect(() =>
      saveAttachmentFile(dir, {
        fileName: 'archive.zip',
        mime: 'application/zip',
        bytes: PNG_BYTES,
        kind: 'other',
      }),
    ).toThrow(/not allowed/i);
  });

  it('rejects empty files', () => {
    expect(() =>
      saveAttachmentFile(dir, {
        fileName: 'empty.png',
        mime: 'image/png',
        bytes: Buffer.alloc(0),
        kind: 'photo',
      }),
    ).toThrow(/empty/i);
  });
});

describe('missing-file tolerance', () => {
  it('readAttachmentFile returns null and deleteAttachmentFile does not throw', () => {
    expect(readAttachmentFile(dir, 'does-not-exist.png')).toBeNull();
    expect(() => deleteAttachmentFile(dir, 'does-not-exist.png')).not.toThrow();
  });

  it('deletes an existing file', () => {
    const saved = saveAttachmentFile(dir, {
      fileName: 'x.pdf',
      mime: 'application/pdf',
      bytes: PNG_BYTES,
      kind: 'manual',
    });
    deleteAttachmentFile(dir, saved.storedName);
    expect(readAttachmentFile(dir, saved.storedName)).toBeNull();
  });
});
