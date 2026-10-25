import { describe, expect, it } from 'vitest';
import { createDiff, MAX_DIFF_CELLS } from '../../electron/main/diff.js';

describe('diff', () => {
  it('new file all + lines', () => {
    const d = createDiff('a.txt', null, 'one\ntwo\n');
    expect(d).toContain('--- a/a.txt');
    expect(d).toContain('+++ b/a.txt');
    expect(d).toContain('+one');
    expect(d).toContain('+two');
    expect(d.split('\n').some((l) => l.startsWith('-') && l !== '--- a/a.txt')).toBe(false);
  });
  it('modified contains - and +', () => {
    const d = createDiff('a.txt', 'hello\nworld\n', 'hello\nthere\n');
    expect(d).toContain('-world');
    expect(d).toContain('+there');
    expect(d).toContain(' hello');
  });
  it('identical has no +/- lines', () => {
    const d = createDiff('a.txt', 'same\n', 'same\n');
    const lines = d.split('\n').filter((l) => (l.startsWith('+') && !l.startsWith('+++')) || (l.startsWith('-') && !l.startsWith('---')));
    expect(lines.length).toBe(0);
  });
  it('shows an added end-of-file newline as an explicit change (hello -> hello\\n)', () => {
    // Regression (Codex 4368412474): splitLines dropped the trailing empty
    // element, so contents differing only by the final newline produced a
    // hunk of pure context and the proposal review hid the change.
    const d = createDiff('a.txt', 'hello', 'hello\n');
    const lines = d.split('\n');
    const minus = lines.indexOf('-hello');
    const marker = lines.indexOf('\\ No newline at end of file');
    const plus = lines.indexOf('+hello');
    expect(minus).toBeGreaterThanOrEqual(0);
    expect(plus).toBeGreaterThanOrEqual(0);
    expect(marker).toBe(minus + 1);
    expect(plus).toBe(marker + 1);
  });
  it('shows a removed end-of-file newline as an explicit change (hello\\n -> hello)', () => {
    const d = createDiff('a.txt', 'hello\n', 'hello');
    const lines = d.split('\n');
    const minus = lines.indexOf('-hello');
    const plus = lines.indexOf('+hello');
    const marker = lines.indexOf('\\ No newline at end of file');
    expect(minus).toBeGreaterThanOrEqual(0);
    expect(plus).toBe(minus + 1);
    expect(marker).toBe(plus + 1);
  });
  it('marks a new file whose content has no trailing newline', () => {
    const d = createDiff('a.txt', null, 'hello');
    const lines = d.split('\n');
    const plus = lines.indexOf('+hello');
    expect(plus).toBeGreaterThanOrEqual(0);
    expect(lines[plus + 1]).toBe('\\ No newline at end of file');
  });
  it('marks both sides when the changed last line lacks a trailing newline in both', () => {
    const d = createDiff('a.txt', 'hello\nworld', 'hello\nthere');
    const lines = d.split('\n');
    const minus = lines.indexOf('-world');
    const plus = lines.indexOf('+there');
    expect(lines[minus + 1]).toBe('\\ No newline at end of file');
    expect(lines[plus + 1]).toBe('\\ No newline at end of file');
  });
  it('an extra trailing blank line stays visible and needs no EOF marker', () => {
    const d = createDiff('a.txt', 'hello\n', 'hello\n\n');
    const lines = d.split('\n');
    expect(lines).toContain('+');
    expect(lines).not.toContain('\\ No newline at end of file');
  });
  it('identical contents without a trailing newline still produce no change lines', () => {
    const d = createDiff('a.txt', 'same', 'same');
    const lines = d.split('\n').filter((l) => (l.startsWith('+') && !l.startsWith('+++')) || (l.startsWith('-') && !l.startsWith('---')));
    expect(lines.length).toBe(0);
  });
  it('bounds the diff: line-count product above the cap uses a simplified diff, not the LCS matrix', () => {
    // 2,000 x 2,000 = 4,000,000 cells > MAX_DIFF_CELLS: pre-fix this allocated
    // the full quadratic matrix; the bounded path must not.
    expect(MAX_DIFF_CELLS).toBeLessThan(2_000 * 2_000);
    const oldContent = Array.from({ length: 2000 }, (_, i) => `old-${i}`).join('\n') + '\n';
    const newContent = Array.from({ length: 2000 }, (_, i) => `new-${i}`).join('\n') + '\n';
    const d = createDiff('big.txt', oldContent, newContent);
    expect(d).toContain('Diff simplified');
    expect(d).toContain('-old-0');
    expect(d).toContain('+new-1999');
  });
  it('10,000-line files (the Codex OOM repro) complete via the bounded path', () => {
    const oldContent = Array.from({ length: 10_000 }, (_, i) => `o${i}`).join('\n') + '\n';
    const newContent = Array.from({ length: 10_000 }, (_, i) => `n${i}`).join('\n') + '\n';
    const d = createDiff('huge.txt', oldContent, newContent);
    expect(d).toContain('Diff simplified');
    expect(d).toContain('+n9999');
  });
  it('large files with a small changed middle still get an exact diff (common prefix/suffix trimmed)', () => {
    const common = Array.from({ length: 3000 }, (_, i) => `same-${i}`);
    const oldContent = [...common, 'before', ...common].join('\n') + '\n';
    const newContent = [...common, 'after', ...common].join('\n') + '\n';
    const d = createDiff('mostly-same.txt', oldContent, newContent);
    expect(d).not.toContain('Diff simplified');
    expect(d).toContain('-before');
    expect(d).toContain('+after');
    expect(d).toContain(' same-0');
  });
});
