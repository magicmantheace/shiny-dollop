// Deterministic LCS-based unified-diff text.
//
// The LCS dynamic-programming matrix is quadratic in the line counts and is
// built synchronously in the main process, so it must be bounded BEFORE
// allocation: two 10,000-line files need ~100M cells and OOM a small heap
// even though both are far below MAX_PROPOSAL_CHARS. Two defences:
//  1. Common leading/trailing lines are trimmed first — they are context in
//     the diff, never part of the changed region — so the matrix only covers
//     the differing middle.
//  2. If the remaining line-count product exceeds MAX_DIFF_CELLS, the diff
//     falls back to a linear "full replacement" rendering of the changed
//     middle (still a valid, reviewable diff) instead of allocating.
//
// End-of-file newline termination is part of a line's identity: the final
// line carries a `noEol` flag when its content does not end with '\n'.
// Without it, 'hello' and 'hello\n' split to identical line arrays and a
// proposal that only adds/removes the final newline rendered as pure
// context — an invisible change in the approval review. Lines with the
// flag render with the standard `\ No newline at end of file` marker, so
// 'hello' -> 'hello\n' shows as -hello / marker / +hello.

/** Maximum LCS matrix cells (old-middle-lines x new-middle-lines). */
export const MAX_DIFF_CELLS = 1_000_000;

/** Standard unified-diff marker rendered after a line whose file side has no trailing newline. */
export const NO_NEWLINE_MARKER = '\\ No newline at end of file';

interface DiffLine {
  text: string;
  /** True only for the final line when the content does not end with '\n'. */
  noEol: boolean;
}

function splitLines(content: string | null): DiffLine[] {
  if (content === null || content === '') return [];
  const raw = content.split('\n');
  const terminated = raw[raw.length - 1] === '';
  if (terminated) raw.pop();
  return raw.map((text, index) => ({ text, noEol: index === raw.length - 1 && !terminated }));
}

function sameLine(a: DiffLine, b: DiffLine): boolean {
  return a.text === b.text && a.noEol === b.noEol;
}

function renderLine(out: string[], sign: string, line: DiffLine): void {
  out.push(`${sign}${line.text}`);
  if (line.noEol) out.push(NO_NEWLINE_MARKER);
}

function renderAll(sign: string, lines: DiffLine[]): string[] {
  const out: string[] = [];
  for (const line of lines) renderLine(out, sign, line);
  return out;
}

export function createDiff(relativePath: string, oldContent: string | null, newContent: string): string {
  const header = [`--- a/${relativePath}`, `+++ b/${relativePath}`];
  const oldLines = splitLines(oldContent);
  const newLines = splitLines(newContent);
  if ((oldContent ?? '') === newContent) {
    return header.join('\n') + '\n';
  }

  // Trim the common prefix/suffix: those lines appear verbatim as context.
  // Termination counts, so a final line whose newline status changed is
  // never trimmed into context — it falls into the changed middle.
  let start = 0;
  while (start < oldLines.length && start < newLines.length && sameLine(oldLines[start]!, newLines[start]!)) {
    start++;
  }
  let oldEnd = oldLines.length;
  let newEnd = newLines.length;
  while (oldEnd > start && newEnd > start && sameLine(oldLines[oldEnd - 1]!, newLines[newEnd - 1]!)) {
    oldEnd--;
    newEnd--;
  }
  const prefix = renderAll(' ', oldLines.slice(0, start));
  const suffix = renderAll(' ', oldLines.slice(oldEnd));
  const oldMid = oldLines.slice(start, oldEnd);
  const newMid = newLines.slice(start, newEnd);

  const oldCount = oldLines.length; const newCount = newLines.length;
  const hunkHeader = `@@ -${oldCount === 0 ? 0 : 1},${oldCount} +${newCount === 0 ? 0 : 1},${newCount} @@`;

  let midBody: string[];
  if (oldMid.length * newMid.length > MAX_DIFF_CELLS) {
    // Bounded fallback: linear time/memory, no matrix allocation.
    midBody = [
      ...renderAll('-', oldMid),
      ...renderAll('+', newMid),
      `\\ Diff simplified: changed section is ${oldMid.length} x ${newMid.length} lines, above the exact-diff limit; shown as a full replacement.`,
    ];
  } else {
    // LCS DP over the differing middle only.
    const n = oldMid.length; const m = newMid.length;
    const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        dp[i]![j] = sameLine(oldMid[i]!, newMid[j]!) ? dp[i + 1]![j + 1]! + 1 : Math.max(dp[i + 1]![j]!, dp[i]![j + 1]!);
      }
    }
    midBody = [];
    let i = 0; let j = 0;
    while (i < n && j < m) {
      if (sameLine(oldMid[i]!, newMid[j]!)) { renderLine(midBody, ' ', oldMid[i]!); i++; j++; }
      else if (dp[i + 1]![j]! >= dp[i]![j + 1]!) { renderLine(midBody, '-', oldMid[i]!); i++; }
      else { renderLine(midBody, '+', newMid[j]!); j++; }
    }
    while (i < n) { renderLine(midBody, '-', oldMid[i]!); i++; }
    while (j < m) { renderLine(midBody, '+', newMid[j]!); j++; }
  }

  return [...header, hunkHeader, ...prefix, ...midBody, ...suffix].join('\n') + '\n';
}
export const computeDiff = createDiff;
export const unifiedDiff = createDiff;
