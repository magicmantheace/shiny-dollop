/**
 * Static-site export pipeline.
 *
 * Renders a site's theme to files, runs the full validator suite, and writes
 * the result to destDir. Export is BLOCKED (ok:false, nothing written) when
 * any validation issue has severity "error".
 *
 * Named errors (thrown as Error with a "CODE: message" message):
 * - SITE_NOT_FOUND:<id>
 * - THEME_NOT_FOUND:<themeId>
 * - EXPORT_DEST_NOT_EMPTY:<dir>   (existing directory with files in it)
 * - EXPORT_DEST_NOT_DIR:<path>    (existing path that is not a directory)
 */
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import type { ExportResult, RenderedPage, Site, ValidationIssue } from '../../shared/types.js';
import { getTheme } from './themes/index.js';
import { hasBlockingErrors, validateExport, type Issue } from './validate.js';
import type { SiteStore } from './db.js';

export class BwgError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(`${code}: ${message}`);
    this.name = 'BwgError';
    this.code = code;
  }
}

export interface ExportDeps {
  store: SiteStore;
}

function toPublicIssues(issues: Issue[]): ValidationIssue[] {
  return issues.map(({ code, message, field }) => ({ code, message, field }));
}

/** Render a site to its file map (no validation, no disk writes). */
export function renderSiteFiles(site: Site): Record<string, string> {
  const theme = getTheme(site.themeId);
  if (!theme) throw new BwgError('THEME_NOT_FOUND', `Unknown theme "${site.themeId}".`);
  return theme.renderSite(site.profile).files;
}

/** Render a site to preview pages (HTML pages only, in theme page order). */
export function renderPreviewPages(site: Site): RenderedPage[] {
  const theme = getTheme(site.themeId);
  if (!theme) throw new BwgError('THEME_NOT_FOUND', `Unknown theme "${site.themeId}".`);
  const files = theme.renderSite(site.profile).files;
  const pages: RenderedPage[] = [];
  for (const p of theme.info.pages) {
    if (!p.endsWith('.html')) continue;
    const html = files[p];
    if (html !== undefined) pages.push({ path: p, html });
  }
  return pages;
}

/** Validate a site for export without writing anything. */
export function validateSiteExport(deps: ExportDeps, id: string): { ok: boolean; issues: ValidationIssue[] } {
  const site = deps.store.get(id);
  if (!site) throw new BwgError('SITE_NOT_FOUND', `No site with id "${id}".`);
  const theme = getTheme(site.themeId);
  if (!theme) throw new BwgError('THEME_NOT_FOUND', `Unknown theme "${site.themeId}".`);
  const files = theme.renderSite(site.profile).files;
  const issues = validateExport(site.profile, files, theme);
  return { ok: !hasBlockingErrors(issues), issues: toPublicIssues(issues) };
}

/**
 * Run the full export: render, validate, write to destDir.
 * destDir must not exist or must be an empty directory.
 */
export async function runExport(deps: ExportDeps, id: string, destDir: string): Promise<ExportResult> {
  const site = deps.store.get(id);
  if (!site) throw new BwgError('SITE_NOT_FOUND', `No site with id "${id}".`);
  const theme = getTheme(site.themeId);
  if (!theme) throw new BwgError('THEME_NOT_FOUND', `Unknown theme "${site.themeId}".`);

  const files = theme.renderSite(site.profile).files;
  const issues = validateExport(site.profile, files, theme);
  const ok = !hasBlockingErrors(issues);
  const abs = path.resolve(destDir);

  if (!ok) {
    return { ok: false, destDir: abs, files: [], issues: toPublicIssues(issues) };
  }

  let st: Awaited<ReturnType<typeof fs.stat>> | null = null;
  try {
    st = await fs.stat(abs);
  } catch {
    st = null;
  }
  if (st && !st.isDirectory()) {
    throw new BwgError('EXPORT_DEST_NOT_DIR', `Destination "${abs}" exists and is not a directory.`);
  }
  if (st && st.isDirectory()) {
    const entries = await fs.readdir(abs);
    if (entries.length > 0) {
      throw new BwgError(
        'EXPORT_DEST_NOT_EMPTY',
        `Destination "${abs}" is not empty. Choose an empty or new folder.`,
      );
    }
  } else {
    await fs.mkdir(abs, { recursive: true });
  }

  const written: string[] = [];
  const sorted = Object.keys(files).sort();
  for (const rel of sorted) {
    const target = path.join(abs, rel);
    await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.writeFile(target, files[rel] ?? '', 'utf8');
    written.push(rel);
  }
  return { ok: true, destDir: abs, files: written, issues: toPublicIssues(issues) };
}
