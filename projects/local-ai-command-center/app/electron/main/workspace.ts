import { existsSync, readFileSync } from 'node:fs';
import { isAbsolute, resolve, sep } from 'node:path';
import { LACC_ERROR_CODES, laccError } from '../../shared/errors.js';

export function resolveInWorkspace(root: string, relativePath: string): string {
  if (!relativePath || isAbsolute(relativePath)) {
    throw laccError(LACC_ERROR_CODES.PATH_OUTSIDE_WORKSPACE, `Path must be relative to the workspace: ${relativePath}`);
  }
  const resolvedRoot = resolve(root);
  const resolved = resolve(resolvedRoot, relativePath);
  if (resolved !== resolvedRoot && !resolved.startsWith(resolvedRoot + sep)) {
    throw laccError(LACC_ERROR_CODES.PATH_OUTSIDE_WORKSPACE, `Path escapes the workspace: ${relativePath}`);
  }
  if (resolved === resolvedRoot) {
    throw laccError(LACC_ERROR_CODES.PATH_OUTSIDE_WORKSPACE, `Path must name a file inside the workspace: ${relativePath}`);
  }
  return resolved;
}

export function readExistingFile(root: string, relativePath: string): string | null {
  let full: string;
  try { full = resolveInWorkspace(root, relativePath); } catch { return null; }
  if (!existsSync(full)) return null;
  try { return readFileSync(full, 'utf8'); } catch { return null; }
}
