/**
 * Manifest shape tests for all three bundled templates.
 * Uses synthetic fixtures only.
 */
import { describe, expect, it } from 'vitest';
import {
  getBundledManifest,
  listBundledManifests,
} from '../electron/main/templates';
import type { TemplateManifest } from '../shared/types';

function expectValidManifestShape(m: TemplateManifest): void {
  expect(m.manifestVersion).toBe('1.0.0');
  expect(typeof m.templateId).toBe('string');
  expect(m.templateId.length).toBeGreaterThan(0);
  expect(typeof m.name).toBe('string');
  expect(typeof m.description).toBe('string');
  expect(typeof m.version).toBe('string');
  expect(Array.isArray(m.fields)).toBe(true);
  expect(m.fields.length).toBeGreaterThan(0);

  const keys = new Set<string>();
  for (const f of m.fields) {
    expect(typeof f.key).toBe('string');
    expect(typeof f.label).toBe('string');
    expect(['text', 'number', 'date', 'list']).toContain(f.type);
    expect(typeof f.required).toBe('boolean');
    expect(keys.has(f.key)).toBe(false);
    keys.add(f.key);
    if (f.type === 'list') {
      expect(Array.isArray(f.itemSchema)).toBe(true);
    }
  }

  const tokens = m.defaultTokens;
  for (const key of ['bg', 'text', 'accent', 'headingFont', 'bodyFont', 'spacing'] as const) {
    expect(tokens[key]).toBeDefined();
  }
  expect(typeof tokens.spacing).toBe('number');
  expect(Object.isFrozen(m)).toBe(true);
}

describe('bundled template manifests', () => {
  it('ships exactly the three expected templates', () => {
    const ids = listBundledManifests().map((m) => m.templateId).sort();
    expect(ids).toEqual(['checklist-1.0.0', 'invoice-1.0.0', 'weekly-planner-1.0.0']);
  });

  it('invoice manifest has the required fields', () => {
    const m = getBundledManifest('invoice-1.0.0');
    expect(m).toBeDefined();
    expectValidManifestShape(m as TemplateManifest);
    const keys = (m as TemplateManifest).fields.map((f) => f.key);
    expect(keys).toEqual([
      'businessName',
      'clientName',
      'invoiceNumber',
      'issueDate',
      'lineItems',
      'taxRate',
      'notes',
    ]);
    const taxRate = (m as TemplateManifest).fields.find((f) => f.key === 'taxRate');
    expect(taxRate?.min).toBe(0);
    expect(taxRate?.max).toBe(100);
    expect(taxRate?.default).toBe(0);
    const lineItems = (m as TemplateManifest).fields.find((f) => f.key === 'lineItems');
    expect(lineItems?.minItems).toBe(1);
  });

  it('weekly planner manifest prefills seven days', () => {
    const m = getBundledManifest('weekly-planner-1.0.0') as TemplateManifest;
    expectValidManifestShape(m);
    const days = m.fields.find((f) => f.key === 'days');
    expect(days?.minItems).toBe(7);
    const prefill = days?.prefill as Array<{ name: string; tasks: string[] }>;
    expect(prefill.map((d) => d.name)).toEqual([
      'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
    ]);
  });

  it('checklist manifest requires at least one item', () => {
    const m = getBundledManifest('checklist-1.0.0') as TemplateManifest;
    expectValidManifestShape(m);
    const items = m.fields.find((f) => f.key === 'items');
    expect(items?.required).toBe(true);
    expect(items?.minItems).toBe(1);
  });

  it('returns undefined for unknown template ids', () => {
    expect(getBundledManifest('nope-9.9.9')).toBeUndefined();
  });
});
