import { existsSync, lstatSync, readFileSync, realpathSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import { chmod, rename, rm, stat, writeFile } from 'node:fs/promises';
import { dirname, isAbsolute, join, resolve, sep } from 'node:path';
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

/**
 * Write `content` to `fullPath` by REPLACING the directory entry, never by
 * writing in place: the content goes to an exclusively created temporary
 * file in the same directory and is then renamed over the destination.
 *
 * An in-place write (fs.writeFile's truncate-and-rewrite) follows the
 * destination's inode, so a destination that is hard-linked to a file
 * outside the workspace would silently modify that external file too —
 * hard links have no target for the canonical containment walk above to
 * reject (lstat sees an ordinary file and realpath returns the workspace
 * path itself). Renaming instead gives the destination a fresh inode:
 * every other link keeps the old inode and its old content. The same
 * argument covers a destination symlink, which rename replaces rather
 * than writes through.
 */
export async function writeFileReplacing(fullPath: string, content: string): Promise<void> {
  const dir = dirname(fullPath);
  let tmp: string | null = null;
  for (let attempt = 0; attempt < 10 && tmp === null; attempt++) {
    const candidate = join(dir, `.lacc-write-${process.pid}-${randomBytes(8).toString('hex')}.tmp`);
    try {
      // 'wx': fail rather than clobber if the name is somehow taken.
      await writeFile(candidate, content, { encoding: 'utf8', flag: 'wx' });
      tmp = candidate;
    } catch (err) {
      if (err && typeof err === 'object' && 'code' in err && (err as { code?: string }).code === 'EEXIST') continue;
      throw err;
    }
  }
  if (tmp === null) throw new Error(`Could not create a temporary file in ${dir} to replace ${fullPath}.`);
  try {
    // Preserve the replaced file's permission bits (an in-place write
    // would have kept them); a brand-new file keeps the default mode.
    try {
      const existing = await stat(fullPath);
      if (existing.isFile()) await chmod(tmp, existing.mode);
    } catch { /* destination does not exist yet — nothing to preserve */ }
    await rename(tmp, fullPath);
  } catch (err) {
    await rm(tmp, { force: true }).catch(() => undefined);
    throw err;
  }
}

export function readExistingFile(root: string, relativePath: string): string | null {
  let full: string;
  try { full = resolveInWorkspace(root, relativePath); } catch { return null; }
  if (!existsSync(full)) return null;
  try { return readFileSync(full, 'utf8'); } catch { return null; }
}
