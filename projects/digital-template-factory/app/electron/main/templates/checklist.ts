/**
 * Checklist template — original design authored for this project.
 */
import type { TemplateManifest } from '../../../shared/types';

function deepFreeze<T>(obj: T): T {
  if (obj !== null && typeof obj === 'object' && !Object.isFrozen(obj)) {
    for (const value of Object.values(obj as Record<string, unknown>)) {
      deepFreeze(value);
    }
    Object.freeze(obj);
  }
  return obj;
}

export const checklistManifest: TemplateManifest = deepFreeze({
  manifestVersion: '1.0.0',
  templateId: 'checklist-1.0.0',
  name: 'Checklist',
  description: 'A printable checklist with checkable items and a footer note.',
  version: '1.0.0',
  fields: [
    { key: 'title', label: 'Title', type: 'text', required: true },
    {
      key: 'items',
      label: 'Items',
      type: 'list',
      required: true,
      minItems: 1,
      itemSchema: [
        { key: 'label', label: 'Label', type: 'text', required: true },
        { key: 'done', label: 'Done', type: 'boolean', required: false },
      ],
      prefill: [{ label: '', done: false }],
    },
    { key: 'footerNote', label: 'Footer note', type: 'text', required: false },
  ],
  defaultTokens: {
    bg: '#ffffff',
    text: '#1f2937',
    accent: '#b45309',
    headingFont: 'Georgia, serif',
    bodyFont: 'Arial, Helvetica, sans-serif',
    spacing: 12,
  },
} as TemplateManifest);
