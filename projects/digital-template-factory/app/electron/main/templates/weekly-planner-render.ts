/**
 * Weekly planner renderer. Pure and deterministic: identical
 * (data, tokens, format) inputs produce byte-identical HTML.
 * No timestamps. All user values escaped.
 */
import type { ExportFormat, ThemeTokens } from '../../../shared/types';
import { escapeHtml } from '../util/escape';

interface DayEntry {
  name: string;
  tasks: string[];
}

function toDays(value: unknown): DayEntry[] {
  if (!Array.isArray(value)) return [];
  return value.map((raw) => {
    const day = (raw ?? {}) as Record<string, unknown>;
    const tasks = Array.isArray(day.tasks)
      ? day.tasks.filter((x): x is string => typeof x === 'string')
      : [];
    return {
      name: typeof day.name === 'string' ? day.name : '',
      tasks,
    };
  });
}

export function renderWeeklyPlanner(
  data: Record<string, unknown>,
  tokens: ThemeTokens,
  format: ExportFormat,
): string {
  const t = tokens;
  const s = t.spacing;
  const days = toDays(data.days);

  const columns = days
    .map((day) => {
      const taskItems =
        day.tasks.length > 0
          ? day.tasks
              .map((task) => `              <li>${escapeHtml(task)}</li>`)
              .join('\n')
          : `              <li class="empty">&nbsp;</li>`;
      return `        <section class="day">
          <h2>${escapeHtml(day.name)}</h2>
          <ul>
${taskItems}
          </ul>
        </section>`;
    })
    .join('\n');

  const focus =
    typeof data.focusGoal === 'string' && data.focusGoal.length > 0
      ? `      <section class="focus">
        <h2>Focus goal</h2>
        <p>${escapeHtml(data.focusGoal)}</p>
      </section>\n`
      : '';

  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(data.weekTitle)}</title>
    <style>
      * { box-sizing: border-box; }
      body { margin: 0; background: ${t.bg}; color: ${t.text}; font-family: ${t.bodyFont}; }
      main.planner { max-width: 1100px; margin: 0 auto; padding: ${s * 2}px; }
      h1 { font-family: ${t.headingFont}; color: ${t.accent}; margin: 0 0 ${s}px 0; }
      .grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: ${s}px; }
      .day { border: 1px solid ${t.accent}; border-radius: 6px; padding: ${s}px; min-height: 220px; }
      .day h2 { font-family: ${t.headingFont}; font-size: 0.9em; margin: 0 0 ${s / 2}px 0; color: ${t.accent}; }
      .day ul { list-style: square; margin: 0; padding-left: ${s * 1.25}px; font-size: 0.85em; }
      .day li { margin-bottom: ${s / 4}px; }
      .day li.empty { list-style: none; }
      .focus { margin-top: ${s * 1.5}px; border-top: 2px solid ${t.accent}; padding-top: ${s}px; }
      .focus h2 { font-family: ${t.headingFont}; color: ${t.accent}; font-size: 1em; margin: 0 0 ${s / 2}px 0; }
      @media print {
        main.planner { padding: 0; max-width: none; }
        .grid { grid-template-columns: repeat(7, 1fr); }
        @page { size: letter landscape; margin: 12mm; }
      }
    </style>
  </head>
  <body class="format-${format}">
    <main class="planner">
      <h1>${escapeHtml(data.weekTitle)}</h1>
      <div class="grid">
${columns}
      </div>
${focus}    </main>
  </body>
</html>
`;
}
