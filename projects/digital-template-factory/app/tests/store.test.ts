/**
 * Store (SQLite persistence) tests. Uses :memory: databases plus one
 * temp-file database to prove imported templates survive a restart.
 */
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import type { DatabaseSync } from 'node:sqlite';
import { openDatabase } from '../electron/main/db/database';
import {
  createDocument,
  deleteDocument,
  getDocument,
  getTemplate,
  importTemplate,
  listDocuments,
  listTemplates,
  updateDocumentField,
  updateDocumentTokens,
} from '../electron/main/store';
import { DtfError } from '../electron/main/validation';

const dbs: DatabaseSync[] = [];
const tmpDirs: string[] = [];

afterEach(() => {
  for (const db of dbs.splice(0)) {
    try {
      db.close();
    } catch {
      // ignore close errors in teardown
    }
  }
  for (const dir of tmpDirs.splice(0)) {
    rmSync(dir, { recursive: true, force: true });
  }
});

function memoryDb(): DatabaseSync {
  const db = openDatabase(':memory:');
  dbs.push(db);
  return db;
}

function fileDb(): { db: DatabaseSync; path: string; dir: string } {
  const dir = mkdtempSync(join(tmpdir(), 'dtf-test-'));
  tmpDirs.push(dir);
  const path = join(dir, 'test.db');
  const db = openDatabase(path);
  dbs.push(db);
  return { db, path, dir };
}

function externalBundle(): string {
  return JSON.stringify({
    manifestVersion: '1.0.0',
    templateId: 'external-note-1.0.0',
    name: 'External Note',
    description: 'Imported note template.',
    version: '1.0.0',
    fields: [{ key: 'body', label: 'Body', type: 'text', required: true }],
    defaultTokens: {
      bg: '#ffffff',
      text: '#111111',
      accent: '#0f766e',
      headingFont: 'Georgia, serif',
      bodyFont: 'Arial, sans-serif',
      spacing: 10,
    },
  });
}

describe('template listing', () => {
  it('lists bundled templates with a bundled source flag', () => {
    const summaries = listTemplates(memoryDb());
    expect(summaries).toHaveLength(3);
    for (const s of summaries) {
      expect(s.source).toBe('bundled');
      expect(s.fieldCount).toBeGreaterThan(0);
    }
  });

  it('lists imported templates alongside bundled ones', () => {
    const db = memoryDb();
    importTemplate(db, externalBundle());
    const summaries = listTemplates(db);
    expect(summaries).toHaveLength(4);
    const imported = summaries.find((s) => s.templateId === 'external-note-1.0.0');
    expect(imported?.source).toBe('imported');
    expect(imported?.name).toBe('External Note');
  });

  it('imported templates survive a database restart', () => {
    const { db, path } = fileDb();
    importTemplate(db, externalBundle());
    db.close();
    dbs.splice(dbs.indexOf(db), 1);

    const reopened = openDatabase(path);
    dbs.push(reopened);
    const summaries = listTemplates(reopened);
    expect(summaries.map((s) => s.templateId)).toContain('external-note-1.0.0');
    // And the full manifest resolves after restart too.
    expect(getTemplate(reopened, 'external-note-1.0.0').source).toBe('imported');
  });

  it('rejects importing a bundle that collides with a bundled id', () => {
    const db = memoryDb();
    const raw = JSON.parse(externalBundle());
    raw.templateId = 'invoice-1.0.0';
    expect(() => importTemplate(db, JSON.stringify(raw))).toThrow(DtfError);
  });

  it('rejects importing the same id twice', () => {
    const db = memoryDb();
    importTemplate(db, externalBundle());
    expect(() => importTemplate(db, externalBundle())).toThrow(DtfError);
  });
});

function schemalessListBundle(): string {
  return JSON.stringify({
    manifestVersion: '1.0.0',
    templateId: 'external-tags-1.0.0',
    name: 'External Tags',
    description: 'Imported template with a schema-less string list.',
    version: '1.0.0',
    fields: [
      { key: 'title', label: 'Title', type: 'text', required: true },
      {
        key: 'tags',
        label: 'Tags',
        type: 'list',
        required: false,
        minItems: 0,
        prefill: ['First'],
      },
    ],
    defaultTokens: {
      bg: '#ffffff',
      text: '#111111',
      accent: '#0f766e',
      headingFont: 'Georgia, serif',
      bodyFont: 'Arial, sans-serif',
      spacing: 10,
    },
  });
}

describe('documents', () => {
  it('creates a document with manifest defaults', () => {
    const db = memoryDb();
    const doc = createDocument(db, 'invoice-1.0.0');
    expect(doc.templateId).toBe('invoice-1.0.0');
    expect(doc.version).toBe(1);
    expect(doc.data.taxRate).toBe(0);
    expect(doc.data.businessName).toBe('');
    expect(doc.data.lineItems).toEqual([{ desc: '', qty: 1, price: 0 }]);
    expect(doc.tokens).toEqual(getTemplate(db, 'invoice-1.0.0').manifest.defaultTokens);
  });

  it('creates a planner document prefilled with seven days', () => {
    const db = memoryDb();
    const doc = createDocument(db, 'weekly-planner-1.0.0');
    const days = doc.data.days as Array<{ name: string }>;
    expect(days).toHaveLength(7);
    expect(days[0]?.name).toBe('Monday');
  });

  it('round-trips get after create', () => {
    const db = memoryDb();
    const created = createDocument(db, 'checklist-1.0.0');
    const loaded = getDocument(db, created.id);
    expect(loaded).toEqual(created);
  });

  it('updates a text field and bumps the version', () => {
    const db = memoryDb();
    const doc = createDocument(db, 'invoice-1.0.0');
    const updated = updateDocumentField(db, doc.id, 'businessName', 'Acme');
    expect(updated.data.businessName).toBe('Acme');
    expect(updated.version).toBe(2);
  });

  it('coerces numeric strings for number fields', () => {
    const db = memoryDb();
    const doc = createDocument(db, 'invoice-1.0.0');
    const updated = updateDocumentField(db, doc.id, 'taxRate', '7.5');
    expect(updated.data.taxRate).toBe(7.5);
  });

  it('rejects out-of-range numbers', () => {
    const db = memoryDb();
    const doc = createDocument(db, 'invoice-1.0.0');
    expect(() => updateDocumentField(db, doc.id, 'taxRate', 101)).toThrow(DtfError);
  });

  it('rejects malformed dates', () => {
    const db = memoryDb();
    const doc = createDocument(db, 'invoice-1.0.0');
    expect(() => updateDocumentField(db, doc.id, 'issueDate', '2026-13-99')).toThrow(
      DtfError,
    );
    const ok = updateDocumentField(db, doc.id, 'issueDate', '2026-10-23');
    expect(ok.data.issueDate).toBe('2026-10-23');
  });

  it('rejects unknown field keys', () => {
    const db = memoryDb();
    const doc = createDocument(db, 'invoice-1.0.0');
    expect(() => updateDocumentField(db, doc.id, 'hacker', 'x')).toThrow(DtfError);
  });

  it('validates nested list items on update', () => {
    const db = memoryDb();
    const doc = createDocument(db, 'invoice-1.0.0');
    const updated = updateDocumentField(db, doc.id, 'lineItems', [
      { desc: 'Widget', qty: 2, price: 9.99 },
    ]);
    expect(updated.data.lineItems).toEqual([{ desc: 'Widget', qty: 2, price: 9.99 }]);
    expect(() =>
      updateDocumentField(db, doc.id, 'lineItems', [{ desc: 'x', qty: 'many', price: 1 }]),
    ).toThrow(DtfError);
    expect(() => updateDocumentField(db, doc.id, 'lineItems', [])).toThrow(DtfError);
  });

  it('updates and validates tokens', () => {
    const db = memoryDb();
    const doc = createDocument(db, 'invoice-1.0.0');
    const updated = updateDocumentTokens(db, doc.id, { bg: '#fafafa', spacing: 20 });
    expect(updated.tokens.bg).toBe('#fafafa');
    expect(updated.tokens.spacing).toBe(20);
    expect(updated.version).toBe(2);
    expect(() => updateDocumentTokens(db, doc.id, { bg: 'red' })).toThrow(DtfError);
    expect(() => updateDocumentTokens(db, doc.id, { spacing: -1 })).toThrow(DtfError);
    expect(() =>
      updateDocumentTokens(db, doc.id, { headingFont: '' }),
    ).toThrow(DtfError);
  });

  it('deletes documents', () => {
    const db = memoryDb();
    const doc = createDocument(db, 'checklist-1.0.0');
    expect(deleteDocument(db, doc.id)).toBe(true);
    expect(deleteDocument(db, doc.id)).toBe(false);
    expect(() => getDocument(db, doc.id)).toThrow(DtfError);
  });

  it('lists all persisted documents with their template names', () => {
    const db = memoryDb();
    const a = createDocument(db, 'invoice-1.0.0');
    const b = createDocument(db, 'checklist-1.0.0');
    const listed = listDocuments(db);
    expect(listed.map((d) => d.id).sort()).toEqual([a.id, b.id].sort());
    const invoice = listed.find((d) => d.id === a.id);
    expect(invoice?.templateId).toBe('invoice-1.0.0');
    expect(invoice?.templateName).toBe(
      getTemplate(db, 'invoice-1.0.0').manifest.name,
    );
    expect(invoice?.updatedAt).toBe(a.updatedAt);
  });

  it('accepts string rows when a list field has no item schema', () => {
    const db = memoryDb();
    importTemplate(db, schemalessListBundle());
    const doc = createDocument(db, 'external-tags-1.0.0');
    // The imported prefill survives document creation as string rows.
    expect(doc.data.tags).toEqual(['First']);
    const updated = updateDocumentField(db, doc.id, 'tags', ['First', 'Second']);
    expect(updated.data.tags).toEqual(['First', 'Second']);
    // Non-string rows are still rejected for a schema-less list.
    expect(() => updateDocumentField(db, doc.id, 'tags', ['First', 42])).toThrow(
      DtfError,
    );
    expect(() =>
      updateDocumentField(db, doc.id, 'tags', [{ label: 'First' }]),
    ).toThrow(DtfError);
  });

  it('throws for unknown template ids and document ids', () => {
    const db = memoryDb();
    expect(() => createDocument(db, 'nope-1.0.0')).toThrow(DtfError);
    expect(() => getDocument(db, 'missing')).toThrow(DtfError);
  });
});
