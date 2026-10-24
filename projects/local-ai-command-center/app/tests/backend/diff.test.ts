import { describe, expect, it } from 'vitest';
import { createDiff } from '../../electron/main/diff.js';

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
});
