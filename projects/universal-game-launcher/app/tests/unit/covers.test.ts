/** Unit tests for the cover-art store: validation, import, eviction, data URLs. */
import { afterEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  COVER_MAX_SOURCE_BYTES,
  coverDataUrl,
  deleteCoverFile,
  enforceDirCap,
  importCoverFile,
  isValidCoverFilename,
} from '../../electron/main/files/cover-store';

// Minimal 1x1 PNG (valid image bytes for the stub scaler).
const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);

const GOOD_NAME = '12345678-1234-1234-1234-123456789abc.png';

let tmp: string | null = null;
afterEach(() => {
  if (tmp) {
    fs.rmSync(tmp, { recursive: true, force: true });
    tmp = null;
  }
});

function makeTmp(): string {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ugl-covers-'));
  return tmp;
}

const identityScale = (input: Buffer): Buffer => input;

describe('isValidCoverFilename', () => {
  it('accepts uuid filenames this module writes', () => {
    expect(isValidCoverFilename(GOOD_NAME)).toBe(true);
    expect(isValidCoverFilename('12345678-1234-1234-1234-123456789abc.jpg')).toBe(true);
    expect(isValidCoverFilename('12345678-1234-1234-1234-123456789abc.webp')).toBe(true);
  });

  it('rejects traversal, executables and junk', () => {
    expect(isValidCoverFilename('../evil.png')).toBe(false);
    expect(isValidCoverFilename('..\\evil.png')).toBe(false);
    expect(isValidCoverFilename('game.exe')).toBe(false);
    expect(isValidCoverFilename('')).toBe(false);
    expect(isValidCoverFilename('not-a-uuid.png')).toBe(false);
    expect(isValidCoverFilename('/abs/path.png')).toBe(false);
  });
});

describe('importCoverFile', () => {
  it('imports a valid image and returns a uuid filename', () => {
    const dir = makeTmp();
    const src = path.join(dir, 'src.png');
    fs.writeFileSync(src, PNG_1X1);
    const name = importCoverFile(src, path.join(dir, 'covers'), identityScale);
    expect(isValidCoverFilename(name)).toBe(true);
    expect(name.endsWith('.png')).toBe(true);
    expect(fs.existsSync(path.join(dir, 'covers', name))).toBe(true);
  });

  it('rejects non-image extensions', () => {
    const dir = makeTmp();
    const src = path.join(dir, 'evil.exe');
    fs.writeFileSync(src, PNG_1X1);
    expect(() => importCoverFile(src, path.join(dir, 'covers'), identityScale)).toThrow(/Unsupported image type/);
  });

  it('rejects files the scaler cannot decode', () => {
    const dir = makeTmp();
    const src = path.join(dir, 'fake.png');
    fs.writeFileSync(src, Buffer.from('not an image'));
    const badScale = () => {
      throw new Error('nope');
    };
    expect(() => importCoverFile(src, path.join(dir, 'covers'), badScale)).toThrow(/could not be decoded/);
  });

  it('rejects missing files', () => {
    const dir = makeTmp();
    expect(() =>
      importCoverFile(path.join(dir, 'nope.png'), path.join(dir, 'covers'), identityScale),
    ).toThrow(/not found/);
  });

  it('rejects oversized sources without reading them fully', () => {
    const dir = makeTmp();
    const src = path.join(dir, 'big.png');
    const fh = fs.openSync(src, 'w');
    fs.ftruncateSync(fh, COVER_MAX_SOURCE_BYTES + 1); // sparse — fast
    fs.closeSync(fh);
    expect(() => importCoverFile(src, path.join(dir, 'covers'), identityScale)).toThrow(/exceeds/);
  });
});

describe('coverDataUrl', () => {
  it('returns a data URL for a stored cover', () => {
    const dir = makeTmp();
    const covers = path.join(dir, 'covers');
    fs.mkdirSync(covers, { recursive: true });
    fs.writeFileSync(path.join(covers, GOOD_NAME), PNG_1X1);
    const url = coverDataUrl(covers, GOOD_NAME);
    expect(url).toMatch(/^data:image\/png;base64,/);
  });

  it('returns null for invalid filenames and missing files', () => {
    const dir = makeTmp();
    expect(coverDataUrl(dir, '../evil.png')).toBeNull();
    expect(coverDataUrl(dir, GOOD_NAME)).toBeNull();
  });
});

describe('enforceDirCap', () => {
  it('evicts oldest-first until under the cap', () => {
    const dir = makeTmp();
    const covers = path.join(dir, 'covers');
    fs.mkdirSync(covers, { recursive: true });
    const names = [
      '11111111-1111-1111-1111-111111111111.png',
      '22222222-2222-2222-2222-222222222222.png',
      '33333333-3333-3333-3333-333333333333.png',
    ];
    const now = Date.now();
    names.forEach((n, i) => {
      const p = path.join(covers, n);
      fs.writeFileSync(p, Buffer.alloc(100, i));
      const t = new Date(now - (names.length - i) * 1000);
      fs.utimesSync(p, t, t);
    });
    const evicted = enforceDirCap(covers, 250); // 300 bytes total → evict 1
    expect(evicted).toBe(1);
    expect(fs.existsSync(path.join(covers, names[0]!))).toBe(false); // oldest gone
    expect(fs.existsSync(path.join(covers, names[2]!))).toBe(true); // newest kept
  });

  it('evicts nothing when under the cap', () => {
    const dir = makeTmp();
    expect(enforceDirCap(dir, 1024)).toBe(0);
    expect(enforceDirCap('/nonexistent-dir-xyz', 1024)).toBe(0);
  });
});

describe('deleteCoverFile', () => {
  it('deletes and ignores missing files and bad names', () => {
    const dir = makeTmp();
    const covers = path.join(dir, 'covers');
    fs.mkdirSync(covers, { recursive: true });
    fs.writeFileSync(path.join(covers, GOOD_NAME), PNG_1X1);
    deleteCoverFile(covers, GOOD_NAME);
    expect(fs.existsSync(path.join(covers, GOOD_NAME))).toBe(false);
    expect(() => deleteCoverFile(covers, GOOD_NAME)).not.toThrow();
    expect(() => deleteCoverFile(covers, '../evil.png')).not.toThrow();
  });
});
