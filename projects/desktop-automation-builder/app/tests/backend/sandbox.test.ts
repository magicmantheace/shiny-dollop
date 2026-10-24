// Sandbox enforcement: every step path must stay inside the workflow's
// sandboxRoot. `..` traversal and absolute escapes are the key cases.
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { resolveInSandbox, startRun } from '../../electron/main/executor.js';
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
    const run = await startRun(fx.db, wf.id, { approved: true });
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
    const run = await startRun(fx.db, wf.id, { approved: true });
    expect(run.status).toBe('completed');
    expect(run.steps.map((s) => s.outcome)).toEqual(['succeeded', 'succeeded', 'succeeded']);
  });
});
