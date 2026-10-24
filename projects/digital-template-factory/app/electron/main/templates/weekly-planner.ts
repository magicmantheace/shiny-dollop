/**
 * Weekly planner template — original design authored for this project.
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

const DAY_NAMES = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
] as const;

export const weeklyPlannerManifest: TemplateManifest = deepFreeze({
  manifestVersion: '1.0.0',
  templateId: 'weekly-planner-1.0.0',
  name: 'Weekly Planner Page',
  description:
    'A one-page weekly planner with seven day columns and a focus goal.',
  version: '1.0.0',
  fields: [
    { key: 'weekTitle', label: 'Week title', type: 'text', required: true },
    {
      key: 'days',
      label: 'Days',
      type: 'list',
      required: true,
      minItems: 7,
      itemSchema: [
        { key: 'name', label: 'Day name', type: 'text', required: true },
        { key: 'tasks', label: 'Tasks', type: 'string-list', required: false },
      ],
      prefill: DAY_NAMES.map((name) => ({ name, tasks: [] as string[] })),
    },
    { key: 'focusGoal', label: 'Focus goal', type: 'text', required: false },
  ],
  defaultTokens: {
    bg: '#fdfbf7',
    text: '#222222',
    accent: '#0f766e',
    headingFont: 'Georgia, serif',
    bodyFont: 'Arial, Helvetica, sans-serif',
    spacing: 14,
  },
} as TemplateManifest);
