import { describe, expect, it } from 'vitest';
import { ArgsParseError, parseArgsString, serializeArgs } from '../../shared/args';

describe('parseArgsString', () => {
  it('splits simple whitespace-separated args', () => {
    expect(parseArgsString('--fullscreen --level 3')).toEqual(['--fullscreen', '--level', '3']);
  });
  it('handles double-quoted segments with spaces', () => {
    expect(parseArgsString('--name "My Game" --level 3')).toEqual(['--name', 'My Game', '--level', '3']);
  });
  it('handles single-quoted segments', () => {
    expect(parseArgsString("--path 'C:\\Games\\x'")).toEqual(['--path', 'C:\\Games\\x']);
  });
  it('handles backslash escapes', () => {
    expect(parseArgsString('--say hello\\ world')).toEqual(['--say', 'hello world']);
  });
  it('handles empty quoted strings as empty args', () => {
    expect(parseArgsString('--name ""')).toEqual(['--name', '']);
  });
  it('returns [] for empty/blank input', () => {
    expect(parseArgsString('')).toEqual([]);
    expect(parseArgsString('   ')).toEqual([]);
  });
  it('throws on unterminated quotes', () => {
    expect(() => parseArgsString('--name "oops')).toThrow(ArgsParseError);
    expect(() => parseArgsString("--name 'oops")).toThrow(ArgsParseError);
  });
  it('keeps shell metacharacters as literal text (no interpretation)', () => {
    expect(parseArgsString('--cmd "a; rm -rf /"')).toEqual(['--cmd', 'a; rm -rf /']);
    expect(parseArgsString('$(evil) `backtick`')).toEqual(['$(evil)', '`backtick`']);
  });
});

describe('serializeArgs', () => {
  it('leaves simple args bare', () => {
    expect(serializeArgs(['--fullscreen', '--level', '3'])).toBe('--fullscreen --level 3');
    expect(serializeArgs([])).toBe('');
  });
  it('quotes arguments containing whitespace', () => {
    expect(serializeArgs(['--name', 'My Game'])).toBe('--name "My Game"');
    expect(serializeArgs(['a\tb'])).toBe('"a\tb"');
  });
  it('escapes backslashes so Windows paths survive', () => {
    expect(serializeArgs(['--path', 'C:\\Games\\x'])).toBe('--path "C:\\\\Games\\\\x"');
  });
  it('round-trips through parseArgsString losslessly', () => {
    const cases: string[][] = [
      [],
      ['--fullscreen'],
      ['--name', 'My Game'],
      ['--path', 'C:\\Games\\x'],
      [''],
      ['--name', ''],
      ['say "hi"'],
      ["it's"],
      ['a\\b'],
      ['--say', 'hello world'],
      ['trailing\\'],
      ['"quoted"'],
      ['--cmd', 'a; rm -rf /'],
    ];
    for (const args of cases) {
      expect(parseArgsString(serializeArgs(args))).toEqual(args);
    }
  });
});
