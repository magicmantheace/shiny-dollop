import { describe, expect, it } from 'vitest';
import { mkdirSync, mkdtempSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { readExistingFile, resolveInWorkspace } from '../../electron/main/workspace.js';

describe('resolveInWorkspace', () => {
  const root = mkdtempSync(join(tmpdir(), 'lacc-ws-'));
  it('normal relative resolves', () => {
    expect(resolveInWorkspace(root, 'a/b.txt')).toBe(join(root, 'a/b.txt'));
  });
  it.each(['../evil', 'a/../../evil', '/etc/passwd'])('rejects %s', (p) => {
    expect(() => resolveInWorkspace(root, p)).toThrowError(expect.objectContaining({ code: 'PATH_OUTSIDE_WORKSPACE' }));
  });

  it('rejects a path through a symlinked directory pointing outside', () => {
    const outside = mkdtempSync(join(tmpdir(), 'lacc-outside-'));
    symlinkSync(outside, join(root, 'link'), 'dir');
    expect(() => resolveInWorkspace(root, 'link/out.txt')).toThrowError(expect.objectContaining({ code: 'PATH_OUTSIDE_WORKSPACE' }));
    expect(readExistingFile(root, 'link/out.txt')).toBeNull();
  });

  it('rejects a destination that is itself a symlink pointing outside', () => {
    const outside = mkdtempSync(join(tmpdir(), 'lacc-outside-'));
    const secret = join(outside, 'secret.txt');
    writeFileSync(secret, 'secret');
    symlinkSync(secret, join(root, 'evil.txt'));
    expect(() => resolveInWorkspace(root, 'evil.txt')).toThrowError(expect.objectContaining({ code: 'PATH_OUTSIDE_WORKSPACE' }));
    expect(readExistingFile(root, 'evil.txt')).toBeNull();
  });

  it('allows a symlink whose target stays inside the workspace', () => {
    mkdirSync(join(root, 'real'), { recursive: true });
    writeFileSync(join(root, 'real/inner.txt'), 'inner');
    symlinkSync(join(root, 'real'), join(root, 'alias'), 'dir');
    expect(resolveInWorkspace(root, 'alias/inner.txt')).toBe(join(root, 'alias/inner.txt'));
    expect(readExistingFile(root, 'alias/inner.txt')).toBe('inner');
  });
});
