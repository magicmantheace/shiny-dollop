import { createHash } from 'node:crypto';
import { readdirSync, realpathSync } from 'node:fs';
import { join, resolve } from 'node:path';

export interface DiscoveredGame {
  installPath: string;
  title: string;
  originalTitle: string;
}

export const MAX_SCAN_DEPTH = 4;
export const SKIPPED_DIR_NAMES = new Set(['node_modules', '.git', 'windows']);

/**
 * Normalize a path for identity purposes: absolute, forward slashes,
 * lowercased (Windows installs are case-insensitive).
 */
export function normalizePathForId(p: string): string {
  return resolve(p).replace(/\\/g, '/').toLowerCase();
}

/** Stable id for a game: sha256 of the normalized install path at first import. */
export function gameIdFor(installPath: string): string {
  return createHash('sha256').update(normalizePathForId(installPath)).digest('hex');
}

/**
 * Derive a human title from an exe filename:
 * strip the .exe extension, turn underscores/dots into spaces, collapse runs.
 */
export function titleFromExeName(fileName: string): string {
  const stem = fileName.replace(/\.exe$/i, '');
  return stem
    .replace(/[_.]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function isSkippedDir(name: string): boolean {
  return SKIPPED_DIR_NAMES.has(name.toLowerCase());
}

/**
 * Scan roots for *.exe files, max depth 4, skipping node_modules/.git/Windows.
 * Symlinks are resolved and revisited directories are skipped (loop guard).
 * Returns discovered executables in deterministic (sorted) order.
 */
export function scanRoots(roots: string[]): DiscoveredGame[] {
  const found: DiscoveredGame[] = [];
  const seenDirs = new Set<string>();

  function walk(dir: string, depth: number): void {
    if (depth > MAX_SCAN_DEPTH) return;

    let real: string;
    try {
      real = realpathSync(dir);
    } catch {
      return; // unreadable / vanished
    }
    if (seenDirs.has(real)) return;
    seenDirs.add(real);

    let entries: Array<{ name: string; isDirectory(): boolean; isFile(): boolean }>;
    try {
      entries = readdirSync(dir, { withFileTypes: true }) as unknown as Array<{
        name: string;
        isDirectory(): boolean;
        isFile(): boolean;
      }>;
    } catch {
      return; // permission denied etc.
    }

    for (const entry of entries) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        if (isSkippedDir(entry.name)) continue;
        walk(full, depth + 1);
      } else if (entry.isFile() && /\.exe$/i.test(entry.name)) {
        const title = titleFromExeName(entry.name);
        found.push({ installPath: full, title, originalTitle: title });
      }
    }
  }

  for (const root of roots) {
    walk(root, 0);
  }

  found.sort((a, b) => a.installPath.localeCompare(b.installPath));
  return found;
}
