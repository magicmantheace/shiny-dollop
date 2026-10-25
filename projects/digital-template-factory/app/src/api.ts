/**
 * Thin typed wrapper around `window.dtf` (the preload IPC bridge).
 *
 * Every renderer component talks to the backend through this module, never
 * through `window` directly. The wrapper adds no logic beyond null-checking
 * the bridge and forwarding calls; validation and persistence live in the
 * backend (Worker A).
 */
import type {
  DocumentRecord,
  DocumentSummary,
  DtfApi,
  ExportFormat,
  ExportResult,
  TemplateManifest,
  TemplateSummary,
  ThemeTokens,
  TokenUpdate,
} from '../shared/types';

function bridge(): DtfApi {
  const api = window.dtf;
  if (!api) {
    throw new Error(
      'DTF backend bridge (window.dtf) is not available. ' +
        'This UI must run inside the Electron app shell.',
    );
  }
  return api;
}

export const api = {
  listTemplates(): Promise<TemplateSummary[]> {
    return bridge().templates.list();
  },
  getTemplate(templateId: string): Promise<TemplateManifest> {
    return bridge().templates.get({ templateId });
  },
  importTemplate(bundleJson: string): Promise<TemplateSummary> {
    return bridge().templates.import({ bundleJson });
  },
  listDocuments(): Promise<DocumentSummary[]> {
    return bridge().documents.list();
  },
  createDocument(templateId: string): Promise<DocumentRecord> {
    return bridge().documents.create({ templateId });
  },
  getDocument(id: string): Promise<DocumentRecord> {
    return bridge().documents.get({ id });
  },
  updateField(id: string, key: string, value: unknown): Promise<DocumentRecord> {
    return bridge().documents.updateField({ id, key, value });
  },
  updateTokens(id: string, tokens: TokenUpdate): Promise<DocumentRecord> {
    return bridge().documents.updateTokens({ id, tokens });
  },
  deleteDocument(id: string): Promise<{ deleted: boolean }> {
    return bridge().documents.delete({ id });
  },
  generateExport(id: string, format: ExportFormat): Promise<ExportResult> {
    return bridge().export.generate({ id, format });
  },
  saveExport(
    html: string,
    suggestedName: string,
  ): Promise<{ canceled: boolean; filePath?: string }> {
    return bridge().export.save({ html, suggestedName });
  },
};

/** Render a thrown backend failure as plain text (shown verbatim in UI). */
export function errorText(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
