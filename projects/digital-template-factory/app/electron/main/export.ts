/**
 * Export pipeline: render + validators, in order.
 * Deterministic — two calls with identical inputs produce identical
 * HTML and identical contentHash.
 */
import { createHash } from 'node:crypto';
import type {
  DocumentRecord,
  ExportFormat,
  ExportResult,
  LicenseRecord,
  TemplateManifest,
} from '../../shared/types';
import { renderBundledTemplate } from './templates';
import { validateRequiredFields } from './validators/required';
import { checkContrast } from './validators/contrast';
import { validateStructure } from './validators/structure';

export function sha256Hex(input: string): string {
  return createHash('sha256').update(input, 'utf8').digest('hex');
}

export interface ExportInput {
  document: DocumentRecord;
  manifest: TemplateManifest;
  format: ExportFormat;
}

/**
 * Run the full export pipeline for a document:
 *   1. required-field validation
 *   2. render (bundled templates only)
 *   3. contrast validation
 *   4. structure validation
 * On success returns { ok: true, html, errors: [], licenseRecord }.
 * exportedAt is returned separately and never hashed.
 */
export function generateExport(input: ExportInput): ExportResult {
  const { document, manifest, format } = input;

  const missing = validateRequiredFields(manifest, document.data);
  if (missing.length > 0) {
    return {
      ok: false,
      errors: missing.map((key) => `FIELD_REQUIRED:${key}`),
    };
  }

  const html = renderBundledTemplate(
    manifest.templateId,
    document.data,
    document.tokens,
    format,
  );
  if (html === undefined) {
    return { ok: false, errors: ['TEMPLATE_RENDER_UNSUPPORTED'] };
  }

  const contrastFailures = checkContrast(document.tokens);
  if (contrastFailures.length > 0) {
    return {
      ok: false,
      errors: contrastFailures.map((key) => `CONTRAST_FAIL:${key}`),
    };
  }

  const structure = validateStructure(html);
  if (!structure.ok) {
    return {
      ok: false,
      errors: [`STRUCTURE_INVALID:${structure.reason ?? 'unknown'}`],
    };
  }

  const licenseRecord: LicenseRecord = {
    templateId: manifest.templateId,
    templateVersion: manifest.version,
    manifestVersion: manifest.manifestVersion,
    format,
    contentHash: sha256Hex(html),
    exportedAt: new Date().toISOString(),
  };

  return { ok: true, html, errors: [], licenseRecord };
}
