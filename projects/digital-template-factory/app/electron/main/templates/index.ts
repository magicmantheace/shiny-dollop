/**
 * Template registry: the three bundled manifests, render dispatch,
 * and default document data derived from a manifest's field schema.
 */
import type {
  ExportFormat,
  TemplateFieldDef,
  TemplateManifest,
  ThemeTokens,
} from '../../../shared/types';
import { invoiceManifest } from './invoice';
import { weeklyPlannerManifest } from './weekly-planner';
import { checklistManifest } from './checklist';
import { renderInvoice } from './invoice-render';
import { renderWeeklyPlanner } from './weekly-planner-render';
import { renderChecklist } from './checklist-render';

const BUNDLED: TemplateManifest[] = [
  invoiceManifest,
  weeklyPlannerManifest,
  checklistManifest,
];

const BUNDLED_BY_ID = new Map<string, TemplateManifest>(
  BUNDLED.map((m) => [m.templateId, m]),
);

export function listBundledManifests(): TemplateManifest[] {
  return [...BUNDLED];
}

export function getBundledManifest(templateId: string): TemplateManifest | undefined {
  return BUNDLED_BY_ID.get(templateId);
}

export function isBundledTemplate(templateId: string): boolean {
  return BUNDLED_BY_ID.has(templateId);
}

type RenderFn = (
  data: Record<string, unknown>,
  tokens: ThemeTokens,
  format: ExportFormat,
) => string;

const RENDERERS: Record<string, RenderFn> = {
  'invoice-1.0.0': renderInvoice,
  'weekly-planner-1.0.0': renderWeeklyPlanner,
  'checklist-1.0.0': renderChecklist,
};

/**
 * Render a bundled template. Returns undefined for template ids without
 * a renderer (e.g. imported external templates) — callers turn that into
 * a TEMPLATE_RENDER_UNSUPPORTED export error.
 */
export function renderBundledTemplate(
  templateId: string,
  data: Record<string, unknown>,
  tokens: ThemeTokens,
  format: ExportFormat,
): string | undefined {
  const render = RENDERERS[templateId];
  return render ? render(data, tokens, format) : undefined;
}

function defaultValueForField(field: TemplateFieldDef): unknown {
  if (field.default !== undefined) {
    return structuredClone(field.default);
  }
  switch (field.type) {
    case 'text':
      return '';
    case 'number':
      return 0;
    case 'date':
      return '';
    case 'list':
      return field.prefill !== undefined
        ? structuredClone(field.prefill)
        : [];
  }
}

/** Build the initial `data` object for a new document from a manifest. */
export function defaultDataForManifest(
  manifest: TemplateManifest,
): Record<string, unknown> {
  const data: Record<string, unknown> = {};
  for (const field of manifest.fields) {
    data[field.key] = defaultValueForField(field);
  }
  return data;
}
