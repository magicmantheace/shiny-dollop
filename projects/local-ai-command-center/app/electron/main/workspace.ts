import { existsSync, lstatSync, readFileSync, realpathSync } from 'node:fs';
import { isAbsolute, join, resolve, sep } from 'node:path';
import { LACC_ERROR_CODES, laccError } from '../../shared/errors.js';

function isInside(root: string, candidate: string): boolean {
  return candidate === root || candidate.startsWith(root + sep);
}

function outside(relativePath: string): ReturnType<typeof laccError> {
  return laccError(LACC_ERROR_CODES.PATH_OUTSIDE_WORKSPACE, `Path escapes the workspace: ${relativePath}`);
}

export function resolveInWorkspace(root: string, relativePath: string): string {
  if (!relativePath || isAbsolute(relativePath)) {
    throw laccError(LACC_ERROR_CODES.PATH_OUTSIDE_WORKSPACE, `Path must be relative to the workspace: ${relativePath}`);
  }
  const resolvedRoot = resolve(root);
  const resolved = resolve(resolvedRoot, relativePath);
  if (resolved !== resolvedRoot && !resolved.startsWith(resolvedRoot + sep)) {
    throw outside(relativePath);
  }
  if (resolved === resolvedRoot) {
    throw laccError(LACC_ERROR_CODES.PATH_OUTSIDE_WORKSPACE, `Path must name a file inside the workspace: ${relativePath}`);
  }

  // Canonical containment: a lexical prefix check alone accepts paths that
  // traverse a symlink / directory junction inside the workspace pointing
  // outside it. Resolve the canonical root, then walk every existing path
  // component (including the destination itself); any component whose real
  // path leaves the canonical root is rejected. Non-existent trailing
  // components cannot be links, so the walk stops at the first missing one —
  // its nearest existing ancestor has already been validated.
  let canonicalRoot = resolvedRoot;
  try { canonicalRoot = realpathSync(resolvedRoot); } catch { /* root may not exist yet; lexical root stands */ }

  const rel = resolved.slice(resolvedRoot.length + 1);
  const parts = rel.split(sep).filter((p) => p.length > 0);
  let current = canonicalRoot;
  for (const part of parts) {
    current = join(current, part);
    let stat;
    try { stat = lstatSync(current); } catch { break; }
    if (stat.isSymbolicLink()) {
      let real: string;
      try { real = realpathSync(current); } catch { throw outside(relativePath); }
      if (!isInside(canonicalRoot, real)) throw outside(relativePath);
      current = real;
    } else {
      // Defence in depth for junctions / non-symlink reparse points: the
      // real path of any existing component must stay inside.
      try {
        const real = realpathSync(current);
        if (!isInside(canonicalRoot, real)) throw outside(relativePath);
        current = real;
      } catch (err) {
        if (err && typeof err === 'object' && 'code' in err && (err as { code?: string }).code === LACC_ERROR_CODES.PATH_OUTSIDE_WORKSPACE) throw err;
        // If realpath fails for another reason, fall through with lexical path.
      }
    }
  }
  return resolved;
}

export function readExistingFile(root: string, relativePath: string): string | null {
  let full: string;
  try { full = resolveInWorkspace(root, relativePath); } catch { return null; }
  if (!existsSync(full)) return null;
  try { return readFileSync(full, 'utf8'); } catch { return null; }
}
