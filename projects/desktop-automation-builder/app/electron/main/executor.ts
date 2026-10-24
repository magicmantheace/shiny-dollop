// Workflow executor: sandbox enforcement, dry-run preview, step execution,
// cancellation, and retry-from-failure. Pure Node — no Electron imports, so
// it is directly unit-testable.
import { spawn, type ChildProcess } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { copyFile, mkdir, rename, stat } from 'node:fs/promises';
import { basename, dirname, resolve, sep } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import {
  DAB_ERROR_CODES,
  dabError,
  type DabError,
} from '../../shared/errors.js';
import type {
  PreviewAction,
  Run,
  Step,
  StepKind,
  Workflow,
} from '../../shared/types.js';
import {
  createRun,
  getRun,
  getScript,
  getWorkflow,
  setRunStatus,
  transact,
  updateRunStep,
} from './store.js';

// ---------------------------------------------------------------------------
// Sandbox enforcement
// ---------------------------------------------------------------------------

/**
 * Resolve a step path inside the sandbox. Throws PATH_OUTSIDE_SANDBOX naming
 * the step when the resolved path escapes the sandbox root — this catches
 * `..` traversal and absolute-path escapes alike.
 */
export function resolveInSandbox(sandboxRoot: string, p: string, stepId: string): string {
  const root = resolve(sandboxRoot);
  const resolved = resolve(root, p);
  if (resolved !== root && !resolved.startsWith(root + sep)) {
    throw dabError(
      DAB_ERROR_CODES.PATH_OUTSIDE_SANDBOX,
      `Step "${stepId}": path "${p}" escapes the workflow sandbox.`,
    );
  }
  return resolved;
}

/** Steps that mutate or run code — the approval gate treats them as destructive-ish. */
const DESTRUCTIVE_KINDS: ReadonlySet<StepKind> = new Set(['file-move-to-trash', 'run-approved-script']);

export function requiresApproval(steps: Step[]): boolean {
  return steps.some((s) => DESTRUCTIVE_KINDS.has(s.kind));
}

// ---------------------------------------------------------------------------
// Cancellation registry
// ---------------------------------------------------------------------------

interface ActiveRunControl {
  cancelled: boolean;
  child: ChildProcess | undefined;
}

const activeRuns = new Map<string, ActiveRunControl>();

export function isRunActive(runId: string): boolean {
  return activeRuns.has(runId);
}

// ---------------------------------------------------------------------------
// Preview (dry-run)
// ---------------------------------------------------------------------------

const MAX_DETAIL = 8000;

function truncate(s: string): string {
  return s.length > MAX_DETAIL ? s.slice(0, MAX_DETAIL) + '…[truncated]' : s;
}

function describeStep(db: DatabaseSync, wf: Workflow, step: Step): string {
  switch (step.kind) {
    case 'file-copy': {
      const from = resolveInSandbox(wf.sandboxRoot, step.from, step.id);
      const to = resolveInSandbox(wf.sandboxRoot, step.to, step.id);
      return `Copy "${from}" → "${to}"`;
    }
    case 'file-move-to-trash': {
      const p = resolveInSandbox(wf.sandboxRoot, step.path, step.id);
      return `Move "${p}" to the sandbox trash (.dab-trash) — recoverable, never deleted`;
    }
    case 'folder-create': {
      const p = resolveInSandbox(wf.sandboxRoot, step.path, step.id);
      return `Create folder "${p}" (parents created as needed)`;
    }
    case 'run-approved-script': {
      const script = getScript(db, step.scriptId);
      if (!script) {
        throw dabError(
          DAB_ERROR_CODES.SCRIPT_NOT_APPROVED,
          `Step "${step.id}": script "${step.scriptId}" is not in the approved-scripts allowlist.`,
        );
      }
      const args = step.args.length > 0 ? ` with args: ${step.args.join(' ')}` : '';
      return `Run approved script "${script.name}" (${script.path})${args}`;
    }
    case 'log-message':
      return `Log message: "${step.message}"`;
    default: {
      const _exhaustive: never = step;
      throw stepFailed('STEP_FAILED', `Unknown step kind: ${JSON.stringify(_exhaustive)}`);
    }
  }
}

/**
 * Dry-run: returns plain-language descriptions and performs ZERO
 * filesystem writes. Sandbox and allowlist violations still throw.
 */
export function previewWorkflow(db: DatabaseSync, wf: Workflow): PreviewAction[] {
  return wf.steps.map((step) => ({
    stepId: step.id,
    kind: step.kind,
    label: step.label,
    description: describeStep(db, wf, step),
  }));
}

// ---------------------------------------------------------------------------
// Step execution
// ---------------------------------------------------------------------------

const SCRIPT_TIMEOUT_MS = 60_000;

function stepFailed(code: keyof typeof DAB_ERROR_CODES, message: string): DabError {
  return dabError(DAB_ERROR_CODES[code], message);
}

function runScript(
  scriptPath: string,
  args: string[],
  cwd: string,
  ctrl: ActiveRunControl,
): Promise<{ exitCode: number; stdout: string; stderr: string; killed: boolean }> {
  return new Promise((resolvePromise) => {
    const child = spawn(scriptPath, args, {
      cwd,
      shell: false,
      timeout: SCRIPT_TIMEOUT_MS,
      windowsHide: true,
      // Own process group on POSIX so cancellation can kill the whole tree
      // (a shell script's children would otherwise outlive it and hold the
      // stdio pipes open).
      detached: process.platform !== 'win32',
    });
    ctrl.child = child;
    let stdout = '';
    let stderr = '';
    let killed = false;
    child.stdout?.on('data', (d: Buffer) => {
      stdout += d.toString();
    });
    child.stderr?.on('data', (d: Buffer) => {
      stderr += d.toString();
    });
    child.on('error', () => {
      // 'error' fires on spawn failure; 'close' follows and settles the promise.
    });
    child.on('close', (code, signal) => {
      if (ctrl.child === child) ctrl.child = undefined;
      killed = signal === 'SIGKILL' || signal === 'SIGTERM';
      resolvePromise({ exitCode: code ?? -1, stdout, stderr, killed });
    });
  });
}

async function executeStep(
  db: DatabaseSync,
  wf: Workflow,
  step: Step,
  ctrl: ActiveRunControl,
): Promise<string> {
  switch (step.kind) {
    case 'file-copy': {
      const from = resolveInSandbox(wf.sandboxRoot, step.from, step.id);
      const to = resolveInSandbox(wf.sandboxRoot, step.to, step.id);
      try {
        const st = await stat(from);
        if (!st.isFile()) throw new Error(`"${from}" is not a file`);
        await mkdir(dirname(to), { recursive: true });
        await copyFile(from, to);
        return `Copied ${st.size} bytes: "${from}" → "${to}"`;
      } catch (err) {
        throw stepFailed('STEP_FAILED', `Step "${step.id}" file-copy failed: ${errMessage(err)}`);
      }
    }
    case 'file-move-to-trash': {
      const p = resolveInSandbox(wf.sandboxRoot, step.path, step.id);
      try {
        const trashDir = resolveInSandbox(wf.sandboxRoot, '.dab-trash', step.id);
        await mkdir(trashDir, { recursive: true });
        const dest = resolveInSandbox(
          wf.sandboxRoot,
          `.dab-trash/${Date.now()}-${randomUUID().slice(0, 8)}-${basename(p)}`,
          step.id,
        );
        await rename(p, dest);
        return `Moved "${p}" to trash: "${dest}" (recoverable)`;
      } catch (err) {
        throw stepFailed('STEP_FAILED', `Step "${step.id}" move-to-trash failed: ${errMessage(err)}`);
      }
    }
    case 'folder-create': {
      const p = resolveInSandbox(wf.sandboxRoot, step.path, step.id);
      try {
        await mkdir(p, { recursive: true });
        return `Created folder "${p}"`;
      } catch (err) {
        throw stepFailed('STEP_FAILED', `Step "${step.id}" folder-create failed: ${errMessage(err)}`);
      }
    }
    case 'run-approved-script': {
      const script = getScript(db, step.scriptId);
      if (!script) {
        throw stepFailed(
          'SCRIPT_NOT_APPROVED',
          `Step "${step.id}": script "${step.scriptId}" is not in the approved-scripts allowlist.`,
        );
      }
      let scriptStat;
      try {
        scriptStat = await stat(script.path);
      } catch {
        scriptStat = null;
      }
      if (!scriptStat || !scriptStat.isFile()) {
        throw stepFailed('SCRIPT_NOT_FOUND', `Step "${step.id}": approved script file not found: "${script.path}"`);
      }
      const result = await runScript(script.path, step.args, resolve(wf.sandboxRoot), ctrl);
      if (ctrl.cancelled || result.killed) {
        throw stepFailed('STEP_FAILED', `Step "${step.id}" was cancelled during script execution.`);
      }
      const detail =
        `Script "${script.name}" exited with code ${result.exitCode}.` +
        (result.stdout ? `\nstdout:\n${truncate(result.stdout)}` : '') +
        (result.stderr ? `\nstderr:\n${truncate(result.stderr)}` : '');
      if (result.exitCode !== 0) {
        throw stepFailed('STEP_FAILED', `Step "${step.id}" script failed.\n${detail}`);
      }
      return detail;
    }
    case 'log-message':
      return step.message;
    default: {
      const _exhaustive: never = step;
      throw stepFailed('STEP_FAILED', `Unknown step kind: ${JSON.stringify(_exhaustive)}`);
    }
  }
}

function killChildTree(child: ChildProcess | undefined): void {
  if (!child) return;
  const pid = child.pid;
  if (pid !== undefined && process.platform !== 'win32') {
    try {
      process.kill(-pid, 'SIGKILL');
      return;
    } catch {
      // Group already gone — fall through to a direct kill.
    }
  }
  try {
    child.kill('SIGKILL');
  } catch {
    // Process already exited; the executor will observe the flag.
  }
}

function errMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

// ---------------------------------------------------------------------------
// Run lifecycle
// ---------------------------------------------------------------------------

export interface StartRunOptions {
  approved: boolean;
}

/**
 * Create a run record. approved=false → `awaiting-approval`, zero side
 * effects. approved=true → executes immediately and resolves with the final
 * run (completed / failed / cancelled).
 */
export async function startRun(
  db: DatabaseSync,
  workflowId: string,
  options: StartRunOptions,
): Promise<Run> {
  const wf = getWorkflow(db, workflowId);
  if (!wf) throw dabError(DAB_ERROR_CODES.WORKFLOW_NOT_FOUND, `Workflow not found: ${workflowId}`);

  if (!options.approved) {
    // Explicit approval gate: no validation of side effects is skipped, but
    // nothing executes and nothing is written to the filesystem.
    return createRun(db, {
      workflowId: wf.id,
      workflowVersion: wf.version,
      status: 'awaiting-approval',
      dryRun: false,
      steps: wf.steps.map((s) => ({ stepId: s.id, kind: s.kind, label: s.label, outcome: 'pending' as const })),
    });
  }

  if (requiresApproval(wf.steps) && !options.approved) {
    // Unreachable via the public runsStart path (handled above), but kept as
    // a guard so the executor can never run destructive steps unapproved.
    throw dabError(DAB_ERROR_CODES.APPROVAL_REQUIRED, 'Approval is required before running destructive steps.');
  }

  const run = createRun(db, {
    workflowId: wf.id,
    workflowVersion: wf.version,
    status: 'running',
    dryRun: false,
    steps: wf.steps.map((s) => ({ stepId: s.id, kind: s.kind, label: s.label, outcome: 'pending' as const })),
  });
  return executeRun(db, run.id);
}

/**
 * Execute (or resume) a run. Steps already recorded as `skipped` or
 * `succeeded` are not re-run — this is what makes retry-from-failure work.
 */
export async function executeRun(db: DatabaseSync, runId: string): Promise<Run> {
  const run = getRun(db, runId);
  if (!run) throw dabError(DAB_ERROR_CODES.RUN_NOT_FOUND, `Run not found: ${runId}`);
  const wf = getWorkflow(db, run.workflowId);
  if (!wf) throw dabError(DAB_ERROR_CODES.WORKFLOW_NOT_FOUND, `Workflow not found: ${run.workflowId}`);

  const ctrl: ActiveRunControl = { cancelled: false, child: undefined };
  activeRuns.set(runId, ctrl);
  try {
    setRunStatus(db, runId, 'running', false);
    for (let seq = 0; seq < wf.steps.length; seq++) {
      if (ctrl.cancelled) {
        updateRunStep(db, runId, seq, { outcome: 'cancelled', finished: true, detail: 'Cancelled before starting.' });
        setRunStatus(db, runId, 'cancelled', true);
        return getRunOrThrow(db, runId);
      }
      const existing = run.steps[seq];
      if (existing && (existing.outcome === 'skipped' || existing.outcome === 'succeeded')) {
        continue;
      }
      const step = wf.steps[seq];
      if (!step) continue;
      updateRunStep(db, runId, seq, { outcome: 'running', started: true });
      try {
        const detail = await executeStep(db, wf, step, ctrl);
        if (ctrl.cancelled) {
          updateRunStep(db, runId, seq, { outcome: 'cancelled', finished: true, detail: 'Cancelled.' });
          setRunStatus(db, runId, 'cancelled', true);
          return getRunOrThrow(db, runId);
        }
        updateRunStep(db, runId, seq, { outcome: 'succeeded', finished: true, detail });
      } catch (err) {
        if (ctrl.cancelled) {
          updateRunStep(db, runId, seq, { outcome: 'cancelled', finished: true, detail: 'Cancelled.' });
          setRunStatus(db, runId, 'cancelled', true);
        } else {
          const message = isDabError(err) ? err.message : errMessage(err);
          updateRunStep(db, runId, seq, { outcome: 'failed', finished: true, detail: message });
          setRunStatus(db, runId, 'failed', true);
        }
        return getRunOrThrow(db, runId);
      }
    }
    setRunStatus(db, runId, 'completed', true);
    return getRunOrThrow(db, runId);
  } finally {
    activeRuns.delete(runId);
  }
}

function getRunOrThrow(db: DatabaseSync, runId: string): Run {
  const run = getRun(db, runId);
  if (!run) throw dabError(DAB_ERROR_CODES.RUN_NOT_FOUND, `Run not found: ${runId}`);
  return run;
}

/**
 * Cancel a run. `awaiting-approval`/`pending` runs are marked cancelled
 * directly; a `running` run gets its abort flag set and its child process
 * killed, and the executor finalizes the DB state.
 */
export function cancelRun(db: DatabaseSync, runId: string): Run {
  const run = getRunOrThrow(db, runId);
  if (run.status === 'completed' || run.status === 'failed' || run.status === 'cancelled') {
    throw dabError(
      DAB_ERROR_CODES.RUN_NOT_CANCELLABLE,
      `Run ${runId} is ${run.status} and cannot be cancelled.`,
    );
  }
  const ctrl = activeRuns.get(runId);
  if (ctrl) {
    ctrl.cancelled = true;
    killChildTree(ctrl.child);
    // The executor loop owns the final DB write; return current state.
    return getRunOrThrow(db, runId);
  }
  // Not actively executing (e.g. awaiting-approval): cancel immediately.
  transact(db, () => {
    const fresh = getRunOrThrow(db, runId);
    fresh.steps.forEach((s, seq) => {
      if (s.outcome === 'pending' || s.outcome === 'running') {
        updateRunStep(db, runId, seq, { outcome: 'cancelled', finished: true, detail: 'Cancelled.' });
      }
    });
    setRunStatus(db, runId, 'cancelled', true);
  });
  return getRunOrThrow(db, runId);
}

/**
 * Retry a failed run: creates a NEW run of the same workflow version with
 * steps before the failed one marked `skipped`, then resumes at the failed
 * step. The original run is left untouched.
 */
export async function retryRun(db: DatabaseSync, runId: string): Promise<Run> {
  const source = getRunOrThrow(db, runId);
  if (source.status !== 'failed') {
    throw dabError(
      DAB_ERROR_CODES.RUN_NOT_RETRYABLE,
      `Run ${runId} is ${source.status}; only failed runs can be retried.`,
    );
  }
  const wf = getWorkflow(db, source.workflowId);
  if (!wf) throw dabError(DAB_ERROR_CODES.WORKFLOW_NOT_FOUND, `Workflow not found: ${source.workflowId}`);

  const failedIdx = source.steps.findIndex((s) => s.outcome === 'failed');
  if (failedIdx === -1) {
    throw dabError(DAB_ERROR_CODES.RUN_NOT_RETRYABLE, `Run ${runId} has no failed step to resume from.`);
  }
  const failedStepId = source.steps[failedIdx]?.stepId;
  const resumeSeq = wf.steps.findIndex((s) => s.id === failedStepId);
  if (resumeSeq === -1) {
    throw dabError(
      DAB_ERROR_CODES.RUN_NOT_RETRYABLE,
      `Run ${runId}: failed step "${failedStepId ?? '?'}" no longer exists in the workflow.`,
    );
  }

  const steps = wf.steps.map((s, seq) => ({
    stepId: s.id,
    kind: s.kind,
    label: s.label,
    outcome: (seq < resumeSeq ? 'skipped' : 'pending') as 'skipped' | 'pending',
  }));
  const next = createRun(db, {
    workflowId: wf.id,
    workflowVersion: source.workflowVersion,
    status: 'running',
    dryRun: false,
    steps,
  });
  // Stamp the skipped prefix with a reason (createRun leaves detail NULL).
  for (let seq = 0; seq < resumeSeq; seq++) {
    updateRunStep(db, next.id, seq, {
      outcome: 'skipped',
      finished: true,
      detail: `Skipped on retry: succeeded or passed before the failure in run ${runId}.`,
    });
  }
  return executeRun(db, next.id);
}

export function isDabError(err: unknown): err is DabError {
  if (typeof err !== 'object' || err === null) return false;
  const code = (err as { code?: unknown }).code;
  const message = (err as { message?: unknown }).message;
  if (typeof code !== 'string' || typeof message !== 'string') return false;
  return (Object.values(DAB_ERROR_CODES) as string[]).includes(code);
}
