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
const TOKEN_KEYS = ['bg', 'text', 'accent', 'headingFont', 'bodyFont', 'spacing'] as const;
const HEX_COLOR_PATTERN = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

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
      if (entry.itemSchema !== undefined && !Array.isArray(entry.itemSchema)) {
        invalid(`Field "${key}" "itemSchema" must be an array.`);
      }
      if (entry.minItems !== undefined && typeof entry.minItems !== 'number') {
        invalid(`Field "${key}" "minItems" must be a number.`);
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
