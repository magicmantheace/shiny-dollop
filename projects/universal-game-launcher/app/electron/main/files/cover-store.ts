/**
 * User cover-art storage.
 *
 * Covers live in the per-user app-data `covers/` directory as files named
 * `<uuid>.<ext>` — the filename is the only thing the database stores, and
 * it is strictly validated on every read. No network fetching: covers come
 * only from the user's own file picker.
 *
 * This module has no Electron imports so it is fully unit-testable. Image
 * scaling is injected (the real implementation uses Electron's nativeImage).
 */
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

export class CoverError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = 'CoverError';
    this.code = code;
  }
}

/** Refuse source images larger than this. */
export const COVER_MAX_SOURCE_BYTES = 10 * 1024 * 1024;
/** Evict oldest covers when the directory exceeds this. */
export const COVERS_DIR_MAX_BYTES = 100 * 1024 * 1024;
/** Scale images to fit within this dimension. */
export const COVER_MAX_DIM = 512;

const ALLOWED_EXTS = new Set(['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp']);

const FILENAME_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(png|jpg|jpeg|webp|gif|bmp)$/;

/** True when the name is exactly a filename this module could have written. */
export function isValidCoverFilename(name: string): boolean {
  return FILENAME_RE.test(name);
}

function extOf(filename: string): string | null {
  const ext = path.extname(filename).slice(1).toLowerCase();
  return ALLOWED_EXTS.has(ext) ? ext : null;
}

function mimeForExt(ext: string): string {
  switch (ext) {
    case 'jpg':
    case 'jpeg':
      return 'image/jpeg';
    case 'png':
      return 'image/png';
    case 'webp':
      return 'image/webp';
    case 'gif':
      return 'image/gif';
    case 'bmp':
      return 'image/bmp';
    default:
      return 'application/octet-stream';
  }
}

/**
 * Import a user-picked image file into the covers directory.
 * Returns the stored filename. Throws CoverError on any problem.
 */
export function importCoverFile(
  srcPath: string,
  coversDir: string,
  scaleImage: (input: Buffer, ext: string) => Buffer,
): string {
  let stat: fs.Stats;
  try {
    stat = fs.statSync(srcPath);
  } catch {
    throw new CoverError('NOT_FOUND', 'Cover image not found.');
  }
  if (!stat.isFile()) throw new CoverError('NOT_A_FILE', 'Cover image is not a file.');
  if (stat.size > COVER_MAX_SOURCE_BYTES) {
    throw new CoverError(
      'TOO_LARGE',
      `Cover image exceeds ${COVER_MAX_SOURCE_BYTES / 1024 / 1024} MB.`,
    );
  }
  const ext = extOf(srcPath);
  if (!ext) {
    throw new CoverError(
      'BAD_TYPE',
      'Unsupported image type. Use PNG, JPG, WebP, GIF or BMP.',
    );
  }
  let bytes: Buffer;
  try {
    bytes = fs.readFileSync(srcPath);
  } catch (err) {
    throw new CoverError('READ_FAILED', `Could not read image: ${(err as Error).message}`);
  }
  let scaled: Buffer;
  try {
    scaled = scaleImage(bytes, ext);
  } catch (err) {
    throw new CoverError(
      'NOT_AN_IMAGE',
      `That file could not be decoded as an image: ${(err as Error).message}`,
    );
  }
  fs.mkdirSync(coversDir, { recursive: true });
  const filename = `${randomUUID()}.${ext}`;
  const dest = path.join(coversDir, filename);
  try {
    fs.writeFileSync(dest, scaled);
  } catch (err) {
    throw new CoverError('WRITE_FAILED', `Could not save cover: ${(err as Error).message}`);
  }
  enforceDirCap(coversDir);
  return filename;
}

/**
 * Read a stored cover as a data URL for the renderer. Returns null when the
 * filename is invalid or the file is gone (renderer shows the placeholder).
 */
export function coverDataUrl(coversDir: string, filename: string): string | null {
  if (!isValidCoverFilename(filename)) return null;
  // The pattern above cannot contain separators, so joining is safe.
  const full = path.join(coversDir, filename);
  let bytes: Buffer;
  try {
    const stat = fs.statSync(full);
    if (!stat.isFile() || stat.size > COVER_MAX_SOURCE_BYTES) return null;
    bytes = fs.readFileSync(full);
  } catch {
    return null;
  }
  const ext = path.extname(filename).slice(1).toLowerCase();
  return `data:${mimeForExt(ext)};base64,${bytes.toString('base64')}`;
}

/** Delete a stored cover file. Missing files are not an error. */
export function deleteCoverFile(coversDir: string, filename: string): void {
  if (!isValidCoverFilename(filename)) return;
  try {
    fs.unlinkSync(path.join(coversDir, filename));
  } catch {
    // Already gone — fine.
  }
}

/**
 * Evict oldest covers (by mtime) until the directory is under the cap.
 * Returns the number of files evicted.
 */
export function enforceDirCap(coversDir: string, maxBytes: number = COVERS_DIR_MAX_BYTES): number {
  let entries: Array<{ name: string; mtime: number; size: number }>;
  try {
    entries = fs
      .readdirSync(coversDir)
      .filter((n) => isValidCoverFilename(n))
      .map((name) => {
        const stat = fs.statSync(path.join(coversDir, name));
        return { name, mtime: stat.mtimeMs, size: stat.size };
      });
  } catch {
    return 0;
  }
  let total = entries.reduce((s, e) => s + e.size, 0);
  let evicted = 0;
  entries.sort((a, b) => a.mtime - b.mtime);
  for (const e of entries) {
    if (total <= maxBytes) break;
    try {
      fs.unlinkSync(path.join(coversDir, e.name));
      total -= e.size;
      evicted++;
    } catch {
      break;
    }
  }
  return evicted;
}
