/**
 * APPROXIMATE PREVIEW RENDERER — display only.
 *
 * This module is a pure, local re-implementation of the document renderers
 * for on-screen preview purposes. It deliberately mirrors the backend
 * exporters' output shape but MUST NOT be treated as authoritative: the
 * HTML produced by `export.generate` (Worker A's backend) is the real
 * artifact. The preview pane labels itself accordingly.
 *
 * Keep the escaping logic in sync with the backend: every interpolated
 * value goes through `escapeHtml`.
 */
import type {
  DocumentRecord,
  ListItemFieldDef,
  TemplateFieldDef,
  TemplateManifest,
  ThemeTokens,
} from '../shared/types';
import { FONT_STACKS } from './fonts';

const HEX_COLOR = /^#[0-9a-fA-F]{6}$/;
const MAX_SPACING = 64;

export function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function sanitizeColor(value: unknown, fallback: string): string {
  return typeof value === 'string' && HEX_COLOR.test(value) ? value : fallback;
}

function sanitizeFont(value: unknown, fallback: string): string {
  if (typeof value !== 'string') return fallback;
  return FONT_STACKS.some((s) => s.value === value) ? value : fallback;
}

function sanitizeSpacing(value: unknown, fallback: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback;
  return Math.min(Math.max(Math.round(value), 0), MAX_SPACING);
}

/** Resolve a document's (possibly partial) tokens against safe defaults. */
export function resolveTokens(
  tokens: Partial<ThemeTokens>,
  defaults: ThemeTokens,
): ThemeTokens {
  return {
    bg: sanitizeColor(tokens.bg, defaults.bg),
    text: sanitizeColor(tokens.text, defaults.text),
    accent: sanitizeColor(tokens.accent, defaults.accent),
    headingFont: sanitizeFont(tokens.headingFont, defaults.headingFont),
    bodyFont: sanitizeFont(tokens.bodyFont, defaults.bodyFont),
    spacing: sanitizeSpacing(tokens.spacing, defaults.spacing),
  };
}

function renderScalarField(field: TemplateFieldDef, value: unknown): string {
  const label = escapeHtml(field.label);
  const required = field.required ? ' <span aria-hidden="true">*</span>' : '';
  if (value === undefined || value === null || value === '') {
    return `<p class="pv-field"><span class="pv-label">${label}${required}:</span> <em class="pv-empty">not set</em></p>`;
  }
  return `<p class="pv-field"><span class="pv-label">${label}${required}:</span> ${escapeHtml(value)}</p>`;
}

function renderListCell(
  col: ListItemFieldDef,
  raw: unknown,
): string {
  switch (col.type) {
    case 'boolean':
      return raw === true ? 'Yes' : 'No';
    case 'string-list':
      return Array.isArray(raw) ? raw.map((v) => escapeHtml(v)).join('<br>') : escapeHtml(raw);
    default:
      return escapeHtml(raw);
  }
}

function renderListField(field: TemplateFieldDef, value: unknown): string {
  const label = escapeHtml(field.label);
  const rows = Array.isArray(value) ? value : [];
  if (rows.length === 0) {
    return `<section class="pv-list"><h3>${label}</h3><p><em class="pv-empty">no rows</em></p></section>`;
  }
  const schema = field.itemSchema;
  let body: string;
  if (schema && schema.length > 0) {
    const head = schema.map((c) => `<th>${escapeHtml(c.label)}</th>`).join('');
    const trs = rows
      .map((row) => {
        const obj =
          row !== null && typeof row === 'object'
            ? (row as Record<string, unknown>)
            : {};
        const tds = schema
          .map((c) => `<td>${renderListCell(c, obj[c.key])}</td>`)
          .join('');
        return `<tr>${tds}</tr>`;
      })
      .join('');
    body = `<table class="pv-table"><thead><tr>${head}</tr></thead><tbody>${trs}</tbody></table>`;
  } else {
    body = `<ul class="pv-bullets">${rows.map((r) => `<li>${escapeHtml(r)}</li>`).join('')}</ul>`;
  }
  return `<section class="pv-list"><h3>${label}</h3>${body}</section>`;
}

/**
 * Render a whole document to a standalone HTML string for the preview pane.
 * Pure function: no DOM, no network, safe to call on every keystroke.
 */
export function renderPreviewHtml(
  manifest: TemplateManifest,
  doc: DocumentRecord,
): string {
  const tokens = resolveTokens(doc.tokens, manifest.defaultTokens);
  const pad = tokens.spacing;
  const sections = manifest.fields
    .map((f) =>
      f.type === 'list'
        ? renderListField(f, doc.data[f.key])
        : renderScalarField(f, doc.data[f.key]),
    )
    .join('\n');

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${escapeHtml(manifest.name)} — preview</title>
<style>
  body { background: ${tokens.bg}; color: ${tokens.text}; font-family: ${tokens.bodyFont}; margin: 0; padding: ${pad * 2}px; }
  h1, h2, h3 { font-family: ${tokens.headingFont}; }
  h1 { border-bottom: 3px solid ${tokens.accent}; padding-bottom: ${pad}px; }
  .pv-label { font-weight: 600; }
  .pv-empty { color: ${tokens.text}; opacity: 0.55; }
  .pv-table { border-collapse: collapse; width: 100%; margin: ${pad}px 0; }
  .pv-table th, .pv-table td { border: 1px solid ${tokens.accent}; padding: ${Math.max(4, pad / 2)}px ${pad}px; text-align: left; }
  .pv-table th { background: ${tokens.accent}; color: ${tokens.bg}; }
  .pv-list { margin: ${pad}px 0; }
  .pv-bullets { padding-left: 1.25em; }
  .pv-note { margin-top: ${pad * 2}px; font-size: 0.8em; opacity: 0.6; }
</style>
</head>
<body>
<!-- DTF preview render: approximate. The exported file is authoritative. -->
<h1>${escapeHtml(manifest.name)}</h1>
<p class="pv-desc">${escapeHtml(manifest.description)}</p>
${sections}
<p class="pv-note">Preview is approximate — the exported file is authoritative.</p>
</body>
</html>`;
}
