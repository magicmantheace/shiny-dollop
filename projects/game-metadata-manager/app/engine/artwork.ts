import { randomUUID } from 'node:crypto';
import { copyFileSync, existsSync, lstatSync, mkdirSync, readFileSync, realpathSync, unlinkSync, writeFileSync } from 'node:fs';
import { join, basename } from 'node:path';
import { pathToFileURL } from 'node:url';
import type { DatabaseSync } from 'node:sqlite';
import type { Artwork } from '../shared/ipc-contract.js';

export const MAX_ARTWORK_BYTES = 10 * 1024 * 1024;

type SupportedMime = 'image/png' | 'image/jpeg' | 'image/webp';

function detectMime(buf: Buffer): SupportedMime | null {
  if (
    buf.length >= 8 &&
    buf[0] === 0x89 &&
    buf[1] === 0x50 &&
    buf[2] === 0x4e &&
    buf[3] === 0x47 &&
    buf[4] === 0x0d &&
    buf[5] === 0x0a &&
    buf[6] === 0x1a &&
    buf[7] === 0x0a
  ) {
    return 'image/png';
  }
  if (buf.length >= 3 && buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) {
    return 'image/jpeg';
  }
  if (
    buf.length >= 12 &&
    buf[0] === 0x52 && // R
    buf[1] === 0x49 && // I
    buf[2] === 0x46 && // F
    buf[3] === 0x46 && // F
    buf[8] === 0x57 && // W
    buf[9] === 0x45 && // E
    buf[10] === 0x42 && // B
    buf[11] === 0x50 // P
  ) {
    return 'image/webp';
  }
  return null;
}

function extensionFor(mime: SupportedMime): string {
  return mime === 'image/png' ? '.png' : mime === 'image/jpeg' ? '.jpg' : '.webp';
}

export class ArtworkStore {
  constructor(
    private db: DatabaseSync,
    private cacheDir: string
  ) {
    mkdirSync(cacheDir, { recursive: true });
  }

  /**
   * Validate and import an image file into the app-owned cache.
   * - refuses unreadable paths, non-files, and >10 MB inputs
   * - validates by magic bytes (PNG/JPEG/WEBP only), not by extension
   * - symlinks are resolved explicitly (never followed blindly) and the
   *   resolved target is used for all reads
   */
  add(sourcePath: string, provenance: string): Artwork {
    let st: ReturnType<typeof lstatSync>;
    try {
      st = lstatSync(sourcePath);
    } catch {
      throw new Error(`artwork source not found: ${basename(sourcePath)}`);
    }

    let targetPath = sourcePath;
    if (st.isSymbolicLink()) {
      // Resolve the link explicitly and operate on the resolved target.
      targetPath = realpathSync(sourcePath);
      st = lstatSync(targetPath);
    }
    if (!st.isFile()) throw new Error('artwork source is not a file');
    if (st.size > MAX_ARTWORK_BYTES) {
      throw new Error(
        `artwork too large: ${(st.size / 1024 / 1024).toFixed(2)} MB > 10 MB`
      );
    }

    const bytes = readFileSync(targetPath);
    const mime = detectMime(bytes);
    if (!mime) throw new Error('unsupported image type: expected PNG, JPEG or WEBP');

    const id = randomUUID();
    const fileName = `${id}${extensionFor(mime)}`;
    const dest = join(this.cacheDir, fileName);
    copyFileSync(targetPath, dest);

    const addedAt = new Date().toISOString();
    this.db
      .prepare('INSERT INTO artwork (id, file_name, provenance, mime, added_at) VALUES (?, ?, ?, ?, ?)')
      .run(id, fileName, provenance || 'file', mime, addedAt);

    return { id, fileName, provenance: provenance || 'file', mime, addedAt };
  }

  /** Add base64 image data (used by bundle import). Returns null if data is invalid. */
  addBase64(id: string, provenance: string, mime: string, dataBase64: string): Artwork | null {
    if (mime !== 'image/png' && mime !== 'image/jpeg' && mime !== 'image/webp') return null;
    let bytes: Buffer;
    try {
      bytes = Buffer.from(dataBase64, 'base64');
    } catch {
      return null;
    }
    if (bytes.length === 0 || bytes.length > MAX_ARTWORK_BYTES) return null;
    if (detectMime(bytes) !== mime) return null; // declared mime must match magic bytes

    const fileName = `${id}${extensionFor(mime)}`;
    const dest = join(this.cacheDir, fileName);
    if (!existsSync(dest)) {
      mkdirSync(this.cacheDir, { recursive: true });
      writeFileSync(dest, bytes);
    }

    const existing = this.db
      .prepare('SELECT * FROM artwork WHERE id = ?')
      .get(id) as unknown as { id: string } | undefined;
    if (existing) return this.get(id);

    const addedAt = new Date().toISOString();
    this.db
      .prepare('INSERT INTO artwork (id, file_name, provenance, mime, added_at) VALUES (?, ?, ?, ?, ?)')
      .run(id, fileName, provenance || 'bundle', mime, addedAt);
    return { id, fileName, provenance: provenance || 'bundle', mime, addedAt };
  }

  list(): Artwork[] {
    const rows = this.db
      .prepare('SELECT * FROM artwork ORDER BY added_at DESC')
      .all() as unknown as Array<{ id: string; file_name: string; provenance: string; mime: string; added_at: string }>;
    return rows.map((r) => ({
      id: r.id,
      fileName: r.file_name,
      provenance: r.provenance,
      mime: r.mime,
      addedAt: r.added_at,
    }));
  }

  get(artworkId: string): Artwork | null {
    const row = this.db
      .prepare('SELECT * FROM artwork WHERE id = ?')
      .get(artworkId) as unknown as { id: string; file_name: string; provenance: string; mime: string; added_at: string } | undefined;
    if (!row) return null;
    return { id: row.id, fileName: row.file_name, provenance: row.provenance, mime: row.mime, addedAt: row.added_at };
  }

  filePath(artworkId: string): string {
    const art = this.get(artworkId);
    if (!art) throw new Error(`artwork not found: ${artworkId}`);
    const full = join(this.cacheDir, art.fileName);
    if (!existsSync(full)) throw new Error('artwork file missing from cache');
    return full;
  }

  fileUrl(artworkId: string): string {
    return pathToFileURL(this.filePath(artworkId)).toString();
  }

  /** Remove all artwork rows and their cached files. */
  clear(): void {
    for (const art of this.list()) {
      const full = join(this.cacheDir, art.fileName);
      if (existsSync(full)) {
        try {
          unlinkSync(full);
        } catch {
          // best effort — stale files must not block a wipe
        }
      }
    }
    this.db.prepare('DELETE FROM artwork').run();
  }
}
