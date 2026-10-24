/**
 * Field value coercion and validation for `documents:update-field`.
 * Unknown keys are rejected; values are coerced/validated per field type:
 * text / number / date / list (with nested item schemas).
 */
import type {
  ListItemFieldDef,
  TemplateFieldDef,
  TemplateManifest,
  ThemeTokens,
  TokenUpdate,
} from '../../shared/types';

export class DtfError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'DtfError';
    this.code = code;
  }
}

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

function fail(code: string, message: string): never {
  throw new DtfError(code, message);
}

function checkNumberBounds(
  key: string,
  n: number,
  field: { min?: number; max?: number },
): void {
  if (field.min !== undefined && n < field.min) {
    fail('FIELD_INVALID', `Field "${key}" must be >= ${field.min}.`);
  }
  if (field.max !== undefined && n > field.max) {
    fail('FIELD_INVALID', `Field "${key}" must be <= ${field.max}.`);
  }
}

function coerceNumber(key: string, value: unknown): number {
  let n: number;
  if (typeof value === 'number') {
    n = value;
  } else if (typeof value === 'string' && value.trim() !== '') {
    n = Number(value);
  } else {
    fail('FIELD_INVALID', `Field "${key}" must be a number.`);
  }
  if (!Number.isFinite(n)) {
    fail('FIELD_INVALID', `Field "${key}" must be a finite number.`);
  }
  return n;
}

function coerceItemValue(
  def: ListItemFieldDef,
  value: unknown,
  path: string,
): unknown {
  switch (def.type) {
    case 'text': {
      if (typeof value !== 'string') {
        fail('FIELD_INVALID', `Item field "${path}" must be a string.`);
      }
      return value as string;
    }
    case 'number': {
      const n = coerceNumber(path, value);
      checkNumberBounds(path, n, def);
      return n;
    }
    case 'date': {
      if (typeof value !== 'string' || !isValidDateString(value)) {
        fail('FIELD_INVALID', `Item field "${path}" must be a YYYY-MM-DD date.`);
      }
      return value as string;
    }
    case 'boolean': {
      if (typeof value !== 'boolean') {
        fail('FIELD_INVALID', `Item field "${path}" must be a boolean.`);
      }
      return value as boolean;
    }
    case 'string-list': {
      if (!Array.isArray(value) || !value.every((v) => typeof v === 'string')) {
        fail('FIELD_INVALID', `Item field "${path}" must be an array of strings.`);
      }
      return [...(value as string[])];
    }
  }
}

function coerceListItem(
  field: TemplateFieldDef,
  raw: unknown,
  index: number,
): Record<string, unknown> {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    fail('FIELD_INVALID', `Item ${index} of "${field.key}" must be an object.`);
  }
  const schema = field.itemSchema ?? [];
  const allowed = new Set(schema.map((s) => s.key));
  const source = raw as Record<string, unknown>;
  for (const key of Object.keys(source)) {
    if (!allowed.has(key)) {
      fail('FIELD_UNKNOWN', `Unknown item key "${key}" in "${field.key}".`);
    }
  }
  const item: Record<string, unknown> = {};
  for (const sub of schema) {
    const path = `${field.key}[${index}].${sub.key}`;
    const value = source[sub.key];
    if (value === undefined || value === null) {
      if (sub.required) {
        fail('FIELD_REQUIRED', `Required item field "${path}" is missing.`);
      }
      item[sub.key] = sub.type === 'string-list' ? [] : sub.type === 'boolean' ? false : '';
      continue;
    }
    item[sub.key] = coerceItemValue(sub, value, path);
  }
  return item;
}

/**
 * Coerce/validate a raw value for a manifest field. Returns the stored
 * value. Throws DtfError with code FIELD_UNKNOWN / FIELD_INVALID /
 * FIELD_REQUIRED on rejection.
 */
export function coerceFieldValue(
  manifest: TemplateManifest,
  key: string,
  value: unknown,
): unknown {
  const field = manifest.fields.find((f) => f.key === key);
  if (!field) {
    fail('FIELD_UNKNOWN', `Unknown field "${key}" for template "${manifest.templateId}".`);
  }
  const f = field as TemplateFieldDef;

  switch (f.type) {
    case 'text': {
      if (value === null || value === undefined) {
        if (f.required) fail('FIELD_REQUIRED', `Field "${key}" is required.`);
        return '';
      }
      if (typeof value === 'string') return value;
      if (typeof value === 'number' || typeof value === 'boolean') {
        return String(value);
      }
      fail('FIELD_INVALID', `Field "${key}" must be text.`);
      break;
    }
    case 'number': {
      const n = coerceNumber(key, value);
      checkNumberBounds(key, n, f);
      return n;
    }
    case 'date': {
      if (typeof value !== 'string' || !isValidDateString(value)) {
        fail('FIELD_INVALID', `Field "${key}" must be a YYYY-MM-DD date.`);
      }
      return value;
    }
    case 'list': {
      if (!Array.isArray(value)) {
        fail('FIELD_INVALID', `Field "${key}" must be an array.`);
      }
      const arr = value as unknown[];
      const minItems = f.required ? (f.minItems ?? 1) : (f.minItems ?? 0);
      if (arr.length < minItems) {
        fail(
          'FIELD_INVALID',
          `Field "${key}" needs at least ${minItems} item(s).`,
        );
      }
      return arr.map((raw, index) => coerceListItem(f, raw, index));
    }
  }
}

const TOKEN_COLOR_KEYS = ['bg', 'text', 'accent'] as const;
const TOKEN_FONT_KEYS = ['headingFont', 'bodyFont'] as const;
const HEX_COLOR_PATTERN = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

/**
 * Validate a partial token update and merge it over the current tokens.
 * Throws DtfError with code TOKEN_INVALID on rejection.
 */
export function mergeTokens(
  current: ThemeTokens,
  update: TokenUpdate,
): ThemeTokens {
  const merged: ThemeTokens = { ...current };
  for (const key of TOKEN_COLOR_KEYS) {
    const value = update[key];
    if (value === undefined) continue;
    if (typeof value !== 'string' || !HEX_COLOR_PATTERN.test(value)) {
      fail(
        'TOKEN_INVALID',
        `Token "${key}" must be a valid #rgb or #rrggbb color.`,
      );
    }
    merged[key] = value;
  }
  for (const key of TOKEN_FONT_KEYS) {
    const value = update[key];
    if (value === undefined) continue;
    if (typeof value !== 'string' || value.trim().length === 0) {
      fail('TOKEN_INVALID', `Token "${key}" must be a non-empty font name.`);
    }
    merged[key] = value;
  }
  if (update.spacing !== undefined) {
    if (
      typeof update.spacing !== 'number' ||
      !Number.isFinite(update.spacing) ||
      update.spacing < 0
    ) {
      fail('TOKEN_INVALID', 'Token "spacing" must be a number >= 0.');
    }
    merged.spacing = update.spacing;
  }
  return merged;
}
