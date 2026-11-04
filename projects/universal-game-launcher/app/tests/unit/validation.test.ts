import { mkdtempSync, writeFileSync, chmodSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  ValidationError,
  assertDirectoryUsable,
  assertExecutableUsable,
  canonicalKey,
  canonicalizePath,
  defaultTitleFor,
  validateArgsArray,
} from '../../electron/main/launch/validation';

function makeExe(): string {
  const dir = mkdtempSync(path.join(tmpdir(), 'ugl-val-'));
  const exe = path.join(dir, 'game.sh');
  writeFileSync(exe, '#!/bin/sh\necho hi\n');
  chmodSync(exe, 0o755);
  return exe;
}

describe('canonicalizePath', () => {
  it('resolves to an absolute path', () => {
    expect(path.isAbsolute(canonicalizePath('/tmp/../tmp/x'))).toBe(true);
  });
  it('rejects empty input', () => {
    expect(() => canonicalizePath('')).toThrow(ValidationError);
    expect(() => canonicalizePath('   ')).toThrow(ValidationError);
  });
  it('rejects null bytes', () => {
    expect(() => canonicalizePath('/tmp/a\0b')).toThrow(ValidationError);
  });
});

describe('canonicalKey', () => {
  it('is case-insensitive on win32', () => {
    expect(canonicalKey('C:\\Games\\X.exe', 'win32')).toBe(canonicalKey('c:\\games\\x.exe', 'win32'));
  });
  it('is case-sensitive on linux', () => {
    expect(canonicalKey('/Games/X', 'linux')).not.toBe(canonicalKey('/games/x', 'linux'));
  });
});

describe('defaultTitleFor', () => {
  it('strips the extension', () => {
    expect(defaultTitleFor('/g/My Game.exe')).toBe('My Game');
    expect(defaultTitleFor('/g/run')).toBe('run');
  });
});

describe('validateArgsArray', () => {
  it('accepts a normal argv array', () => {
    expect(validateArgsArray(['--a', 'b c'])).toEqual(['--a', 'b c']);
  });
  it('defaults undefined to []', () => {
    expect(validateArgsArray(undefined)).toEqual([]);
  });
  it('rejects non-arrays and non-strings', () => {
    expect(() => validateArgsArray('--a')).toThrow(ValidationError);
    expect(() => validateArgsArray([1])).toThrow(ValidationError);
  });
  it('rejects control characters', () => {
    expect(() => validateArgsArray(['a\0b'])).toThrow(ValidationError);
    expect(() => validateArgsArray(['a\nb'])).toThrow(ValidationError);
  });
  it('rejects empty strings and overlong args', () => {
    expect(() => validateArgsArray([''])).toThrow(ValidationError);
    expect(() => validateArgsArray(['x'.repeat(4097)])).toThrow(ValidationError);
  });
});

describe('assertExecutableUsable', () => {
  it('passes for a real file', async () => {
    await expect(assertExecutableUsable(makeExe())).resolves.toBeUndefined();
  });
  it('fails with FILE_NOT_FOUND for a missing path', async () => {
    const err = await assertExecutableUsable('/nope/missing-ugl-12345.exe').catch((e) => e);
    expect(err).toBeInstanceOf(ValidationError);
    expect((err as ValidationError).code).toBe('FILE_NOT_FOUND');
  });
  it('fails with NOT_A_FILE for a directory', async () => {
    const err = await assertExecutableUsable(tmpdir()).catch((e) => e);
    expect((err as ValidationError).code).toBe('NOT_A_FILE');
  });
});

describe('assertDirectoryUsable', () => {
  it('passes for a real directory', async () => {
    await expect(assertDirectoryUsable(tmpdir())).resolves.toBeUndefined();
  });
  it('fails for a missing directory', async () => {
    const err = await assertDirectoryUsable('/nope/missing-ugl-dir-12345').catch((e) => e);
    expect((err as ValidationError).code).toBe('WORKDIR_NOT_FOUND');
  });
  it('fails when the path is a file', async () => {
    const err = await assertDirectoryUsable(makeExe()).catch((e) => e);
    expect((err as ValidationError).code).toBe('WORKDIR_NOT_DIR');
  });
});
