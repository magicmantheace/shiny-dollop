// SQLite persistence for the Desktop Automation Builder (main process).
// Uses node:sqlite (Node 22+) with explicit BEGIN/COMMIT/ROLLBACK —
// node:sqlite provides no transaction helper, so every multi-statement
// write is wrapped manually.
import { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import type {
  ApprovedScript,
  Run,
  RunStatus,
  Step,
  StepLog,
  StepOutcome,
  Workflow,
  WorkflowVersionSnapshot,
} from '../../shared/types.js';

export const SCHEMA_VERSION = 1;

const MIGRATIONS = `
CREATE TABLE IF NOT EXISTS workflows (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  sandbox_root TEXT NOT NULL,
  steps_json TEXT NOT NULL,
  version INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_versions (
  workflow_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (workflow_id, version)
);
CREATE TABLE IF NOT EXISTS approved_scripts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  path TEXT NOT NULL,
  approved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL,
  workflow_version INTEGER NOT NULL,
  status TEXT NOT NULL,
  dry_run INTEGER NOT NULL,
  started_at TEXT,
  finished_at TEXT
);
CREATE TABLE IF NOT EXISTS run_steps (
  run_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  step_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  label TEXT NOT NULL,
  outcome TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  detail TEXT,
  PRIMARY KEY (run_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_runs_workflow ON runs (workflow_id);
`;

export function nowIso(): string {
  return new Date().toISOString();
}

export function openDatabase(dbPath: string): DatabaseSync {
  const db = new DatabaseSync(dbPath);
  db.exec('PRAGMA journal_mode = WAL;');
  db.exec('PRAGMA foreign_keys = ON;');
  db.exec(MIGRATIONS);
  return db;
}

/** Run fn inside an explicit transaction; rolls back on throw. */
export function transact<T>(db: DatabaseSync, fn: () => T): T {
  db.exec('BEGIN IMMEDIATE;');
  try {
    const result = fn();
    db.exec('COMMIT;');
    return result;
  } catch (err) {
    try {
      db.exec('ROLLBACK;');
    } catch {
      // Already rolled back / no transaction — preserve the original error.
    }
    throw err;
  }
}

// ---------------------------------------------------------------------------
// Row mapping
// ---------------------------------------------------------------------------

interface WorkflowRow {
  id: string;
  name: string;
  sandbox_root: string;
  steps_json: string;
  version: number;
  created_at: string;
  updated_at: string;
}

interface VersionRow {
  workflow_id: string;
  version: number;
  snapshot_json: string;
  created_at: string;
}

function parseSteps(json: string): Step[] {
  const parsed: unknown = JSON.parse(json);
  if (!Array.isArray(parsed)) throw new Error('steps_json is not an array');
  return parsed as Step[];
}

export function listWorkflowVersions(db: DatabaseSync, workflowId: string): WorkflowVersionSnapshot[] {
  const rows = db
    .prepare('SELECT * FROM workflow_versions WHERE workflow_id = ? ORDER BY version ASC')
    .all(workflowId) as unknown as VersionRow[];
  return rows.map((r) => {
    const snap = JSON.parse(r.snapshot_json) as {
      name: string;
      sandboxRoot: string;
      steps: Step[];
    };
    return {
      version: r.version,
      name: snap.name,
      sandboxRoot: snap.sandboxRoot,
      steps: snap.steps,
      createdAt: r.created_at,
    };
  });
}

export function rowToWorkflow(db: DatabaseSync, row: WorkflowRow): Workflow {
  return {
    id: row.id,
    name: row.name,
    sandboxRoot: row.sandbox_root,
    steps: parseSteps(row.steps_json),
    version: row.version,
    versions: listWorkflowVersions(db, row.id),
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

// ---------------------------------------------------------------------------
// Workflows
// ---------------------------------------------------------------------------

export interface CreateWorkflowInput {
  name: string;
  sandboxRoot: string;
}

export function createWorkflow(db: DatabaseSync, input: CreateWorkflowInput): Workflow {
  const id = randomUUID();
  const ts = nowIso();
  db.prepare(
    'INSERT INTO workflows (id, name, sandbox_root, steps_json, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
  ).run(id, input.name, input.sandboxRoot, '[]', 1, ts, ts);
  const row = db.prepare('SELECT * FROM workflows WHERE id = ?').get(id) as unknown as WorkflowRow;
  return rowToWorkflow(db, row);
}

export function getWorkflow(db: DatabaseSync, id: string): Workflow | null {
  const row = db.prepare('SELECT * FROM workflows WHERE id = ?').get(id) as unknown as WorkflowRow | undefined;
  return row ? rowToWorkflow(db, row) : null;
}

export function listWorkflows(db: DatabaseSync): Workflow[] {
  const rows = db.prepare('SELECT * FROM workflows ORDER BY updated_at DESC').all() as unknown as WorkflowRow[];
  return rows.map((r) => rowToWorkflow(db, r));
}

export interface UpdateWorkflowPatch {
  name?: string;
  sandboxRoot?: string;
  steps?: Step[];
}

/**
 * Archives the current {name, sandboxRoot, steps} into workflow_versions,
 * then applies the patch and bumps version. Returns null when missing.
 */
export function updateWorkflow(
  db: DatabaseSync,
  id: string,
  patch: UpdateWorkflowPatch,
): Workflow | null {
  return transact(db, () => {
    const current = db.prepare('SELECT * FROM workflows WHERE id = ?').get(id) as unknown as
      | WorkflowRow
      | undefined;
    if (!current) return null;
    const snapshot = JSON.stringify({
      name: current.name,
      sandboxRoot: current.sandbox_root,
      steps: parseSteps(current.steps_json),
    });
    db.prepare(
      'INSERT OR REPLACE INTO workflow_versions (workflow_id, version, snapshot_json, created_at) VALUES (?, ?, ?, ?)',
    ).run(id, current.version, snapshot, nowIso());
    const next = {
      name: patch.name ?? current.name,
      sandboxRoot: patch.sandboxRoot ?? current.sandbox_root,
      stepsJson: patch.steps !== undefined ? JSON.stringify(patch.steps) : current.steps_json,
      version: current.version + 1,
      updatedAt: nowIso(),
    };
    db.prepare(
      'UPDATE workflows SET name = ?, sandbox_root = ?, steps_json = ?, version = ?, updated_at = ? WHERE id = ?',
    ).run(next.name, next.sandboxRoot, next.stepsJson, next.version, next.updatedAt, id);
    const row = db.prepare('SELECT * FROM workflows WHERE id = ?').get(id) as unknown as WorkflowRow;
    return rowToWorkflow(db, row);
  });
}

export function deleteWorkflow(db: DatabaseSync, id: string): boolean {
  return transact(db, () => {
    db.prepare('DELETE FROM workflow_versions WHERE workflow_id = ?').run(id);
    const res = db.prepare('DELETE FROM workflows WHERE id = ?').run(id);
    return res.changes > 0;
  });
}

/** Replace a workflow's identity + steps wholesale (used by import). */
export function insertWorkflowWithId(
  db: DatabaseSync,
  wf: { name: string; sandboxRoot: string; steps: Step[]; version: number },
): Workflow {
  const id = randomUUID();
  const ts = nowIso();
  db.prepare(
    'INSERT INTO workflows (id, name, sandbox_root, steps_json, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
  ).run(id, wf.name, wf.sandboxRoot, JSON.stringify(wf.steps), wf.version, ts, ts);
  const row = db.prepare('SELECT * FROM workflows WHERE id = ?').get(id) as unknown as WorkflowRow;
  return rowToWorkflow(db, row);
}

// ---------------------------------------------------------------------------
// Approved scripts
// ---------------------------------------------------------------------------

interface ScriptRow {
  id: string;
  name: string;
  path: string;
  approved_at: string;
}

function rowToScript(row: ScriptRow): ApprovedScript {
  return { id: row.id, name: row.name, path: row.path, approvedAt: row.approved_at };
}

export function registerScript(db: DatabaseSync, name: string, filePath: string): ApprovedScript {
  const id = randomUUID();
  const ts = nowIso();
  db.prepare('INSERT INTO approved_scripts (id, name, path, approved_at) VALUES (?, ?, ?, ?)').run(
    id,
    name,
    filePath,
    ts,
  );
  return { id, name, path: filePath, approvedAt: ts };
}

export function unregisterScript(db: DatabaseSync, id: string): boolean {
  return db.prepare('DELETE FROM approved_scripts WHERE id = ?').run(id).changes > 0;
}

export function listScripts(db: DatabaseSync): ApprovedScript[] {
  const rows = db.prepare('SELECT * FROM approved_scripts ORDER BY approved_at ASC').all() as unknown as ScriptRow[];
  return rows.map(rowToScript);
}

export function getScript(db: DatabaseSync, id: string): ApprovedScript | null {
  const row = db.prepare('SELECT * FROM approved_scripts WHERE id = ?').get(id) as unknown as
    | ScriptRow
    | undefined;
  return row ? rowToScript(row) : null;
}

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

interface RunRow {
  id: string;
  workflow_id: string;
  workflow_version: number;
  status: string;
  dry_run: number;
  started_at: string | null;
  finished_at: string | null;
}

interface RunStepRow {
  run_id: string;
  seq: number;
  step_id: string;
  kind: string;
  label: string;
  outcome: string;
  started_at: string | null;
  finished_at: string | null;
  detail: string | null;
}

export function rowToRun(db: DatabaseSync, row: RunRow): Run {
  const stepRows = db
    .prepare('SELECT * FROM run_steps WHERE run_id = ? ORDER BY seq ASC')
    .all(row.id) as unknown as RunStepRow[];
  const steps: StepLog[] = stepRows.map((s) => {
    const log: StepLog = {
      stepId: s.step_id,
      kind: s.kind as StepLog['kind'],
      label: s.label,
      outcome: s.outcome as StepOutcome,
    };
    if (s.started_at !== null) log.startedAt = s.started_at;
    if (s.finished_at !== null) log.finishedAt = s.finished_at;
    if (s.detail !== null) log.detail = s.detail;
    return log;
  });
  const run: Run = {
    id: row.id,
    workflowId: row.workflow_id,
    workflowVersion: row.workflow_version,
    status: row.status as RunStatus,
    steps,
    dryRun: row.dry_run === 1,
  };
  if (row.started_at !== null) run.startedAt = row.started_at;
  if (row.finished_at !== null) run.finishedAt = row.finished_at;
  return run;
}

export interface CreateRunInput {
  workflowId: string;
  workflowVersion: number;
  status: RunStatus;
  dryRun: boolean;
  /** Pre-seeded step rows (pending for a fresh run; skipped for retry prefix). */
  steps: { stepId: string; kind: string; label: string; outcome: StepOutcome }[];
}

export function createRun(db: DatabaseSync, input: CreateRunInput): Run {
  const id = randomUUID();
  const startedAt = input.status === 'running' || input.status === 'awaiting-approval' ? nowIso() : null;
  transact(db, () => {
    db.prepare(
      'INSERT INTO runs (id, workflow_id, workflow_version, status, dry_run, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, NULL)',
    ).run(id, input.workflowId, input.workflowVersion, input.status, input.dryRun ? 1 : 0, startedAt);
    const stmt = db.prepare(
      'INSERT INTO run_steps (run_id, seq, step_id, kind, label, outcome, started_at, finished_at, detail) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL)',
    );
    input.steps.forEach((s, seq) => {
      stmt.run(id, seq, s.stepId, s.kind, s.label, s.outcome);
    });
  });
  const row = db.prepare('SELECT * FROM runs WHERE id = ?').get(id) as unknown as RunRow;
  return rowToRun(db, row);
}

export function getRun(db: DatabaseSync, id: string): Run | null {
  const row = db.prepare('SELECT * FROM runs WHERE id = ?').get(id) as unknown as RunRow | undefined;
  return row ? rowToRun(db, row) : null;
}

export function listRuns(db: DatabaseSync, workflowId?: string): Run[] {
  const rows =
    workflowId !== undefined
      ? (db.prepare('SELECT * FROM runs WHERE workflow_id = ? ORDER BY started_at DESC').all(workflowId) as unknown as RunRow[])
      : (db.prepare('SELECT * FROM runs ORDER BY started_at DESC').all() as unknown as RunRow[]);
  return rows.map((r) => rowToRun(db, r));
}

export function setRunStatus(
  db: DatabaseSync,
  runId: string,
  status: RunStatus,
  finished: boolean,
): void {
  if (finished) {
    db.prepare('UPDATE runs SET status = ?, finished_at = ? WHERE id = ?').run(status, nowIso(), runId);
  } else {
    db.prepare('UPDATE runs SET status = ? WHERE id = ?').run(status, runId);
  }
}

export interface StepLogUpdate {
  outcome: StepOutcome;
  started?: boolean;
  finished?: boolean;
  detail?: string;
}

export function updateRunStep(db: DatabaseSync, runId: string, seq: number, update: StepLogUpdate): void {
  const sets: string[] = ['outcome = ?'];
  const params: (string | number)[] = [update.outcome];
  if (update.started) {
    sets.push('started_at = ?');
    params.push(nowIso());
  }
  if (update.finished) {
    sets.push('finished_at = ?');
    params.push(nowIso());
  }
  if (update.detail !== undefined) {
    sets.push('detail = ?');
    params.push(update.detail);
  }
  params.push(runId, seq);
  db.prepare(`UPDATE run_steps SET ${sets.join(', ')} WHERE run_id = ? AND seq = ?`).run(...params);
}

export function closeDatabase(db: DatabaseSync): void {
  db.close();
}
