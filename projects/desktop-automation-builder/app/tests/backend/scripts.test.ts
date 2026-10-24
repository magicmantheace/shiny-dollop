// Script allowlist enforcement and move-to-trash recoverability.
import { chmodSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { previewWorkflow, startRun } from '../../electron/main/executor.js';
import {
  createWorkflow,
  getWorkflow,
  registerScript,
  updateWorkflow,
} from '../../electron/main/store.js';
import { makeFixture, type Fixture } from './helpers.js';

let fx: Fixture;

beforeEach(() => {
  fx = makeFixture();
  mkdirSync(fx.sandbox, { recursive: true });
});

afterEach(() => fx.cleanup());

function makeScript(name: string, body: string): string {
  const p = join(fx.root, name);
  writeFileSync(p, body);
  chmodSync(p, 0o755);
  return p;
}

describe('approved scripts', () => {
  it('blocks an unapproved scriptId with SCRIPT_NOT_APPROVED (preview and run)', async () => {
    makeScript('evil.sh', '#!/bin/sh\necho pwned\n');
    const wf = createWorkflow(fx.db, { name: 'unapproved', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [
        { id: 'sc', label: 'Run it', kind: 'run-approved-script', scriptId: 'not-registered', args: [] },
      ],
    });
    const wfNow = getWorkflow(fx.db, wf.id);
    expect(wfNow).not.toBeNull();
    expect(() => previewWorkflow(fx.db, wfNow!)).toThrowError(
      expect.objectContaining({ code: 'SCRIPT_NOT_APPROVED' }),
    );
    const run = await startRun(fx.db, wf.id, { approved: true });
    expect(run.status).toBe('failed');
    expect(run.steps[0]?.outcome).toBe('failed');
    expect(run.steps[0]?.detail).toContain('not in the approved-scripts allowlist');
  });

  it('runs an approved script and captures stdout into the step detail', async () => {
    const scriptPath = makeScript('hello.sh', '#!/bin/sh\necho "hello from script $1"\n');
    const script = registerScript(fx.db, 'hello', scriptPath);
    const wf = createWorkflow(fx.db, { name: 'approved', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [
        { id: 'sc', label: 'Run hello', kind: 'run-approved-script', scriptId: script.id, args: ['world'] },
      ],
    });
    const run = await startRun(fx.db, wf.id, { approved: true });
    expect(run.status).toBe('completed');
    expect(run.steps[0]?.outcome).toBe('succeeded');
    expect(run.steps[0]?.detail).toContain('hello from script world');
    expect(run.steps[0]?.detail).toContain('exited with code 0');
  });

  it('a non-zero exit code fails the step and captures stderr', async () => {
    const scriptPath = makeScript('bad.sh', '#!/bin/sh\necho "boom" 1>&2\nexit 3\n');
    const script = registerScript(fx.db, 'bad', scriptPath);
    const wf = createWorkflow(fx.db, { name: 'failingscript', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [
        { id: 'sc', label: 'Run bad', kind: 'run-approved-script', scriptId: script.id, args: [] },
      ],
    });
    const run = await startRun(fx.db, wf.id, { approved: true });
    expect(run.status).toBe('failed');
    expect(run.steps[0]?.detail).toContain('exited with code 3');
    expect(run.steps[0]?.detail).toContain('boom');
  });
});

describe('move-to-trash', () => {
  it('moves the file into .dab-trash instead of deleting it — fully recoverable', async () => {
    const original = join(fx.sandbox, 'important.txt');
    writeFileSync(original, 'precious data');
    const wf = createWorkflow(fx.db, { name: 'trasher', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [{ id: 'tr', label: 'Trash it', kind: 'file-move-to-trash', path: 'important.txt' }],
    });
    const run = await startRun(fx.db, wf.id, { approved: true });
    expect(run.status).toBe('completed');
    expect(existsSync(original)).toBe(false);
    const trashDir = join(fx.sandbox, '.dab-trash');
    const entries = readdirSync(trashDir);
    expect(entries).toHaveLength(1);
    const trashed = entries[0];
    expect(trashed).toContain('important.txt');
    expect(readFileSync(join(trashDir, trashed!), 'utf8')).toBe('precious data');
  });
});
