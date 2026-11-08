// Sandbox enforcement: every step path must stay inside the workflow's
// sandboxRoot. `..` traversal and absolute escapes are the key cases.
import { existsSync, mkdirSync, readFileSync, symlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { resolveInSandbox, resolveInSandboxReal, startRunAndWait } from '../../electron/main/executor.js';
import { createWorkflow, updateWorkflow } from '../../electron/main/store.js';
import { makeFixture, type Fixture } from './helpers.js';

let fx: Fixture;

beforeEach(() => {
  fx = makeFixture();
  mkdirSync(fx.sandbox, { recursive: true });
});

afterEach(() => fx.cleanup());

describe('resolveInSandbox', () => {
  it('resolves relative paths inside the sandbox', () => {
    expect(resolveInSandbox(fx.sandbox, 'a/b.txt', 's1')).toBe(join(fx.sandbox, 'a', 'b.txt'));
  });

  it('rejects ../evil traversal with PATH_OUTSIDE_SANDBOX naming the step', () => {
    expect(() => resolveInSandbox(fx.sandbox, '../evil', 'evil-step')).toThrowError(
      expect.objectContaining({ code: 'PATH_OUTSIDE_SANDBOX' }),
    );
    try {
      resolveInSandbox(fx.sandbox, '../evil', 'evil-step');
      expect.unreachable();
    } catch (err) {
      expect((err as { message: string }).message).toContain('evil-step');
    }
  });

  it('rejects absolute paths that escape the sandbox (/etc/...)', () => {
    expect(() => resolveInSandbox(fx.sandbox, '/etc/passwd', 's2')).toThrowError(
      expect.objectContaining({ code: 'PATH_OUTSIDE_SANDBOX' }),
    );
  });

  it('rejects nested traversal that climbs out and back in', () => {
    expect(() => resolveInSandbox(fx.sandbox, 'docs/../../evil', 's3')).toThrowError(
      expect.objectContaining({ code: 'PATH_OUTSIDE_SANDBOX' }),
    );
  });
});

describe('sandbox enforcement during execution', () => {
  it('a workflow step escaping the sandbox fails the run and writes nothing outside', async () => {
    writeFileSync(join(fx.root, 'outside.txt'), 'secret');
    const wf = createWorkflow(fx.db, { name: 'esc', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [
        {
          id: 'copy-outside',
          label: 'Steal from outside',
          kind: 'file-copy',
          from: '../outside.txt',
          to: 'stolen.txt',
        },
      ],
    });
    const run = await startRunAndWait(fx.db, wf.id, { approved: true });
    expect(run.status).toBe('failed');
    expect(run.steps[0]?.outcome).toBe('failed');
    expect(run.steps[0]?.detail).toContain('escapes the workflow sandbox');
  });

  it('an approved run with valid in-sandbox paths completes', async () => {
    writeFileSync(join(fx.sandbox, 'a.txt'), 'hello');
    const wf = createWorkflow(fx.db, { name: 'ok', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [
        { id: 'mk', label: 'mkdir', kind: 'folder-create', path: 'out' },
        { id: 'cp', label: 'copy', kind: 'file-copy', from: 'a.txt', to: 'out/a.txt' },
        { id: 'lg', label: 'log', kind: 'log-message', message: 'done' },
      ],
    });
    const run = await startRunAndWait(fx.db, wf.id, { approved: true });
    expect(run.status).toBe('completed');
    expect(run.steps.map((s) => s.outcome)).toEqual(['succeeded', 'succeeded', 'succeeded']);
  });
});

describe('sandbox enforcement against filesystem links', () => {
  function makeEscapeLink() {
    const outside = join(fx.root, 'outside');
    mkdirSync(outside, { recursive: true });
    symlinkSync(outside, join(fx.sandbox, 'link'), 'dir');
    return outside;
  }

  it('resolveInSandboxReal rejects a path through a symlink that escapes', async () => {
    makeEscapeLink();
    await expect(resolveInSandboxReal(fx.sandbox, 'link/victim.txt', 's-link')).rejects.toMatchObject({
      code: 'PATH_OUTSIDE_SANDBOX',
    });
  });

  it('resolveInSandboxReal accepts ordinary new paths and existing in-sandbox files', async () => {
    writeFileSync(join(fx.sandbox, 'real.txt'), 'ok');
    await expect(resolveInSandboxReal(fx.sandbox, 'real.txt', 's-ok')).resolves.toBe(
      join(fx.sandbox, 'real.txt'),
    );
    await expect(resolveInSandboxReal(fx.sandbox, 'newdir/file.txt', 's-ok')).resolves.toBe(
      join(fx.sandbox, 'newdir', 'file.txt'),
    );
  });

  it('a copy whose destination traverses a symlink fails and writes nothing outside', async () => {
    const outside = makeEscapeLink();
    writeFileSync(join(outside, 'victim.txt'), 'original');
    writeFileSync(join(fx.sandbox, 'a.txt'), 'payload');
    const wf = createWorkflow(fx.db, { name: 'link-copy', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [{ id: 'cp', label: 'Copy', kind: 'file-copy', from: 'a.txt', to: 'link/victim.txt' }],
    });
    const run = await startRunAndWait(fx.db, wf.id, { approved: true });
    expect(run.status).toBe('failed');
    expect(run.steps[0]?.detail).toContain('escapes the workflow sandbox');
    expect(readFileSync(join(outside, 'victim.txt'), 'utf8')).toBe('original');
  });

  it('a copy whose source traverses a symlink fails instead of reading outside data', async () => {
    const outside = makeEscapeLink();
    writeFileSync(join(outside, 'secret.txt'), 'secret');
    const wf = createWorkflow(fx.db, { name: 'link-read', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [{ id: 'cp', label: 'Copy', kind: 'file-copy', from: 'link/secret.txt', to: 'stolen.txt' }],
    });
    const run = await startRunAndWait(fx.db, wf.id, { approved: true });
    expect(run.status).toBe('failed');
    expect(existsSync(join(fx.sandbox, 'stolen.txt'))).toBe(false);
  });

  it('a folder-create through a symlink fails and creates nothing outside', async () => {
    const outside = makeEscapeLink();
    const wf = createWorkflow(fx.db, { name: 'link-mkdir', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [{ id: 'mk', label: 'Mkdir', kind: 'folder-create', path: 'link/newdir' }],
    });
    const run = await startRunAndWait(fx.db, wf.id, { approved: true });
    expect(run.status).toBe('failed');
    expect(existsSync(join(outside, 'newdir'))).toBe(false);
  });
});
