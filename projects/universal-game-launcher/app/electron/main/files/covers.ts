/**
 * Cover-art wiring with Electron dependencies.
 *
 * Pure storage logic lives in cover-store.ts (no Electron imports, fully
 * tested). This module adds the app-data directory, nativeImage scaling,
 * and the picker-to-import flow used by the IPC layer.
 */
import { app, nativeImage } from 'electron';
import path from 'node:path';
import {
  COVER_MAX_DIM,
  importCoverFile,
} from './cover-store';
import { chooseCoverImage } from './picker';

export * from './cover-store';

export function getCoversDir(): string {
  return path.join(app.getPath('userData'), 'covers');
}

/** Scale to fit within COVER_MAX_DIM using Electron's nativeImage. */
function scaleWithNativeImage(input: Buffer): Buffer {
  const img = nativeImage.createFromBuffer(input);
  if (img.isEmpty()) {
    throw new Error('not a decodable image');
  }
  const { width, height } = img.getSize();
  const longest = Math.max(width, height);
  if (longest <= COVER_MAX_DIM) return input;
  const scale = COVER_MAX_DIM / longest;
  return img
    .resize({ width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) })
    .toJPEG(85);
}

/**
 * Let the user pick a cover image and import it into the covers dir.
 * Returns the stored filename (validated, uuid-based) or a cancellation.
 */
export async function chooseCover(): Promise<{ canceled: true } | { coverPath: string }> {
  const picked = await chooseCoverImage();
  if ('canceled' in picked) return { canceled: true };
  const coverPath = importCoverFile(picked.path, getCoversDir(), scaleWithNativeImage);
  return { coverPath };
}
