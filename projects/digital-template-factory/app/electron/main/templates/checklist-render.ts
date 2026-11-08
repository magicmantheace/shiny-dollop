/**
 * Checklist renderer. Pure and deterministic: identical (data, tokens,
 * format) inputs produce byte-identical HTML. No timestamps.
 * All user values escaped.
 */
import type { ExportFormat, ThemeTokens } from '../../../shared/types';
import { escapeHtml } from '../util/escape';

interface ChecklistItem {
  label: string;
  done: boolean;
}

function toItems(value: unknown): ChecklistItem[] {
  if (!Array.isArray(value)) return [];
  return value.map((raw) => {
    const item = (raw ?? {}) as Record<string, unknown>;
    return {
      label: typeof item.label === 'string' ? item.label : '',
      done: item.done === true,
    };
  });
}

export function renderChecklist(
  data: Record<string, unknown>,
  tokens: ThemeTokens,
  format: ExportFormat,
): string {
  const t = tokens;
  const s = t.spacing;
  const items = toItems(data.items);
  const doneCount = items.filter((it) => it.done).length;

  const listItems = items
    .map(
      (it) => `        <li class="${it.done ? 'done' : 'open'}">
          <span class="box" aria-hidden="true">${it.done ? '&#10003;' : ''}</span>
          <span class="label">${escapeHtml(it.label)}</span>
        </li>`,
    )
    .join('\n');

  const footer =
    typeof data.footerNote === 'string' && data.footerNote.length > 0
      ? `      <footer class="checklist-foot">
        <p>${escapeHtml(data.footerNote)}</p>
      </footer>\n`
      : '';

  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(data.title)}</title>
    <style>
      * { box-sizing: border-box; }
      body { margin: 0; background: ${t.bg}; color: ${t.text}; font-family: ${t.bodyFont}; }
      main.checklist { max-width: 640px; margin: 0 auto; padding: ${s * 2}px; }
      h1 { font-family: ${t.headingFont}; color: ${t.accent}; margin: 0 0 ${s / 2}px 0; }
      .progress { font-size: 0.9em; margin-bottom: ${s}px; }
      ul.items { list-style: none; margin: 0; padding: 0; }
      ul.items li { display: flex; align-items: center; gap: ${s / 2}px; padding: ${s / 2}px 0; border-bottom: 1px solid ${t.text}; }
      .box { display: inline-flex; align-items: center; justify-content: center; width: 1.4em; height: 1.4em; border: 2px solid ${t.accent}; border-radius: 4px; color: ${t.accent}; font-weight: bold; flex: none; }
      li.done .label { text-decoration: line-through; opacity: 0.65; }
      .checklist-foot { margin-top: ${s * 1.5}px; font-size: 0.9em; border-top: 2px solid ${t.accent}; padding-top: ${s}px; }
      @media print {
        main.checklist { padding: 0; }
        @page { size: letter; margin: 18mm; }
      }
    </style>
  </head>
  <body class="format-${format}">
    <main class="checklist">
      <h1>${escapeHtml(data.title)}</h1>
      <p class="progress">${escapeHtml(String(doneCount))} of ${escapeHtml(String(items.length))} done</p>
      <ul class="items">
${listItems}
      </ul>
${footer}    </main>
  </body>
</html>
`;
}
