/**
 * Shared types for Digital Product Template Factory.
 * Main, preload and renderer all agree on these shapes.
 */

/** Primitive field kinds supported by template manifests. */
export type FieldType = 'text' | 'number' | 'date' | 'list';

/** Item kinds allowed inside a `list` field's item schema. */
export type ListItemType = 'text' | 'number' | 'date' | 'boolean' | 'string-list';

/** One sub-field of a list item (e.g. a line item's `desc`). */
export interface ListItemFieldDef {
  key: string;
  label: string;
  type: ListItemType;
  required: boolean;
  /** Numeric bounds, only meaningful for type 'number'. */
  min?: number;
  max?: number;
}

/** A single editable field declared by a template manifest. */
export interface TemplateFieldDef {
  key: string;
  label: string;
  type: FieldType;
  required: boolean;
  /** Numeric bounds, only meaningful for type 'number'. */
  min?: number;
  max?: number;
  /** Static default value used when a document is created. */
  default?: unknown;
  /** For type 'list': schema of each item, minimum item count, prefill rows. */
  itemSchema?: ListItemFieldDef[];
  minItems?: number;
  prefill?: unknown[];
}

/** Theme/design tokens attached to every document. */
export interface ThemeTokens {
  bg: string;
  text: string;
  accent: string;
  headingFont: string;
  bodyFont: string;
  spacing: number;
}

/** A versioned, deterministic template manifest. */
export interface TemplateManifest {
  manifestVersion: '1.0.0';
  templateId: string;
  name: string;
  description: string;
  version: string;
  fields: TemplateFieldDef[];
  defaultTokens: ThemeTokens;
}

export type TemplateSource = 'bundled' | 'imported';

/**
 * Partial token update as produced by the zod IPC schema (explicit
 * `| undefined` under exactOptionalPropertyTypes).
 */
export type TokenUpdate = {
  [K in keyof ThemeTokens]?: ThemeTokens[K] | undefined;
};

/** Lightweight manifest summary returned by templates:list. */
export interface TemplateSummary {
  templateId: string;
  name: string;
  description: string;
  version: string;
  fieldCount: number;
  source: TemplateSource;
}

/** Lightweight document summary returned by documents:list. */
export interface DocumentSummary {
  id: string;
  templateId: string;
  templateName: string;
  updatedAt: string;
}

/** A persisted user document (one filled-in template). */
export interface DocumentRecord {
  id: string;
  templateId: string;
  data: Record<string, unknown>;
  tokens: ThemeTokens;
  version: number;
  updatedAt: string;
}

export type ExportFormat = 'html' | 'print';

/** License/provenance record returned with a successful export. */
export interface LicenseRecord {
  templateId: string;
  templateVersion: string;
  manifestVersion: string;
  format: ExportFormat;
  /** sha256 hex of the exact HTML bytes. */
  contentHash: string;
  /** ISO timestamp of the export. Kept OUT of the HTML; never part of the hash. */
  exportedAt: string;
}

export interface ExportResult {
  ok: boolean;
  html?: string;
  errors: string[];
  licenseRecord?: LicenseRecord;
}

/** Named error codes produced by template import. */
export const ImportErrorCodes = {
  versionUnsupported: 'TEMPLATE_VERSION_UNSUPPORTED',
  invalid: 'TEMPLATE_INVALID',
} as const;

export type ImportErrorCode =
  (typeof ImportErrorCodes)[keyof typeof ImportErrorCodes];

/** Flat renderer-facing API exposed as `window.dtf` by the preload script. */
export interface DtfApi {
  templates: {
    list: () => Promise<TemplateSummary[]>;
    get: (input: { templateId: string }) => Promise<TemplateManifest>;
    import: (input: { bundleJson: string }) => Promise<TemplateSummary>;
  };
  documents: {
    list: () => Promise<DocumentSummary[]>;
    create: (input: { templateId: string }) => Promise<DocumentRecord>;
    get: (input: { id: string }) => Promise<DocumentRecord>;
    updateField: (input: {
      id: string;
      key: string;
      value: unknown;
    }) => Promise<DocumentRecord>;
    updateTokens: (input: {
      id: string;
      tokens: TokenUpdate;
    }) => Promise<DocumentRecord>;
    delete: (input: { id: string }) => Promise<{ deleted: boolean }>;
  };
  export: {
    generate: (input: { id: string; format: ExportFormat }) => Promise<ExportResult>;
    save: (input: {
      html: string;
      suggestedName: string;
    }) => Promise<{ canceled: boolean; filePath?: string }>;
  };
}
