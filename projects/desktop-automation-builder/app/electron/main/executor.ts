// Workflow executor: sandbox enforcement, dry-run preview, step execution,
// cancellation, and retry-from-failure. Pure Node — no Electron imports, so
// it is directly unit-testable.
import { spawn, type ChildProcess } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { copyFile, mkdir, realpath, rename, stat } from 'node:fs/promises';
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

function isInsideRoot(root: string, p: string): boolean {
  return p === root || p.startsWith(root + sep);
}

/**
 * Filesystem-aware sandbox check for MUTATING operations. The lexical
 * check in `resolveInSandbox` cannot see symlinks / directory junctions:
 * a link inside the sandbox pointing outside it passes the prefix check
 * while `copyFile` / `mkdir` / `rename` happily follow it out.
 *
 * This resolves the real path of the target — or, for a destination that
 * does not exist yet, of its nearest existing ancestor — and requires it
 * to stay inside the sandbox's real path. The not-yet-existing tail is
 * made of plain names (no links can hide in it), so validating the
 * deepest existing ancestor covers the whole path. Returns the lexical
 * resolved path on success; throws PATH_OUTSIDE_SANDBOX otherwise.
 */
export async function resolveInSandboxReal(
  sandboxRoot: string,
  p: string,
  stepId: string,
): Promise<string> {
  const resolved = resolveInSandbox(sandboxRoot, p, stepId);
  const rootLexical = resolve(sandboxRoot);
  let realRoot = rootLexical;
  try {
    realRoot = await realpath(rootLexical);
  } catch {
    // Sandbox root does not exist yet — nothing inside it can be a link,
    // and the lexical check above has already confined the path.
    return resolved;
  }

  let cur = resolved;
  for (;;) {
    try {
      const real = await realpath(cur);
      if (!isInsideRoot(realRoot, real)) {
        throw dabError(
          DAB_ERROR_CODES.PATH_OUTSIDE_SANDBOX,
          `Step "${stepId}": path "${p}" escapes the workflow sandbox through a filesystem link (resolves to "${real}").`,
        );
      }
      return resolved;
    } catch (err) {
      if (isDabError(err)) throw err;
      const code = (err as { code?: unknown }).code;
      if (code !== 'ENOENT' && code !== 'ENOTDIR') throw err;
      const parent = dirname(cur);
      if (parent === cur || !isInsideRoot(rootLexical, cur)) {
        // Reached the sandbox root (or above it) without finding an
        // existing ancestor — the lexical check already passed, so the
        // path is confined as long as the root itself is real-checked,
        // which the first iteration did when the root exists.
        return resolved;
      }
      cur = parent;
    }
  }
}

/** Steps that mutate or run code — the approval gate treats them as destructive-ish. */
const DESTRUCTIVE_KINDS: ReadonlySet<StepKind> = new Set(['file-move-to-trash', 'run-approved-script']);

export function requiresApproval(steps: Step[]): boolean {
  return steps.some((s) => DESTRUCTIVE_KINDS.has(s.kind));
}

// ---------------------------------------------------------------------------
// Cancellation registry
// ---------------------------------------------------------------------------

export interface ActiveRunControl {
  cancelled: boolean;
  child: ChildProcess | undefined;
}

const activeRuns = new Map<string, ActiveRunControl>();

export function isRunActive(runId: string): boolean {
  return activeRuns.has(runId);
}

/**
 * Promises of runs executing in the background (started via `startRun` /
 * `retryRun`, which return the `running` record immediately). Lets
 * in-process callers (smoke mode, tests) await completion via
 * `waitForRun` without making the IPC surface block on execution.
 */
const backgroundRuns = new Map<string, Promise<Run>>();

function launchInBackground(db: DatabaseSync, promise: Promise<Run>, runId: string): void {
  // executeRun records step failures in the DB and resolves with the
  // failed run; it only rejects on infrastructure errors (missing run /
  // workflow). Swallow those here — the persisted record is the truth —
  // so a background rejection can never crash the host process.
  const tracked = promise.catch(() => getRunOrThrow(db, runId));
  backgroundRuns.set(runId, tracked);
  void tracked.finally(() => {
    if (backgroundRuns.get(runId) === tracked) backgroundRuns.delete(runId);
  });
}

/** Await a background run's completion; returns the current record if it is not background-tracked. */
export async function waitForRun(db: DatabaseSync, runId: string): Promise<Run> {
  const tracked = backgroundRuns.get(runId);
  if (tracked) {
    try {
      return await tracked;
    } catch {
      // Fall through to the persisted record.
    }
  }
  return getRunOrThrow(db, runId);
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
/** Grace between the timeout's group SIGTERM and the SIGKILL escalation. */
const SCRIPT_KILL_ESCALATION_MS = 1_000;

function stepFailed(code: keyof typeof DAB_ERROR_CODES, message: string): DabError {
  return dabError(DAB_ERROR_CODES[code], message);
}

export interface ScriptRunResult {
  exitCode: number;
  stdout: string;
  stderr: string;
  killed: boolean;
  timedOut: boolean;
}

/**
 * Run an approved script. Exported for direct unit testing.
 *
 * Timeout handling is manual — NOT the `spawn` `timeout` option, which
 * signals only the immediate child: descendants in the child's (detached)
 * process group survived it and, by holding the inherited stdout/stderr
 * pipes open, prevented `close` from ever firing. On timeout this sends
 * SIGTERM to the whole process group (the same group-kill approach
 * cancellation uses, via `killChildTree`) and escalates to a group
 * SIGKILL if the tree has not exited within the escalation grace.
 */
export function runScript(
  scriptPath: string,
  args: string[],
  cwd: string,
  ctrl: ActiveRunControl,
  timeoutMs: number = SCRIPT_TIMEOUT_MS,
): Promise<ScriptRunResult> {
  return new Promise((resolvePromise) => {
    // A run cancelled before this point must never spawn: no child exists
    // for `cancelRun` to have killed, so without this recheck the script
    // would launch (and produce side effects) after cancellation.
    if (ctrl.cancelled) {
      resolvePromise({ exitCode: -1, stdout: '', stderr: '', killed: true, timedOut: false });
      return;
    }
    const child = spawn(scriptPath, args, {
      cwd,
      shell: false,
      windowsHide: true,
      // Own process group on POSIX so cancellation AND timeout can kill
      // the whole tree (a shell script's children would otherwise outlive
      // it and hold the stdio pipes open).
      detached: process.platform !== 'win32',
    });
    ctrl.child = child;
    let stdout = '';
    let stderr = '';
    let timedOut = false;
    let escalationTimer: NodeJS.Timeout | undefined;
    const timeoutTimer = setTimeout(() => {
      timedOut = true;
      signalProcessGroup(child, 'SIGTERM');
      escalationTimer = setTimeout(() => {
        signalProcessGroup(child, 'SIGKILL');
      }, SCRIPT_KILL_ESCALATION_MS);
      escalationTimer.unref();
    }, timeoutMs);
    timeoutTimer.unref();
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
      clearTimeout(timeoutTimer);
      if (escalationTimer) clearTimeout(escalationTimer);
      if (ctrl.child === child) ctrl.child = undefined;
      const killed = timedOut || signal === 'SIGKILL' || signal === 'SIGTERM';
      resolvePromise({ exitCode: code ?? -1, stdout, stderr, killed, timedOut });
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
      // Sandbox violations (lexical or via filesystem links) must surface
      // as PATH_OUTSIDE_SANDBOX, not be wrapped as a generic step failure.
      const from = await resolveInSandboxReal(wf.sandboxRoot, step.from, step.id);
      const to = await resolveInSandboxReal(wf.sandboxRoot, step.to, step.id);
      try {
        const st = await stat(from);
        if (!st.isFile()) throw new Error(`"${from}" is not a file`);
        await mkdir(dirname(to), { recursive: true });
        // Re-validate the destination now that its parent exists, so a
        // link in the destination chain can never be followed out.
        await resolveInSandboxReal(wf.sandboxRoot, step.to, step.id);
        await copyFile(from, to);
        return `Copied ${st.size} bytes: "${from}" → "${to}"`;
      } catch (err) {
        if (isDabError(err)) throw err;
        throw stepFailed('STEP_FAILED', `Step "${step.id}" file-copy failed: ${errMessage(err)}`);
      }
    }
    case 'file-move-to-trash': {
      const p = await resolveInSandboxReal(wf.sandboxRoot, step.path, step.id);
      try {
        const trashDir = await resolveInSandboxReal(wf.sandboxRoot, '.dab-trash', step.id);
        await mkdir(trashDir, { recursive: true });
        await resolveInSandboxReal(wf.sandboxRoot, '.dab-trash', step.id);
        const dest = await resolveInSandboxReal(
          wf.sandboxRoot,
          `.dab-trash/${Date.now()}-${randomUUID().slice(0, 8)}-${basename(p)}`,
          step.id,
        );
        await rename(p, dest);
        return `Moved "${p}" to trash: "${dest}" (recoverable)`;
      } catch (err) {
        if (isDabError(err)) throw err;
        throw stepFailed('STEP_FAILED', `Step "${step.id}" move-to-trash failed: ${errMessage(err)}`);
      }
    }
    case 'folder-create': {
      const p = await resolveInSandboxReal(wf.sandboxRoot, step.path, step.id);
      try {
        await mkdir(p, { recursive: true });
        // The created chain must really live inside the sandbox — a link
        // in an existing ancestor would have been caught above, and this
        // re-check guards the directories just created.
        await resolveInSandboxReal(wf.sandboxRoot, step.path, step.id);
        return `Created folder "${p}"`;
      } catch (err) {
        if (isDabError(err)) throw err;
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
      // Recheck cancellation IMMEDIATELY before spawning: a cancel that
      // arrived while `await stat(...)` was pending set `ctrl.cancelled`
      // but had no child process to kill, so without this check the script
      // would still launch and produce side effects before the post-run
      // cancellation check noticed. (`runScript` rechecks as well.)
      if (ctrl.cancelled) {
        throw stepFailed('STEP_FAILED', `Step "${step.id}" was cancelled before the script started.`);
      }
      const result = await runScript(script.path, step.args, resolve(wf.sandboxRoot), ctrl);
      if (ctrl.cancelled) {
        throw stepFailed('STEP_FAILED', `Step "${step.id}" was cancelled during script execution.`);
      }
      // Timeout BEFORE the generic killed check: a timed-out run is
      // signalled (so `killed` is true) but was NOT cancelled — it must
      // be reported as a timeout failure.
      if (result.timedOut) {
        const detail =
          `Script "${script.name}" timed out after ${Math.round(SCRIPT_TIMEOUT_MS / 1000)}s and its process group was terminated.` +
          (result.stdout ? `\nstdout:\n${truncate(result.stdout)}` : '') +
          (result.stderr ? `\nstderr:\n${truncate(result.stderr)}` : '');
        throw stepFailed('STEP_FAILED', `Step "${step.id}" script timed out.\n${detail}`);
      }
      if (result.killed) {
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

/**
 * Signal the child's whole process GROUP on POSIX (children are spawned
 * `detached`, so the child is a group leader and `-pid` reaches every
 * descendant); falls back to signalling the child directly when the group
 * is already gone or on Windows.
 */
function signalProcessGroup(child: ChildProcess, signal: 'SIGTERM' | 'SIGKILL'): void {
  const pid = child.pid;
  if (pid !== undefined && process.platform !== 'win32') {
    try {
      process.kill(-pid, signal);
      return;
    } catch {
      // Group already gone — fall through to a direct kill.
    }
  }
  try {
    child.kill(signal);
  } catch {
    // Process already exited; the executor will observe the flag.
  }
}

function killChildTree(child: ChildProcess | undefined): void {
  if (!child) return;
  signalProcessGroup(child, 'SIGKILL');
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
 * effects. approved=true → creates the `running` record, starts execution
 * in the background, and resolves IMMEDIATELY with the running record —
 * callers track progress by polling `getRun` and cancel via `cancelRun`.
 * (Blocking until execution finished made the running record — and its
 * cancel control — unreachable during long runs.)
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
  launchInBackground(db, executeRun(db, run.id), run.id);
  return getRunOrThrow(db, run.id);
}

/**
 * `startRun` + await background completion. For in-process callers that
 * genuinely need the final record (smoke mode, tests) — NOT for the IPC
 * surface, which must return the running record immediately.
 */
export async function startRunAndWait(
  db: DatabaseSync,
  workflowId: string,
  options: StartRunOptions,
): Promise<Run> {
  const run = await startRun(db, workflowId, options);
  if (run.status !== 'running') return run;
  return waitForRun(db, run.id);
}

/**
 * Execute (or resume) a run. Steps already recorded as `skipped` or
 * `succeeded` are not re-run — this is what makes retry-from-failure work.
 *
 * `workflowOverride` pins execution to a specific workflow definition
 * (used by retry, which must run the failed run's archived version, not
 * whatever the workflow has since been edited into). Without it, the
 * current workflow definition is used.
 */
export async function executeRun(
  db: DatabaseSync,
  runId: string,
  workflowOverride?: Workflow,
): Promise<Run> {
  const run = getRun(db, runId);
  if (!run) throw dabError(DAB_ERROR_CODES.RUN_NOT_FOUND, `Run not found: ${runId}`);
  const wf = workflowOverride ?? getWorkflow(db, run.workflowId);
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

/** True while at least one run is executing in this process. */
export function hasActiveRuns(): boolean {
  return activeRuns.size > 0;
}

/** IDs of the runs currently executing in this process. */
export function activeRunIds(): string[] {
  return [...activeRuns.keys()];
}

/**
 * Stop every active run and wait until each one has fully terminated —
 * child process tree killed AND final run/step state persisted.
 *
 * This is the application-shutdown path. Scripts are spawned in their
 * own (detached) POSIX process group, so merely closing the database /
 * exiting the host would leave an approved script running detached,
 * free to keep producing side effects after the app is gone. Cancelling
 * first signals the whole process group; awaiting each run then
 * guarantees the executor has written the finalized (cancelled) log
 * before the caller closes the database and exits.
 *
 * Runs that finish on their own while shutdown is in progress are
 * tolerated (their cancel attempt is a no-op). Returns the IDs that
 * were stopped (or already finishing) by this call.
 */
export async function shutdownActiveRuns(db: DatabaseSync): Promise<string[]> {
  const ids = [...new Set([...activeRuns.keys(), ...backgroundRuns.keys()])];
  for (const runId of ids) {
    try {
      cancelRun(db, runId);
    } catch {
      // Already completed / failed / cancelled in the meantime — its
      // final state is persisted, which is all shutdown needs.
    }
  }
  // Background-tracked runs: awaiting them waits for the executor's
  // final DB writes. Runs driven directly via `executeRun` (no tracked
  // promise) are covered by the active-registry poll below — the
  // executor always removes itself in a `finally` after finalizing.
  await Promise.all(ids.map((runId) => waitForRun(db, runId).catch(() => undefined)));
  while (ids.some((runId) => activeRuns.has(runId))) {
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 5));
  }
  return ids;
}

/**
 * Resolve the workflow definition AS OF `version`: the current definition
 * when the version is current, otherwise the archived snapshot taken when
 * that version was superseded. Returns null when no snapshot survives —
 * retry must then be refused rather than silently running a different
 * (never-approved) definition under the old version number.
 */
export function workflowForVersion(db: DatabaseSync, workflowId: string, version: number): Workflow | null {
  const wf = getWorkflow(db, workflowId);
  if (!wf) return null;
  if (wf.version === version) return wf;
  const snap = wf.versions.find((v) => v.version === version);
  if (!snap) return null;
  return { ...wf, name: snap.name, sandboxRoot: snap.sandboxRoot, steps: snap.steps, version: snap.version };
}

/**
 * Retry a failed run: creates a NEW run of the SAME workflow version the
 * failed run executed, with steps before the failed one marked `skipped`,
 * then resumes at the failed step. The original run is left untouched.
 *
 * The definition executed is the archived snapshot of
 * `source.workflowVersion` — never the workflow's current definition. If
 * the workflow was edited after the failure, the edits do NOT ride along:
 * they were never previewed or approved for this run, and recording them
 * under the source version would corrupt the durable log. (A fresh
 * preview/approval run of the new version is always available instead.)
 *
 * Like `startRun`, this returns the `running` record immediately and
 * executes in the background.
 */
export async function retryRun(db: DatabaseSync, runId: string): Promise<Run> {
  const source = getRunOrThrow(db, runId);
  if (source.status !== 'failed') {
    throw dabError(
      DAB_ERROR_CODES.RUN_NOT_RETRYABLE,
      `Run ${runId} is ${source.status}; only failed runs can be retried.`,
    );
  }
  const wf = workflowForVersion(db, source.workflowId, source.workflowVersion);
  if (!wf) {
    throw dabError(
      DAB_ERROR_CODES.RUN_NOT_RETRYABLE,
      `Run ${runId}: archived workflow version ${source.workflowVersion} is no longer available; ` +
        'start a fresh preview/approval run of the current version instead.',
    );
  }

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
  launchInBackground(db, executeRun(db, next.id, wf), next.id);
  return getRunOrThrow(db, next.id);
}

/** `retryRun` + await background completion (smoke mode / tests only). */
export async function retryRunAndWait(db: DatabaseSync, runId: string): Promise<Run> {
  const run = await retryRun(db, runId);
  if (run.status !== 'running') return run;
  return waitForRun(db, run.id);
}

export function isDabError(err: unknown): err is DabError {
  if (typeof err !== 'object' || err === null) return false;
  const code = (err as { code?: unknown }).code;
  const message = (err as { message?: unknown }).message;
  if (typeof code !== 'string' || typeof message !== 'string') return false;
  return (Object.values(DAB_ERROR_CODES) as string[]).includes(code);
}
