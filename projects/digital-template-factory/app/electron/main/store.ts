/**
 * Persistence for imported templates and documents (node:sqlite).
 * All writes run inside explicit transactions. Bundled templates are
 * code, not rows — `templates` rows are imports only.
 */
import type { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import type {
  DocumentRecord,
  DocumentSummary,
  TemplateManifest,
  TemplateSource,
  TemplateSummary,
  ThemeTokens,
  TokenUpdate,
} from '../../shared/types';
import {
  defaultDataForManifest,
  getBundledManifest,
  isBundledTemplate,
  listBundledManifests,
} from './templates';
import { withTransaction } from './db/database';
import { DtfError, coerceFieldValue, mergeTokens } from './validation';
import { parseTemplateBundle } from './template-import';

function summarize(manifest: TemplateManifest, source: TemplateSource): TemplateSummary {
  return {
    templateId: manifest.templateId,
    name: manifest.name,
    description: manifest.description,
    version: manifest.version,
    fieldCount: manifest.fields.length,
    source,
  };
}

interface TemplateRow {
  id: string;
  manifest_version: string;
  name: string;
  version: string;
  manifest_json: string;
  source: string;
  created_at: string;
}

interface DocumentRow {
  id: string;
  template_id: string;
  data_json: string;
  tokens_json: string;
  version: number;
  updated_at: string;
}

function rowToDocument(row: DocumentRow): DocumentRecord {
  return {
    id: row.id,
    templateId: row.template_id,
    data: JSON.parse(row.data_json) as Record<string, unknown>,
    tokens: JSON.parse(row.tokens_json) as ThemeTokens,
    version: row.version,
    updatedAt: row.updated_at,
  };
}

/** Bundled + imported template summaries. */
export function listTemplates(db: DatabaseSync): TemplateSummary[] {
  const bundled = listBundledManifests().map((m) => summarize(m, 'bundled'));
  const rows = db
    .prepare('SELECT * FROM templates ORDER BY created_at ASC')
    .all() as unknown as TemplateRow[];
  const imported = rows.map((row) => {
    const manifest = JSON.parse(row.manifest_json) as TemplateManifest;
    return summarize(manifest, 'imported');
  });
  return [...bundled, ...imported];
}

export interface ResolvedTemplate {
  manifest: TemplateManifest;
  source: TemplateSource;
}

/** Resolve a full manifest by id, from bundled code or the import table. */
export function getTemplate(db: DatabaseSync, templateId: string): ResolvedTemplate {
  const bundled = getBundledManifest(templateId);
  if (bundled) return { manifest: bundled, source: 'bundled' };
  const row = db.prepare('SELECT * FROM templates WHERE id = ?').get(templateId) as
    | TemplateRow
    | undefined;
  if (!row) {
    throw new DtfError('TEMPLATE_NOT_FOUND', `Template "${templateId}" not found.`);
  }
  return {
    manifest: JSON.parse(row.manifest_json) as TemplateManifest,
    source: 'imported',
  };
}

/**
 * Validate and persist an external template bundle.
 * Rejects bundled-id collisions and re-imports of the same id.
 */
export function importTemplate(db: DatabaseSync, bundleJson: string): TemplateSummary {
  const manifest = parseTemplateBundle(bundleJson);
  if (isBundledTemplate(manifest.templateId)) {
    throw new DtfError(
      'TEMPLATE_INVALID',
      `Template id "${manifest.templateId}" collides with a bundled template.`,
    );
  }
  return withTransaction(db, () => {
    const existing = db
      .prepare('SELECT id FROM templates WHERE id = ?')
      .get(manifest.templateId) as { id: string } | undefined;
    if (existing) {
      throw new DtfError(
        'TEMPLATE_INVALID',
        `Template "${manifest.templateId}" is already imported.`,
      );
    }
    db.prepare(
      `INSERT INTO templates
         (id, manifest_version, name, version, manifest_json, source, created_at)
       VALUES (?, ?, ?, ?, ?, 'imported', ?)`,
    ).run(
      manifest.templateId,
      manifest.manifestVersion,
      manifest.name,
      manifest.version,
      JSON.stringify(manifest),
      new Date().toISOString(),
    );
    return summarize(manifest, 'imported');
  });
}

/** Create a document from a template's defaults. */
export function createDocument(db: DatabaseSync, templateId: string): DocumentRecord {
  const { manifest } = getTemplate(db, templateId);
  const now = new Date().toISOString();
  const doc: DocumentRecord = {
    id: randomUUID(),
    templateId: manifest.templateId,
    data: defaultDataForManifest(manifest),
    tokens: structuredClone(manifest.defaultTokens),
    version: 1,
    updatedAt: now,
  };
  withTransaction(db, () => {
    db.prepare(
      `INSERT INTO documents (id, template_id, data_json, tokens_json, version, updated_at)
       VALUES (?, ?, ?, ?, ?, ?)`,
    ).run(
      doc.id,
      doc.templateId,
      JSON.stringify(doc.data),
      JSON.stringify(doc.tokens),
      doc.version,
      doc.updatedAt,
    );
  });
  return doc;
}

/**
 * Summaries of every persisted document, newest first. This is the
 * authoritative document index: the renderer's local recent-documents
 * cache must never be the only way to reach a stored document.
 */
export function listDocuments(db: DatabaseSync): DocumentSummary[] {
  const rows = db
    .prepare('SELECT * FROM documents ORDER BY updated_at DESC')
    .all() as unknown as DocumentRow[];
  return rows.map((row) => {
    let templateName = row.template_id;
    try {
      templateName = getTemplate(db, row.template_id).manifest.name;
    } catch {
      // Template row missing (should not happen): fall back to its id so
      // the document itself stays reachable from the UI.
    }
    return {
      id: row.id,
      templateId: row.template_id,
      templateName,
      updatedAt: row.updated_at,
    };
  });
}

/** Load a document by id. */
export function getDocument(db: DatabaseSync, id: string): DocumentRecord {
  const row = db.prepare('SELECT * FROM documents WHERE id = ?').get(id) as
    | DocumentRow
    | undefined;
  if (!row) {
    throw new DtfError('DOCUMENT_NOT_FOUND', `Document "${id}" not found.`);
  }
  return rowToDocument(row);
}

function saveDocument(db: DatabaseSync, doc: DocumentRecord): void {
  db.prepare(
    `UPDATE documents
       SET data_json = ?, tokens_json = ?, version = ?, updated_at = ?
     WHERE id = ?`,
  ).run(
    JSON.stringify(doc.data),
    JSON.stringify(doc.tokens),
    doc.version,
    doc.updatedAt,
    doc.id,
  );
}

/** Validate + set one field on a document. */
export function updateDocumentField(
  db: DatabaseSync,
  id: string,
  key: string,
  value: unknown,
): DocumentRecord {
  return withTransaction(db, () => {
    const doc = getDocument(db, id);
    const { manifest } = getTemplate(db, doc.templateId);
    const coerced = coerceFieldValue(manifest, key, value);
    doc.data = { ...doc.data, [key]: coerced };
    doc.version += 1;
    doc.updatedAt = new Date().toISOString();
    saveDocument(db, doc);
    return doc;
  });
}

/** Validate + merge theme tokens on a document. */
export function updateDocumentTokens(
  db: DatabaseSync,
  id: string,
  tokens: TokenUpdate,
): DocumentRecord {
  return withTransaction(db, () => {
    const doc = getDocument(db, id);
    doc.tokens = mergeTokens(doc.tokens, tokens);
    doc.version += 1;
    doc.updatedAt = new Date().toISOString();
    saveDocument(db, doc);
    return doc;
  });
}

/** Delete a document. Returns true when a row was removed. */
export function deleteDocument(db: DatabaseSync, id: string): boolean {
  return withTransaction(db, () => {
    const result = db.prepare('DELETE FROM documents WHERE id = ?').run(id);
    return result.changes > 0;
  });
}
