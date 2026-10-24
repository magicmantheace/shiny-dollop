import { describe, expect, test } from 'vitest';
// Unit tests for the revision history line diff.
import { diffLines, hasChanges } from '../../src/lib/diff';

describe('diffLines', () => {
  test('identical texts produce only same lines', () => {
    const lines = diffLines('a\nb', 'a\nb');
    expect(lines).toEqual([
      { kind: 'same', text: 'a' },
      { kind: 'same', text: 'b' },
    ]);
    expect(hasChanges(lines)).toBe(false);
  });

  test('changed and added lines are marked', () => {
    const lines = diffLines('ratio 25:1.\nturn weekly.', 'ratio 30:1.\nturn weekly.\nkeep moist.');
    expect(lines).toContainEqual({ kind: 'del', text: 'ratio 25:1.' });
    expect(lines).toContainEqual({ kind: 'add', text: 'ratio 30:1.' });
    expect(lines).toContainEqual({ kind: 'same', text: 'turn weekly.' });
    expect(lines).toContainEqual({ kind: 'add', text: 'keep moist.' });
    expect(hasChanges(lines)).toBe(true);
  });

  test('handles empty old text', () => {
    const lines = diffLines('', 'hello');
    expect(lines).toEqual([{ kind: 'add', text: 'hello' }]);
    expect(hasChanges(lines)).toBe(true);
  });

  test('handles empty new text', () => {
    const lines = diffLines('hello', '');
    expect(lines).toEqual([{ kind: 'del', text: 'hello' }]);
    expect(hasChanges(lines)).toBe(true);
  });
});
