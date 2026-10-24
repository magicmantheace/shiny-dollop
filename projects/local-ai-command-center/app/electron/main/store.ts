// SQLite persistence (node:sqlite). Audit is append-only via triggers.
import { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import type { AuditEntry, EndpointConfig, Proposal, ProposalStatus, Task, TaskLogEntry, TaskStatus } from '../../shared/types.js';

export const SCHEMA_VERSION = 1;
export function nowIso(): string { return new Date().toISOString(); }

const MIGRATIONS = `
CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY CHECK (id = 1), json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, prompt TEXT NOT NULL, model TEXT NOT NULL, workspace_root TEXT NOT NULL,
  status TEXT NOT NULL, output TEXT, error TEXT, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT);
CREATE TABLE IF NOT EXISTS task_logs (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL, seq INTEGER NOT NULL, ts TEXT NOT NULL, level TEXT NOT NULL, message TEXT NOT NULL,
  UNIQUE(task_id, seq));
CREATE TABLE IF NOT EXISTS proposals (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL, relative_path TEXT NOT NULL, proposed_content TEXT NOT NULL,
  diff TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, decided_at TEXT);
CREATE TABLE IF NOT EXISTS audit (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, ts TEXT NOT NULL, actor TEXT NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
CREATE INDEX IF NOT EXISTS idx_task_logs_task ON task_logs(task_id, seq);
CREATE INDEX IF NOT EXISTS idx_audit_seq ON audit(seq);
`;

export function openDatabase(dbPath: string): DatabaseSync {
  const db = new DatabaseSync(dbPath);
  db.exec('PRAGMA journal_mode = WAL;');
  db.exec('PRAGMA foreign_keys = ON;');
  db.exec(MIGRATIONS);
  return db;
}
export function transact<T>(db: DatabaseSync, fn: () => T): T {
  db.exec('BEGIN IMMEDIATE;');
  try { const r = fn(); db.exec('COMMIT;'); return r; } catch (e) { try { db.exec('ROLLBACK;'); } catch { /* ignore */ } throw e; }
}

// config
export function getConfig(db: DatabaseSync): EndpointConfig | null {
  const row = db.prepare('SELECT json FROM config WHERE id = 1').get() as unknown as { json: string } | undefined;
  return row ? (JSON.parse(row.json) as EndpointConfig) : null;
}
export function saveConfig(db: DatabaseSync, cfg: EndpointConfig): EndpointConfig {
  db.prepare('INSERT INTO config (id, json) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET json = excluded.json').run(JSON.stringify(cfg));
  return cfg;
}

// tasks
interface TaskRow { id: string; prompt: string; model: string; workspace_root: string; status: string; output: string | null; error: string | null; created_at: string; started_at: string | null; finished_at: string | null; }
function rowToTask(r: TaskRow): Task {
  return { id: r.id, prompt: r.prompt, model: r.model, workspaceRoot: r.workspace_root, status: r.status as TaskStatus, output: r.output, error: r.error, createdAt: r.created_at, startedAt: r.started_at, finishedAt: r.finished_at };
}
export function insertTask(db: DatabaseSync, input: { prompt: string; model: string; workspaceRoot: string }): Task {
  const id = randomUUID(); const ts = nowIso();
  db.prepare('INSERT INTO tasks (id,prompt,model,workspace_root,status,output,error,created_at,started_at,finished_at) VALUES (?,?,?,?,?,?,?,?,?,?)')
    .run(id, input.prompt, input.model, input.workspaceRoot, 'queued', null, null, ts, null, null);
  return getTask(db, id)!;
}
export function getTask(db: DatabaseSync, id: string): Task | null {
  const row = db.prepare('SELECT * FROM tasks WHERE id = ?').get(id) as unknown as TaskRow | undefined;
  return row ? rowToTask(row) : null;
}
export function listTasks(db: DatabaseSync): Task[] {
  const rows = db.prepare('SELECT * FROM tasks ORDER BY created_at ASC, rowid ASC').all() as unknown as TaskRow[];
  return rows.map(rowToTask);
}
export interface UpdateTaskPatch { status?: TaskStatus; output?: string | null; error?: string | null; startedAt?: string | null; finishedAt?: string | null; model?: string; }
export function updateTask(db: DatabaseSync, id: string, patch: UpdateTaskPatch): Task | null {
  const cur = getTask(db, id); if (!cur) return null;
  const next = { ...cur, ...patch };
  db.prepare('UPDATE tasks SET status=?, output=?, error=?, started_at=?, finished_at=?, model=? WHERE id=?')
    .run(next.status, next.output, next.error, next.startedAt, next.finishedAt, next.model, id);
  return getTask(db, id);
}

// logs
interface LogRow { id: string; task_id: string; seq: number; ts: string; level: string; message: string; }
export function appendTaskLog(db: DatabaseSync, taskId: string, level: TaskLogEntry['level'], message: string): TaskLogEntry {
  const id = randomUUID(); const ts = nowIso();
  const maxRow = db.prepare('SELECT COALESCE(MAX(seq),0) AS m FROM task_logs WHERE task_id=?').get(taskId) as unknown as { m: number };
  const seq = Number(maxRow.m) + 1;
  db.prepare('INSERT INTO task_logs (id,task_id,seq,ts,level,message) VALUES (?,?,?,?,?,?)').run(id, taskId, seq, ts, level, message);
  return { id, taskId, seq, ts, level, message };
}
export function listTaskLogs(db: DatabaseSync, taskId: string): TaskLogEntry[] {
  const rows = db.prepare('SELECT * FROM task_logs WHERE task_id=? ORDER BY seq ASC').all(taskId) as unknown as LogRow[];
  return rows.map((r) => ({ id: r.id, taskId: r.task_id, seq: r.seq, ts: r.ts, level: r.level as TaskLogEntry['level'], message: r.message }));
}

// proposals
interface PropRow { id: string; task_id: string; relative_path: string; proposed_content: string; diff: string; status: string; created_at: string; decided_at: string | null; }
function rowToProposal(r: PropRow): Proposal {
  return { id: r.id, taskId: r.task_id, relativePath: r.relative_path, proposedContent: r.proposed_content, diff: r.diff, status: r.status as ProposalStatus, createdAt: r.created_at, decidedAt: r.decided_at };
}
export function insertProposal(db: DatabaseSync, input: { taskId: string; relativePath: string; proposedContent: string; diff: string }): Proposal {
  const id = randomUUID(); const ts = nowIso();
  db.prepare('INSERT INTO proposals (id,task_id,relative_path,proposed_content,diff,status,created_at,decided_at) VALUES (?,?,?,?,?,?,?,?)')
    .run(id, input.taskId, input.relativePath, input.proposedContent, input.diff, 'pending', ts, null);
  return getProposal(db, id)!;
}
export function getProposal(db: DatabaseSync, id: string): Proposal | null {
  const row = db.prepare('SELECT * FROM proposals WHERE id=?').get(id) as unknown as PropRow | undefined;
  return row ? rowToProposal(row) : null;
}
export function listProposals(db: DatabaseSync): Proposal[] {
  const rows = db.prepare('SELECT * FROM proposals ORDER BY created_at ASC, rowid ASC').all() as unknown as PropRow[];
  return rows.map(rowToProposal);
}
export function updateProposalStatus(db: DatabaseSync, id: string, status: ProposalStatus): Proposal | null {
  const ts = nowIso();
  db.prepare('UPDATE proposals SET status=?, decided_at=? WHERE id=?').run(status, ts, id);
  return getProposal(db, id);
}

// audit
interface AuditRow { id: string; seq: number; ts: string; actor: string; event: string; detail: string; }
export function appendAudit(db: DatabaseSync, actor: AuditEntry['actor'], event: string, detail: string): AuditEntry {
  const id = randomUUID(); const ts = nowIso();
  const res = db.prepare('INSERT INTO audit (id,ts,actor,event,detail) VALUES (?,?,?,?,?)').run(id, ts, actor, event, detail);
  return { id, seq: Number(res.lastInsertRowid), ts, actor, event, detail };
}
export function listAudit(db: DatabaseSync, limit?: number): AuditEntry[] {
  const lim = limit !== undefined ? Math.max(1, Math.min(500, Math.trunc(limit))) : 500;
  const rows = db.prepare('SELECT * FROM audit ORDER BY seq DESC LIMIT ?').all(lim) as unknown as AuditRow[];
  return rows.reverse().map((r) => ({ id: r.id, seq: r.seq, ts: r.ts, actor: r.actor as AuditEntry['actor'], event: r.event, detail: r.detail }));
}
