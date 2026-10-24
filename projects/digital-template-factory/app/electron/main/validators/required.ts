/**
 * Required-field validation. Walks a manifest's field schema (including
 * nested list item schemas) and returns the keys of missing required
 * values. Nested misses use dotted paths, e.g. `lineItems[0].desc`.
 */
import type {
  ListItemFieldDef,
  TemplateFieldDef,
  TemplateManifest,
} from '../../../shared/types';

function isBlank(value: unknown): boolean {
  if (value === undefined || value === null) return true;
  if (typeof value === 'string') return value.trim().length === 0;
  if (typeof value === 'number') return Number.isNaN(value);
  return false;
}

function coerceNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return undefined;
}

function checkItemValue(
  def: ListItemFieldDef,
  value: unknown,
): boolean {
  switch (def.type) {
    case 'text':
      return !isBlank(value);
    case 'number':
      return coerceNumber(value) !== undefined;
    case 'date':
      return typeof value === 'string' && value.trim().length > 0;
    case 'boolean':
      return typeof value === 'boolean';
    case 'string-list':
      return Array.isArray(value);
  }
}

function checkList(
  field: TemplateFieldDef,
  value: unknown,
  missing: string[],
): void {
  if (!Array.isArray(value)) {
    missing.push(field.key);
    return;
  }
  const minItems = field.minItems ?? 1;
  if (value.length < minItems) {
    missing.push(field.key);
    return;
  }
  const schema = field.itemSchema ?? [];
  value.forEach((rawItem, index) => {
    const item =
      rawItem !== null && typeof rawItem === 'object'
        ? (rawItem as Record<string, unknown>)
        : {};
    for (const sub of schema) {
      if (sub.required && !checkItemValue(sub, item[sub.key])) {
        missing.push(`${field.key}[${index}].${sub.key}`);
      }
    }
  });
}

function checkField(
  field: TemplateFieldDef,
  value: unknown,
  missing: string[],
): void {
  if (!field.required) return;
  switch (field.type) {
    case 'list':
      checkList(field, value, missing);
      return;
    case 'number': {
      if (coerceNumber(value) === undefined) missing.push(field.key);
      return;
    }
    default:
      if (isBlank(value)) missing.push(field.key);
  }
}

/**
 * Returns the list of missing required field keys for the given document
 * data. Empty array means every required field is satisfied.
 */
export function validateRequiredFields(
  manifest: TemplateManifest,
  data: Record<string, unknown>,
): string[] {
  const missing: string[] = [];
  for (const field of manifest.fields) {
    checkField(field, data[field.key], missing);
  }
  return missing;
}
