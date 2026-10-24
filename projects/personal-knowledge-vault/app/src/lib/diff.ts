// Simple line-based diff used by the revision history panel.
// Compares an older text snapshot against a newer one and reports
// unchanged ('same'), removed ('del') and added ('add') lines.

export interface DiffLine {
  kind: 'same' | 'add' | 'del';
  text: string;
}

export function diffLines(oldText: string, newText: string): DiffLine[] {
  // ''.split('\n') yields [''] — treat empty text as zero lines.
  const split = (t: string): string[] => (t === '' ? [] : t.split('\n'));
  const a = split(oldText);
  const b = split(newText);
  const n = a.length;
  const m = b.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () =>
    new Array<number>(m + 1).fill(0),
  );
  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      const ai = a[i] as string;
      const bj = b[j] as string;
      const next = dp[i + 1] as number[];
      const cur = dp[i] as number[];
      cur[j] = ai === bj ? (next[j + 1] as number) + 1 : Math.max(next[j] as number, cur[j + 1] as number);
    }
  }
  const out: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    const ai = a[i] as string;
    const bj = b[j] as string;
    if (ai === bj) {
      out.push({ kind: 'same', text: ai });
      i += 1;
      j += 1;
    } else if ((dp[i + 1]?.[j] ?? 0) >= (dp[i]?.[j + 1] ?? 0)) {
      out.push({ kind: 'del', text: ai });
      i += 1;
    } else {
      out.push({ kind: 'add', text: bj });
      j += 1;
    }
  }
  while (i < n) {
    out.push({ kind: 'del', text: a[i] as string });
    i += 1;
  }
  while (j < m) {
    out.push({ kind: 'add', text: b[j] as string });
    j += 1;
  }
  return out;
}

/** True when the diff contains any added or removed lines. */
export function hasChanges(lines: DiffLine[]): boolean {
  return lines.some((l) => l.kind !== 'same');
}
