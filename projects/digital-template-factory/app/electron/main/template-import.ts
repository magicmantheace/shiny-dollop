/**
 * Validation of external template bundles for `templates:import`.
 * A bundle must be a JSON manifest with manifestVersion '1.0.0',
 * templateId, name, version, fields[] and default tokens.
 * Anything else is rejected with TEMPLATE_VERSION_UNSUPPORTED or
 * TEMPLATE_INVALID.
 */
import type { TemplateManifest } from '../../shared/types';
import { DtfError } from './validation';

const SUPPORTED_MANIFEST_VERSION = '1.0.0';

const FIELD_TYPES = new Set(['text', 'number', 'date', 'list']);
const ITEM_TYPES = new Set(['text', 'number', 'date', 'boolean', 'string-list']);
const TOKEN_KEYS = ['bg', 'text', 'accent', 'headingFont', 'bodyFont', 'spacing'] as const;
const HEX_COLOR_PATTERN = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

function isValidDateString(value: string): boolean {
  if (!DATE_PATTERN.test(value)) return false;
  const [y, m, d] = value.split('-').map(Number) as [number, number, number];
  if (m < 1 || m > 12 || d < 1 || d > 31) return false;
  const dt = new Date(Date.UTC(y, m - 1, d));
  return (
    dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function invalid(message: string): never {
  throw new DtfError('TEMPLATE_INVALID', message);
}

function validateTokens(raw: unknown): void {
  if (!isRecord(raw)) invalid('Bundle "defaultTokens" must be an object.');
  for (const key of TOKEN_KEYS) {
    const value = raw[key];
    if (key === 'spacing') {
      if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
        invalid('Token "spacing" must be a number >= 0.');
      }
      continue;
    }
    if (key === 'headingFont' || key === 'bodyFont') {
      if (typeof value !== 'string' || value.trim().length === 0) {
        invalid(`Token "${key}" must be a non-empty font name.`);
      }
      continue;
    }
    if (typeof value !== 'string' || !HEX_COLOR_PATTERN.test(value)) {
      invalid(`Token "${key}" must be a valid #rgb or #rrggbb color.`);
    }
  }
}

/**
 * Validate the nested `itemSchema` of a `list` field. Every entry must be
 * a complete ListItemFieldDef: non-empty unique key, non-empty label, a
 * supported item type, boolean `required`, and finite numeric bounds.
 * Anything less is stored verbatim today and later crashes ListEditor /
 * renderPreviewHtml, which dereference `col.key` / `col.label` — so a
 * malformed schema must fail the import here with TEMPLATE_INVALID.
 * Returns the validated entries for prefill checking.
 */
function validateItemSchema(
  fieldKey: string,
  raw: unknown,
): Record<string, unknown>[] {
  if (!Array.isArray(raw)) {
    invalid(`Field "${fieldKey}" "itemSchema" must be an array.`);
  }
  const seen = new Set<string>();
  for (const entry of raw as unknown[]) {
    if (!isRecord(entry)) {
      invalid(`Field "${fieldKey}" itemSchema entries must be objects.`);
    }
    const { key, label, type, required } = entry;
    if (typeof key !== 'string' || key.length === 0) {
      invalid(`Field "${fieldKey}" itemSchema entries must have a non-empty string "key".`);
    }
    if (seen.has(key)) {
      invalid(`Field "${fieldKey}" has duplicate itemSchema key "${key}".`);
    }
    seen.add(key);
    if (typeof label !== 'string' || label.length === 0) {
      invalid(`Field "${fieldKey}" item "${key}" must have a non-empty string "label".`);
    }
    if (typeof type !== 'string' || !ITEM_TYPES.has(type)) {
      invalid(`Field "${fieldKey}" item "${key}" has unsupported type "${String(type)}".`);
    }
    if (typeof required !== 'boolean') {
      invalid(`Field "${fieldKey}" item "${key}" must declare boolean "required".`);
    }
    if (
      entry.min !== undefined &&
      (typeof entry.min !== 'number' || !Number.isFinite(entry.min))
    ) {
      invalid(`Field "${fieldKey}" item "${key}" "min" must be a finite number.`);
    }
    if (
      entry.max !== undefined &&
      (typeof entry.max !== 'number' || !Number.isFinite(entry.max))
    ) {
      invalid(`Field "${fieldKey}" item "${key}" "max" must be a finite number.`);
    }
    if (
      typeof entry.min === 'number' &&
      typeof entry.max === 'number' &&
      entry.min > entry.max
    ) {
      invalid(`Field "${fieldKey}" item "${key}" "min" must be <= "max".`);
    }
  }
  return raw as Record<string, unknown>[];
}

/** Check one prefill cell against its nested schema entry. */
function validatePrefillValue(
  fieldKey: string,
  sub: Record<string, unknown>,
  value: unknown,
): void {
  const path = `${fieldKey} prefill "${String(sub.key)}"`;
  switch (sub.type) {
    case 'text':
      if (typeof value !== 'string') invalid(`"${path}" must be a string.`);
      return;
    case 'number': {
      let n: number;
      if (typeof value === 'number') {
        n = value;
      } else if (typeof value === 'string' && value.trim() !== '') {
        n = Number(value);
      } else {
        invalid(`"${path}" must be a number.`);
      }
      if (!Number.isFinite(n)) invalid(`"${path}" must be a finite number.`);
      if (typeof sub.min === 'number' && n < sub.min) {
        invalid(`"${path}" must be >= ${sub.min}.`);
      }
      if (typeof sub.max === 'number' && n > sub.max) {
        invalid(`"${path}" must be <= ${sub.max}.`);
      }
      return;
    }
    case 'date':
      if (typeof value !== 'string' || !isValidDateString(value)) {
        invalid(`"${path}" must be a YYYY-MM-DD date.`);
      }
      return;
    case 'boolean':
      if (typeof value !== 'boolean') invalid(`"${path}" must be a boolean.`);
      return;
    case 'string-list':
      if (!Array.isArray(value) || !value.every((v) => typeof v === 'string')) {
        invalid(`"${path}" must be an array of strings.`);
      }
      return;
  }
}

/**
 * Validate a `list` field's `prefill` rows against its (already validated)
 * item schema: rows must be objects using only declared keys, required
 * nested fields must be present, and every value must satisfy its type
 * and bounds — the same rules `coerceFieldValue` applies on save, so a
 * stored template can always produce editable documents.
 */
function validatePrefill(
  fieldKey: string,
  schema: Record<string, unknown>[],
  raw: unknown,
): void {
  if (!Array.isArray(raw)) {
    invalid(`Field "${fieldKey}" "prefill" must be an array.`);
  }
  if (schema.length === 0) {
    for (const row of raw as unknown[]) {
      if (typeof row !== 'string') {
        invalid(`Field "${fieldKey}" prefill rows must be strings without an itemSchema.`);
      }
    }
    return;
  }
  const allowed = new Set(schema.map((s) => s.key as string));
  for (const row of raw as unknown[]) {
    if (!isRecord(row)) {
      invalid(`Field "${fieldKey}" prefill rows must be objects.`);
    }
    for (const key of Object.keys(row)) {
      if (!allowed.has(key)) {
        invalid(`Field "${fieldKey}" prefill has unknown item key "${key}".`);
      }
    }
    for (const sub of schema) {
      const value = row[sub.key as string];
      if (value === undefined || value === null) {
        if (sub.required === true) {
          invalid(
            `Field "${fieldKey}" prefill is missing required item field "${String(sub.key)}".`,
          );
        }
        continue;
      }
      validatePrefillValue(fieldKey, sub, value);
    }
  }
}

function validateFields(raw: unknown): void {
  if (!Array.isArray(raw) || raw.length === 0) {
    invalid('Bundle "fields" must be a non-empty array.');
  }
  const seen = new Set<string>();
  for (const entry of raw as unknown[]) {
    if (!isRecord(entry)) invalid('Each field must be an object.');
    const { key, label, type, required } = entry;
    if (typeof key !== 'string' || key.length === 0) {
      invalid('Each field must have a non-empty string "key".');
    }
    if (seen.has(key)) invalid(`Duplicate field key "${key}".`);
    seen.add(key);
    if (typeof label !== 'string' || label.length === 0) {
      invalid(`Field "${key}" must have a non-empty string "label".`);
    }
    if (typeof type !== 'string' || !FIELD_TYPES.has(type)) {
      invalid(`Field "${key}" has unsupported type "${String(type)}".`);
    }
    if (typeof required !== 'boolean') {
      invalid(`Field "${key}" must declare boolean "required".`);
    }
    if (entry.min !== undefined && typeof entry.min !== 'number') {
      invalid(`Field "${key}" "min" must be a number.`);
    }
    if (entry.max !== undefined && typeof entry.max !== 'number') {
      invalid(`Field "${key}" "max" must be a number.`);
    }
    if (type === 'list') {
      const schema =
        entry.itemSchema !== undefined
          ? validateItemSchema(key, entry.itemSchema)
          : [];
      if (entry.minItems !== undefined && typeof entry.minItems !== 'number') {
        invalid(`Field "${key}" "minItems" must be a number.`);
      }
      if (entry.prefill !== undefined) {
        validatePrefill(key, schema, entry.prefill);
      }
    }
  }
}

/**
 * Parse and validate an external template bundle JSON string.
 * Returns the manifest on success; throws DtfError with code
 * TEMPLATE_VERSION_UNSUPPORTED or TEMPLATE_INVALID otherwise.
 */
export function parseTemplateBundle(bundleJson: string): TemplateManifest {
  let raw: unknown;
  try {
    raw = JSON.parse(bundleJson);
  } catch {
    invalid('Bundle is not valid JSON.');
  }
  if (!isRecord(raw)) invalid('Bundle must be a JSON object.');

  if (typeof raw.manifestVersion !== 'string') {
    invalid('Bundle is missing string "manifestVersion".');
  }
  if (raw.manifestVersion !== SUPPORTED_MANIFEST_VERSION) {
    throw new DtfError(
      'TEMPLATE_VERSION_UNSUPPORTED',
      `Unsupported manifestVersion "${raw.manifestVersion}"; expected "${SUPPORTED_MANIFEST_VERSION}".`,
    );
  }

  for (const key of ['templateId', 'name', 'version'] as const) {
    if (typeof raw[key] !== 'string' || (raw[key] as string).length === 0) {
      invalid(`Bundle is missing non-empty string "${key}".`);
    }
  }
  if (typeof raw.description !== 'string') {
    invalid('Bundle is missing string "description".');
  }

  validateFields(raw.fields);
  // Accept both "defaultTokens" and the shorthand "tokens".
  const tokens = raw.defaultTokens ?? raw.tokens;
  if (tokens === undefined) {
    invalid('Bundle is missing "defaultTokens" (or "tokens").');
  }
  validateTokens(tokens);

  return {
    manifestVersion: SUPPORTED_MANIFEST_VERSION,
    templateId: raw.templateId as string,
    name: raw.name as string,
    description: raw.description as string,
    version: raw.version as string,
    fields: raw.fields as TemplateManifest['fields'],
    defaultTokens: tokens as TemplateManifest['defaultTokens'],
  };
}
