// Runs lifecycle: approval gate, dry-run preview, mid-run failure + retry,
// cancellation, and partial-log persistence.
import { chmodSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  cancelRun,
  executeRun,
  isRunActive,
  previewWorkflow,
  retryRun,
  retryRunAndWait,
  startRun,
  startRunAndWait,
  waitForRun,
} from '../../electron/main/executor.js';
import {
  createRun,
  createWorkflow,
  getRun,
  getWorkflow,
  listRuns,
  registerScript,
  updateWorkflow,
} from '../../electron/main/store.js';
import { makeFixture, sleep, type Fixture } from './helpers.js';

let fx: Fixture;

beforeEach(() => {
  fx = makeFixture();
  mkdirSync(fx.sandbox, { recursive: true });
});

afterEach(() => fx.cleanup());

function listTree(dir: string): string[] {
  if (!existsSync(dir)) return [];
  const out: string[] = [];
  const walk = (d: string, prefix: string) => {
    for (const entry of readdirSync(d, { withFileTypes: true })) {
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      if (entry.isDirectory()) walk(join(d, entry.name), rel);
      else out.push(rel);
    }
  };
  walk(dir, '');
  return out.sort();
}

describe('dry-run preview', () => {
  it('performs ZERO filesystem writes and returns plain-language descriptions', () => {
    writeFileSync(join(fx.sandbox, 'keep.txt'), 'x');
    const wf = createWorkflow(fx.db, { name: 'dry', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [
        { id: 'cp', label: 'Copy', kind: 'file-copy', from: 'keep.txt', to: 'copy.txt' },
        { id: 'mk', label: 'Mkdir', kind: 'folder-create', path: 'newdir' },
        { id: 'tr', label: 'Trash', kind: 'file-move-to-trash', path: 'keep.txt' },
        { id: 'lg', label: 'Log', kind: 'log-message', message: 'hello' },
      ],
    });
    const before = listTree(fx.sandbox);
    const wfNow = getWorkflow(fx.db, wf.id);
    expect(wfNow).not.toBeNull();
    const preview = previewWorkflow(fx.db, wfNow!);
    const after = listTree(fx.sandbox);

    expect(after).toEqual(before);
    expect(preview).toHaveLength(4);
    expect(preview[0]?.description).toContain('Copy');
    expect(preview[1]?.description).toContain('Create folder');
    expect(preview[2]?.description).toContain('recoverable');
    expect(preview[3]?.description).toContain('hello');
    // Preview creates no run records.
    expect(listRuns(fx.db)).toHaveLength(0);
  });
});

describe('approval gate', () => {
  it('runsStart(approved=false) creates an awaiting-approval run with no side effects', async () => {
    writeFileSync(join(fx.sandbox, 'a.txt'), 'data');
    const wf = createWorkflow(fx.db, { name: 'gate', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [
        { id: 'cp', label: 'Copy', kind: 'file-copy', from: 'a.txt', to: 'b.txt' },
        { id: 'tr', label: 'Trash', kind: 'file-move-to-trash', path: 'a.txt' },
      ],
    });
    const run = await startRun(fx.db, wf.id, { approved: false });
    expect(run.status).toBe('awaiting-approval');
    expect(run.steps.every((s) => s.outcome === 'pending')).toBe(true);
    expect(existsSync(join(fx.sandbox, 'b.txt'))).toBe(false);
    expect(existsSync(join(fx.sandbox, 'a.txt'))).toBe(true); // not trashed
    expect(existsSync(join(fx.sandbox, '.dab-trash'))).toBe(false);
  });
});

describe('mid-run failure and retry', () => {
  it('persists a partial log, and retry resumes from the failed step only', async () => {
    const wf = createWorkflow(fx.db, { name: 'retryable', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [
        { id: 'mk', label: 'Mkdir', kind: 'folder-create', path: 'out' },
        { id: 'cp', label: 'Copy', kind: 'file-copy', from: 'missing.txt', to: 'out/missing.txt' },
        { id: 'lg', label: 'Log', kind: 'log-message', message: 'finished' },
      ],
    });
    const failed = await startRunAndWait(fx.db, wf.id, { approved: true });
    expect(failed.status).toBe('failed');
    expect(failed.steps.map((s) => s.outcome)).toEqual(['succeeded', 'failed', 'pending']);
    expect(failed.steps[1]?.detail).toBeTruthy();
    expect(failed.finishedAt).toBeTruthy();

    // Fix the cause: provide the source file, then retry.
    writeFileSync(join(fx.sandbox, 'missing.txt'), 'payload');
    const retried = await retryRunAndWait(fx.db, failed.id);
    expect(retried.id).not.toBe(failed.id);
    expect(retried.status).toBe('completed');
    expect(retried.steps.map((s) => s.outcome)).toEqual(['skipped', 'succeeded', 'succeeded']);
    expect(readFileSync(join(fx.sandbox, 'out', 'missing.txt'), 'utf8')).toBe('payload');

    // The original run is untouched.
    const original = getRun(fx.db, failed.id);
    expect(original?.status).toBe('failed');
    expect(original?.steps.map((s) => s.outcome)).toEqual(['succeeded', 'failed', 'pending']);
  });

  it('retry of a non-failed run is rejected with RUN_NOT_RETRYABLE', async () => {
    const wf = createWorkflow(fx.db, { name: 'noretry', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [{ id: 'lg', label: 'Log', kind: 'log-message', message: 'ok' }],
    });
    const done = await startRunAndWait(fx.db, wf.id, { approved: true });
    expect(done.status).toBe('completed');
    await expect(retryRun(fx.db, done.id)).rejects.toMatchObject({ code: 'RUN_NOT_RETRYABLE' });
  });
});

describe('cancellation', () => {
  it('cancel mid-run yields status cancelled plus a persisted partial log', async () => {
    // A script that sleeps 15s gives us a long mid-run window.
    const scriptPath = join(fx.root, 'sleep.sh');
    writeFileSync(scriptPath, '#!/bin/sh\nsleep 15\n');
    chmodSync(scriptPath, 0o755);
    const script = registerScript(fx.db, 'sleeper', scriptPath);

    const wf = createWorkflow(fx.db, { name: 'cancelme', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [
        { id: 'lg1', label: 'Start', kind: 'log-message', message: 'starting' },
        { id: 'sc', label: 'Sleep script', kind: 'run-approved-script', scriptId: script.id, args: [] },
        { id: 'lg2', label: 'End', kind: 'log-message', message: 'never reached' },
      ],
    });
    const wfNow = getWorkflow(fx.db, wf.id);
    expect(wfNow).not.toBeNull();
    const run = createRun(fx.db, {
      workflowId: wf.id,
      workflowVersion: wfNow!.version,
      status: 'running',
      dryRun: false,
      steps: wfNow!.steps.map((s) => ({ stepId: s.id, kind: s.kind, label: s.label, outcome: 'pending' as const })),
    });

    const execPromise = executeRun(fx.db, run.id);
    await sleep(600); // first step done, script running
    cancelRun(fx.db, run.id);
    const final = await execPromise;

    expect(final.status).toBe('cancelled');
    expect(final.steps[0]?.outcome).toBe('succeeded');
    expect(final.steps[1]?.outcome).toBe('cancelled');
    expect(final.finishedAt).toBeTruthy();

    const persisted = getRun(fx.db, run.id);
    expect(persisted?.status).toBe('cancelled');
    expect(persisted?.steps[0]?.outcome).toBe('succeeded'); // partial log persisted
  }, 20000);

  it('cancelling an awaiting-approval run marks steps cancelled immediately', async () => {
    const wf = createWorkflow(fx.db, { name: 'pending-cancel', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [{ id: 'lg', label: 'Log', kind: 'log-message', message: 'hi' }],
    });
    const run = await startRun(fx.db, wf.id, { approved: false });
    const cancelled = cancelRun(fx.db, run.id);
    expect(cancelled.status).toBe('cancelled');
    expect(cancelled.steps[0]?.outcome).toBe('cancelled');
  });

  it('cancelling a completed run throws RUN_NOT_CANCELLABLE', async () => {
    const wf = createWorkflow(fx.db, { name: 'donecancel', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [{ id: 'lg', label: 'Log', kind: 'log-message', message: 'hi' }],
    });
    const done = await startRunAndWait(fx.db, wf.id, { approved: true });
    expect(() => cancelRun(fx.db, done.id)).toThrowError(
      expect.objectContaining({ code: 'RUN_NOT_CANCELLABLE' }),
    );
  });
});

describe('cancellation before script spawn (Codex cycle-2 regression)', () => {
  it('a cancel arriving while the script path is stat-checked prevents the script from ever spawning', async () => {
    // The script's ONLY effect is creating this marker — if cancellation
    // loses the race, the marker proves the script ran anyway.
    const marker = join(fx.sandbox, 'script-ran.txt');
    const scriptPath = join(fx.root, 'marker.sh');
    writeFileSync(scriptPath, `#!/bin/sh\ntouch "${marker}"\n`);
    chmodSync(scriptPath, 0o755);
    const script = registerScript(fx.db, 'marker', scriptPath);

    const wf = createWorkflow(fx.db, { name: 'cancel-before-spawn', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [
        { id: 'sc', label: 'Marker script', kind: 'run-approved-script', scriptId: script.id, args: [] },
      ],
    });
    const wfNow = getWorkflow(fx.db, wf.id);
    expect(wfNow).not.toBeNull();
    const run = createRun(fx.db, {
      workflowId: wf.id,
      workflowVersion: wfNow!.version,
      status: 'running',
      dryRun: false,
      steps: wfNow!.steps.map((s) => ({ stepId: s.id, kind: s.kind, label: s.label, outcome: 'pending' as const })),
    });

    const execPromise = executeRun(fx.db, run.id);
    // executeRun is parked at `await stat(script.path)` when control returns
    // here (the fs completion cannot fire during this synchronous turn), so
    // this cancel lands exactly in the window Codex flagged: the flag is set
    // but there is no child process to kill yet.
    cancelRun(fx.db, run.id);
    const final = await execPromise;

    expect(final.status).toBe('cancelled');
    expect(final.steps[0]?.outcome).toBe('cancelled');
    expect(existsSync(marker)).toBe(false);
  });
});

describe('retry after the workflow was edited', () => {
  it('executes the archived failed-run version, not the later edit', async () => {
    const wf = createWorkflow(fx.db, { name: 'versioned-retry', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [
        { id: 'mk', label: 'Mkdir', kind: 'folder-create', path: 'out' },
        { id: 'cp', label: 'Copy', kind: 'file-copy', from: 'missing.txt', to: 'out/missing.txt' },
        { id: 'lg', label: 'Log', kind: 'log-message', message: 'finished' },
      ],
    });
    const failed = await startRunAndWait(fx.db, wf.id, { approved: true });
    expect(failed.status).toBe('failed');
    expect(failed.workflowVersion).toBe(2);

    // Edit AFTER the failure: the failed step is redefined as a folder
    // action. Running it on retry would execute an action that was never
    // previewed/approved for the failed run.
    const edited = updateWorkflow(fx.db, wf.id, {
      steps: [
        { id: 'mk', label: 'Mkdir', kind: 'folder-create', path: 'out' },
        { id: 'cp', label: 'Copy', kind: 'folder-create', path: 'edited-dir' },
        { id: 'lg', label: 'Log', kind: 'log-message', message: 'finished' },
      ],
    });
    expect(edited?.version).toBe(3);

    // Fix the original cause and retry: the ARCHIVED file-copy must run.
    writeFileSync(join(fx.sandbox, 'missing.txt'), 'payload');
    const retried = await retryRunAndWait(fx.db, failed.id);
    expect(retried.status).toBe('completed');
    expect(retried.workflowVersion).toBe(2);
    expect(retried.steps.map((x) => x.kind)).toEqual(['folder-create', 'file-copy', 'log-message']);
    expect(readFileSync(join(fx.sandbox, 'out', 'missing.txt'), 'utf8')).toBe('payload');
    expect(existsSync(join(fx.sandbox, 'edited-dir'))).toBe(false);
  });
});

describe('non-blocking start', () => {
  it('startRun resolves with the running record while execution is still in flight, and the run can be cancelled', async () => {
    const scriptPath = join(fx.root, 'sleep2.sh');
    writeFileSync(scriptPath, '#!/bin/sh\nsleep 15\n');
    chmodSync(scriptPath, 0o755);
    const script = registerScript(fx.db, 'sleeper2', scriptPath);
    const wf = createWorkflow(fx.db, { name: 'async-start', sandboxRoot: fx.sandbox });
    updateWorkflow(fx.db, wf.id, {
      steps: [
        { id: 'sc', label: 'Sleep script', kind: 'run-approved-script', scriptId: script.id, args: [] },
      ],
    });

    const startedAt = Date.now();
    const run = await startRun(fx.db, wf.id, { approved: true });
    // The promise resolved immediately — not after the 15s script.
    expect(Date.now() - startedAt).toBeLessThan(10_000);
    expect(run.status).toBe('running');
    expect(isRunActive(run.id)).toBe(true);

    cancelRun(fx.db, run.id);
    const final = await waitForRun(fx.db, run.id);
    expect(final.status).toBe('cancelled');
  }, 20000);
});
