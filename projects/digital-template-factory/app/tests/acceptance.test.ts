/**
 * MVP acceptance walkthrough — full workflow against the real engine:
 * select template -> create document -> edit data/theme -> export with checks.
 * No mocks: exercises store, validators, renderers, and the export pipeline.
 */
import { describe, expect, it } from 'vitest';
import type { DatabaseSync } from 'node:sqlite';
import { openDatabase } from '../electron/main/db/database';
import {
  createDocument,
  getDocument,
  getTemplate,
  listTemplates,
  updateDocumentField,
  updateDocumentTokens,
} from '../electron/main/store';
import { generateExport, sha256Hex } from '../electron/main/export';

function freshDb(): DatabaseSync {
  return openDatabase(':memory:');
}

describe('MVP acceptance: invoice template end to end', () => {
  it('select template, edit data/theme, export a valid deterministic HTML package', () => {
    const db = freshDb();
    try {
      // 1. Select an original template from the catalog
      const templates = listTemplates(db);
      expect(templates.map((t) => t.templateId)).toContain('invoice-1.0.0');
      const { manifest } = getTemplate(db, 'invoice-1.0.0');
      expect(manifest.manifestVersion).toBe('1.0.0');

      // 2. Create a document and fill its fields (incl. an injection attempt)
      const created = createDocument(db, 'invoice-1.0.0');
      updateDocumentField(
        db,
        created.id,
        'businessName',
        'Acme <img src=x onerror=alert(1)> Supplies',
      );
      updateDocumentField(db, created.id, 'clientName', 'Northwind Traders');
      updateDocumentField(db, created.id, 'invoiceNumber', 'INV-2026-001');
      updateDocumentField(db, created.id, 'issueDate', '2026-10-23');
      updateDocumentField(db, created.id, 'lineItems', [
        { desc: 'Widget A', qty: 10, price: 9.99 },
        { desc: 'Widget B', qty: 2, price: 49.5 },
      ]);
      updateDocumentField(db, created.id, 'taxRate', 5);

      // 3. Edit the theme
      updateDocumentTokens(db, created.id, { accent: '#0f766e', spacing: 20 });

      const doc = getDocument(db, created.id);
      expect(doc.tokens.accent).toBe('#0f766e');

      // 4. Export — all checks must pass
      const first = generateExport({ document: doc, manifest, format: 'html' });
      expect(first.ok).toBe(true);
      expect(first.errors).toEqual([]);
      expect(first.html).toBeDefined();
      // Injection is rendered inert
      expect(first.html).not.toContain('<img src=x onerror=alert(1)>');
      expect(first.html).toContain('&lt;img');
      // Accessible, structural output
      expect(first.html).toContain('<main');
      expect(first.html).not.toContain('<script');
      // Line items and totals present
      expect(first.html).toContain('Northwind Traders');
      expect(first.html).toContain('INV-2026-001');

      // 5. License record + content hash
      expect(first.licenseRecord).toBeDefined();
      expect(first.licenseRecord!.templateId).toBe('invoice-1.0.0');
      expect(first.licenseRecord!.manifestVersion).toBe('1.0.0');
      expect(first.licenseRecord!.contentHash).toBe(sha256Hex(first.html!));
      expect(first.licenseRecord!.format).toBe('html');

      // 6. Deterministic: identical inputs -> byte-identical output + hash
      const second = generateExport({ document: doc, manifest, format: 'html' });
      expect(second.ok).toBe(true);
      expect(second.html).toBe(first.html);
      expect(second.licenseRecord!.contentHash).toBe(first.licenseRecord!.contentHash);
    } finally {
      db.close();
    }
  });

  it('blocks export when required fields are missing, with named errors', () => {
    const db = freshDb();
    try {
      const { manifest } = getTemplate(db, 'checklist-1.0.0');
      const created = createDocument(db, 'checklist-1.0.0');
      const doc = getDocument(db, created.id);
      const result = generateExport({ document: doc, manifest, format: 'html' });
      expect(result.ok).toBe(false);
      expect(result.errors.some((e) => e.startsWith('FIELD_REQUIRED:'))).toBe(true);
    } finally {
      db.close();
    }
  });

  it('blocks export when theme contrast fails WCAG AA', () => {
    const db = freshDb();
    try {
      const { manifest } = getTemplate(db, 'checklist-1.0.0');
      const created = createDocument(db, 'checklist-1.0.0');
      updateDocumentField(db, created.id, 'title', 'Groceries');
      updateDocumentField(db, created.id, 'items', [{ label: 'Milk', done: false }]);
      // Near-identical foreground/background -> contrast failure
      updateDocumentTokens(db, created.id, { text: '#fefefe' });
      const doc = getDocument(db, created.id);
      const result = generateExport({ document: doc, manifest, format: 'html' });
      expect(result.ok).toBe(false);
      expect(result.errors.some((e) => e.startsWith('CONTRAST_FAIL:'))).toBe(true);
    } finally {
      db.close();
    }
  });
});
