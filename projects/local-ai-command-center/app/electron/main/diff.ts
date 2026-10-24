// Deterministic LCS-based unified-diff text.
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
  // LCS DP
  const n = oldLines.length; const m = newLines.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i]![j] = oldLines[i] === newLines[j] ? dp[i + 1]![j + 1]! + 1 : Math.max(dp[i + 1]![j]!, dp[i]![j + 1]!);
    }
  }
  const body: string[] = [];
  let i = 0; let j = 0;
  while (i < n && j < m) {
    if (oldLines[i] === newLines[j]) { body.push(` ${oldLines[i]}`); i++; j++; }
    else if (dp[i + 1]![j]! >= dp[i]![j + 1]!) { body.push(`-${oldLines[i]}`); i++; }
    else { body.push(`+${newLines[j]}`); j++; }
  }
  while (i < n) { body.push(`-${oldLines[i]}`); i++; }
  while (j < m) { body.push(`+${newLines[j]}`); j++; }
  const oldCount = oldLines.length; const newCount = newLines.length;
  const hunkHeader = `@@ -${oldCount === 0 ? 0 : 1},${oldCount} +${newCount === 0 ? 0 : 1},${newCount} @@`;
  return [...header, hunkHeader, ...body].join('\n') + '\n';
}
export const computeDiff = createDiff;
export const unifiedDiff = createDiff;
