import { describe, expect, it } from 'vitest';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { resolveInWorkspace } from '../../electron/main/workspace.js';

describe('resolveInWorkspace', () => {
  const root = mkdtempSync(join(tmpdir(), 'lacc-ws-'));
  it('normal relative resolves', () => {
    expect(resolveInWorkspace(root, 'a/b.txt')).toBe(join(root, 'a/b.txt'));
  });
  it.each(['../evil', 'a/../../evil', '/etc/passwd'])('rejects %s', (p) => {
    expect(() => resolveInWorkspace(root, p)).toThrowError(expect.objectContaining({ code: 'PATH_OUTSIDE_WORKSPACE' }));
  });
});
