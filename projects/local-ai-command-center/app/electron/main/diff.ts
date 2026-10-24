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

/** Maximum LCS matrix cells (old-middle-lines x new-middle-lines). */
export const MAX_DIFF_CELLS = 1_000_000;

function splitLines(content: string | null): string[] {
  if (content === null || content === '') return [];
  const lines = content.split('\n');
  if (lines.length > 0 && lines[lines.length - 1] === '') lines.pop();
  return lines;
}

export function createDiff(relativePath: string, oldContent: string | null, newContent: string): string {
  const header = [`--- a/${relativePath}`, `+++ b/${relativePath}`];
  const oldLines = splitLines(oldContent);
  const newLines = splitLines(newContent);
  if (oldLines.join('\n') === newLines.join('\n') && (oldContent ?? '') === newContent) {
    return header.join('\n') + '\n';
  }

  // Trim the common prefix/suffix: those lines appear verbatim as context.
  let start = 0;
  while (start < oldLines.length && start < newLines.length && oldLines[start] === newLines[start]) {
    start++;
  }
  let oldEnd = oldLines.length;
  let newEnd = newLines.length;
  while (oldEnd > start && newEnd > start && oldLines[oldEnd - 1] === newLines[newEnd - 1]) {
    oldEnd--;
    newEnd--;
  }
  const prefix = oldLines.slice(0, start).map((l) => ` ${l}`);
  const suffix = oldLines.slice(oldEnd).map((l) => ` ${l}`);
  const oldMid = oldLines.slice(start, oldEnd);
  const newMid = newLines.slice(start, newEnd);

  const oldCount = oldLines.length; const newCount = newLines.length;
  const hunkHeader = `@@ -${oldCount === 0 ? 0 : 1},${oldCount} +${newCount === 0 ? 0 : 1},${newCount} @@`;

  let midBody: string[];
  if (oldMid.length * newMid.length > MAX_DIFF_CELLS) {
    // Bounded fallback: linear time/memory, no matrix allocation.
    midBody = [
      ...oldMid.map((l) => `-${l}`),
      ...newMid.map((l) => `+${l}`),
      `\\ Diff simplified: changed section is ${oldMid.length} x ${newMid.length} lines, above the exact-diff limit; shown as a full replacement.`,
    ];
  } else {
    // LCS DP over the differing middle only.
    const n = oldMid.length; const m = newMid.length;
    const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        dp[i]![j] = oldMid[i] === newMid[j] ? dp[i + 1]![j + 1]! + 1 : Math.max(dp[i + 1]![j]!, dp[i]![j + 1]!);
      }
    }
    midBody = [];
    let i = 0; let j = 0;
    while (i < n && j < m) {
      if (oldMid[i] === newMid[j]) { midBody.push(` ${oldMid[i]}`); i++; j++; }
      else if (dp[i + 1]![j]! >= dp[i]![j + 1]!) { midBody.push(`-${oldMid[i]}`); i++; }
      else { midBody.push(`+${newMid[j]}`); j++; }
    }
    while (i < n) { midBody.push(`-${oldMid[i]}`); i++; }
    while (j < m) { midBody.push(`+${newMid[j]}`); j++; }
  }

  return [...header, hunkHeader, ...prefix, ...midBody, ...suffix].join('\n') + '\n';
}
export const computeDiff = createDiff;
export const unifiedDiff = createDiff;
