/**
 * Filesystem side of attachments: app-owned <userData>/attachments/ dir.
 * The DB row (db/records.ts) and the file bytes are managed together by
 * electron/ipc.ts; this module only touches the filesystem.
 *
 * NOTE: no 'electron' import — backend tests exercise this directly.
 */
import { createHash, randomUUID } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { ALLOWED_ATTACHMENT_MIMES, MAX_ATTACHMENT_BYTES } from '../shared/schemas';
import type { AttachmentKind } from '../shared/types';

const EXT_BY_MIME: Record<string, string> = {
  'image/jpeg': '.jpg',
  'image/png': '.png',
  'image/webp': '.webp',
  'application/pdf': '.pdf',
};

export interface SavedAttachmentFile {
  /** Original name as supplied (validated), for the DB row. */
  originalName: string;
  /** uuid + extension, unique inside the attachments dir. */
  storedName: string;
  sizeBytes: number;
  sha256: string;
  kind: AttachmentKind;
}

export interface SaveAttachmentInput {
  /** User-supplied file name; must already pass attachmentInputSchema. */
  fileName: string;
  mime: string;
  /** Decoded file bytes. */
  bytes: Uint8Array;
  kind: AttachmentKind;
}

/**
 * Sanitize a user-supplied file name: take the basename and keep only
 * [A-Za-z0-9._-]. Throws when nothing usable remains.
 */
export function sanitizeFileName(fileName: string): string {
  const base = path.basename(fileName);
  const cleaned = base.replace(/[^A-Za-z0-9._-]/g, '_').replace(/^\.+/, '');
  if (cleaned.length === 0 || cleaned === '.' || cleaned === '..') {
    throw new Error('File name is not usable after sanitization.');
  }
  return cleaned;
}

export function sha256Hex(bytes: Uint8Array): string {
  return createHash('sha256').update(bytes).digest('hex');
}

/**
 * Validate + persist attachment bytes under attachmentsDir.
 * Enforces the 20 MiB cap and the mime allowlist (defense in depth — the
 * IPC layer already validated the zod schema).
 */
export function saveAttachmentFile(
  attachmentsDir: string,
  input: SaveAttachmentInput,
): SavedAttachmentFile {
  if (!(ALLOWED_ATTACHMENT_MIMES as readonly string[]).includes(input.mime)) {
    throw new Error(`Attachment mime type not allowed: ${input.mime}`);
  }
  const sizeBytes = input.bytes.byteLength;
  if (sizeBytes === 0) {
    throw new Error('Attachment file is empty.');
  }
  if (sizeBytes > MAX_ATTACHMENT_BYTES) {
    throw new Error(
      `Attachment exceeds the ${MAX_ATTACHMENT_BYTES / (1024 * 1024)} MiB limit.`,
    );
  }
  const originalName = sanitizeFileName(input.fileName);
  const ext = EXT_BY_MIME[input.mime] ?? '';
  const storedName = `${randomUUID()}${ext}`;
  fs.mkdirSync(attachmentsDir, { recursive: true });
  const dest = path.join(attachmentsDir, storedName);
  const hash = sha256Hex(input.bytes);
  // Write then re-read to guarantee what is on disk is what we hashed.
  fs.writeFileSync(dest, input.bytes);
  const onDisk = fs.readFileSync(dest);
  if (sha256Hex(onDisk) !== hash) {
    fs.rmSync(dest, { force: true });
    throw new Error('Attachment write verification failed.');
  }
  return { originalName, storedName, sizeBytes, sha256: hash, kind: input.kind };
}

/** Read attachment bytes, or null when the file is missing (integrity gap). */
export function readAttachmentFile(
  attachmentsDir: string,
  storedName: string,
): Buffer | null {
  const filePath = path.join(attachmentsDir, path.basename(storedName));
  try {
    return fs.readFileSync(filePath);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === 'ENOENT') return null;
    throw err;
  }
}

/** Delete an attachment file; a missing file is tolerated (already gone). */
export function deleteAttachmentFile(attachmentsDir: string, storedName: string): void {
  const filePath = path.join(attachmentsDir, path.basename(storedName));
  try {
    fs.rmSync(filePath, { force: true });
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === 'ENOENT') return;
    throw err;
  }
}
