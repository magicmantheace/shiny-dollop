/**
 * System font stacks offered by the design-token editor.
 *
 * Only OS-bundled stacks are used: no webfonts, no downloads, fully offline.
 */
export interface FontStackOption {
  label: string;
  value: string;
}

export const FONT_STACKS: readonly FontStackOption[] = [
  {
    label: 'System UI',
    value: "system-ui, -apple-system, 'Segoe UI', sans-serif",
  },
  {
    label: 'Arial / Helvetica',
    value: 'Arial, Helvetica, sans-serif',
  },
  {
    label: 'Verdana',
    value: 'Verdana, Geneva, sans-serif',
  },
  {
    label: 'Georgia serif',
    value: "Georgia, 'Times New Roman', serif",
  },
  {
    label: 'Monospace',
    value: "ui-monospace, 'Cascadia Code', Menlo, Consolas, monospace",
  },
] as const;

export function isKnownFontStack(value: string): boolean {
  return FONT_STACKS.some((s) => s.value === value);
}
