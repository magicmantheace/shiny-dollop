import { mkdir, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';
import type { DatabaseSync } from 'node:sqlite';
import { LACC_ERROR_CODES, isLaccError, laccError, type LaccError } from '../../shared/errors.js';
import { MAX_PROPOSAL_CHARS, MAX_PROMPT_CHARS, PROPOSE_FENCE, type AuditEntry, type EndpointConfig, type HealthResult, type Proposal, type ResourceSnapshot, type SubmitTaskInput, type Task, type TaskLogEntry } from '../../shared/types.js';
import { createAdapter, type RuntimeAdapter } from './adapter.js';
import { createDiff } from './diff.js';
import { NodeOsLayer, snapshotResources, type OsLayer } from './resources.js';
import { appendAudit, appendTaskLog, getConfig as storeGetConfig, getProposal as storeGetProposal, getTask as storeGetTask, insertProposal, insertTask, listAudit as storeListAudit, listProposals as storeListProposals, listTaskLogs, listTasks as storeListTasks, saveConfig as storeSaveConfig, updateProposalStatus, updateTask, nowIso } from './store.js';
import { readExistingFile, resolveInWorkspace } from './workspace.js';

export interface TaskEngineOptions {
  adapterFactory?: (config: EndpointConfig) => RuntimeAdapter;
  now?: () => string;
  osLayer?: OsLayer;
}

interface RunningEntry {
  controller: AbortController;
  cancelled: boolean;
  timedOut: boolean;
  promise: Promise<void>;
}

const PROPOSE_RE = new RegExp('```' + PROPOSE_FENCE + '\\s+path=([^\\s`]+)[^\\n`]*\\n([\\s\\S]*?)```', 'g');

export class TaskEngine {
  private readonly db: DatabaseSync;
  private readonly adapterFactory: (config: EndpointConfig) => RuntimeAdapter;
  private readonly nowFn: () => string;
  private readonly osLayer: OsLayer;
  private queue: string[] = [];
  private processing = false;
  private running = new Map<string, RunningEntry>();
  private idleWaiters: Array<() => void> = [];

  constructor(db: DatabaseSync, opts?: TaskEngineOptions) {
    this.db = db;
    this.adapterFactory = opts?.adapterFactory ?? ((cfg) => createAdapter(cfg));
    this.nowFn = opts?.now ?? nowIso;
    this.osLayer = opts?.osLayer ?? new NodeOsLayer();
  }

  getConfig(): EndpointConfig | null { return storeGetConfig(this.db); }
  saveConfig(cfg: EndpointConfig): EndpointConfig {
    const saved = storeSaveConfig(this.db, cfg);
    appendAudit(this.db, 'user', 'config.saved', `mode=${cfg.mode} model=${cfg.model} workspaceRoot=${cfg.workspaceRoot}`);
    return saved;
  }
  // aliases for IPC naming
  configGet = this.getConfig;
  
  private requireConfig(): EndpointConfig {
    const cfg = this.getConfig();
    if (!cfg) throw laccError(LACC_ERROR_CODES.ENDPOINT_NOT_CONFIGURED, 'No endpoint is configured. Save an endpoint configuration first.');
    return cfg;
  }

  async health(): Promise<HealthResult> {
    const cfg = this.requireConfig();
    const checkedAt = this.nowFn();
    const started = Date.now();
    const adapter = this.adapterFactory(cfg);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), cfg.timeoutMs);
    try {
      const { models } = await adapter.health(controller.signal);
      return { ok: true, mode: cfg.mode, latencyMs: Date.now() - started, models, message: null, checkedAt };
    } catch (err) {
      const message = isLaccError(err) ? err.message : err instanceof Error ? err.message : String(err);
      const code = isLaccError(err) ? err.code : LACC_ERROR_CODES.ADAPTER_ERROR;
      // health never throws for adapter failures
      return { ok: false, mode: cfg.mode, latencyMs: null, models: [], message: `${code}: ${message}`, checkedAt };
    } finally { clearTimeout(timer); }
  }

  async models(): Promise<string[]> {
    const cfg = this.requireConfig();
    const adapter = this.adapterFactory(cfg);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), cfg.timeoutMs);
    try {
      const { models } = await adapter.health(controller.signal);
      return models;
    } catch (err) {
      if (isLaccError(err)) throw err;
      if (err instanceof Error && err.name === 'AbortError') throw laccError(LACC_ERROR_CODES.ENDPOINT_TIMEOUT, `Health probe to ${cfg.baseUrl} timed out.`);
      throw laccError(LACC_ERROR_CODES.ADAPTER_ERROR, err instanceof Error ? err.message : String(err));
    } finally { clearTimeout(timer); }
  }
  endpointModels = this.models;

  submit(input: SubmitTaskInput): Task {
    if (!input || typeof input.prompt !== 'string' || input.prompt.trim().length === 0) {
      throw laccError(LACC_ERROR_CODES.TASK_INVALID, 'Task prompt must be a non-empty string.');
    }
    if (input.prompt.length > MAX_PROMPT_CHARS) {
      throw laccError(LACC_ERROR_CODES.INPUT_TOO_LARGE, `Task prompt exceeds the maximum of ${MAX_PROMPT_CHARS} characters.`);
    }
    const cfg = this.requireConfig();
    const model = input.model ?? cfg.model;
    const task = insertTask(this.db, { prompt: input.prompt, model, workspaceRoot: cfg.workspaceRoot });
    appendAudit(this.db, 'user', 'task.submitted', `task=${task.id} model=${model}`);
    this.queue.push(task.id);
    void this.kick();
    return task;
  }

  listTasks(): Task[] { return storeListTasks(this.db); }
  getTask(id: string): Task {
    const t = storeGetTask(this.db, id);
    if (!t) throw laccError(LACC_ERROR_CODES.TASK_NOT_FOUND, `Task not found: ${id}`);
    return t;
  }
  getTaskOrNull(id: string): Task | null { return storeGetTask(this.db, id); }
  listTaskLogs(id: string): TaskLogEntry[] { this.getTask(id); return listTaskLogs(this.db, id); }
  tasksLogs = this.listTaskLogs;

  async cancel(id: string): Promise<Task> {
    const task = storeGetTask(this.db, id);
    if (!task) throw laccError(LACC_ERROR_CODES.TASK_NOT_FOUND, `Task not found: ${id}`);
    if (task.status === 'queued') {
      this.queue = this.queue.filter((q) => q !== id);
      const updated = updateTask(this.db, id, { status: 'cancelled', finishedAt: this.nowFn() })!;
      appendAudit(this.db, 'user', 'task.cancelled', `task=${id} (queued)`);
      this.notifyIdle();
      return updated;
    }
    if (task.status === 'running') {
      const entry = this.running.get(id);
      if (entry) {
        entry.cancelled = true;
        entry.controller.abort();
        await entry.promise;
      }
      const after = storeGetTask(this.db, id)!;
      return after;
    }
    throw laccError(LACC_ERROR_CODES.TASK_NOT_CANCELLABLE, `Task ${id} is already ${task.status} and cannot be cancelled.`);
  }

  listProposals(): Proposal[] { return storeListProposals(this.db); }
  getProposal(id: string): Proposal {
    const p = storeGetProposal(this.db, id);
    if (!p) throw laccError(LACC_ERROR_CODES.PROPOSAL_NOT_FOUND, `Proposal not found: ${id}`);
    return p;
  }

  async approve(id: string): Promise<Proposal> {
    const proposal = storeGetProposal(this.db, id);
    if (!proposal) throw laccError(LACC_ERROR_CODES.PROPOSAL_NOT_FOUND, `Proposal not found: ${id}`);
    if (proposal.status !== 'pending') throw laccError(LACC_ERROR_CODES.PROPOSAL_NOT_PENDING, `Proposal ${id} is already ${proposal.status}.`);
    const task = storeGetTask(this.db, proposal.taskId);
    if (!task) throw laccError(LACC_ERROR_CODES.PROPOSAL_NOT_FOUND, `Proposal ${id} references a missing task.`);
    const full = resolveInWorkspace(task.workspaceRoot, proposal.relativePath);
    await mkdir(dirname(full), { recursive: true });
    await writeFile(full, proposal.proposedContent, 'utf8');
    const updated = updateProposalStatus(this.db, id, 'approved')!;
    appendAudit(this.db, 'user', 'proposal.approved', `proposal=${id} path=${proposal.relativePath}`);
    appendAudit(this.db, 'system', 'proposal.applied', `proposal=${id} path=${proposal.relativePath}`);
    return updated;
  }
  async reject(id: string): Promise<Proposal> {
    const proposal = storeGetProposal(this.db, id);
    if (!proposal) throw laccError(LACC_ERROR_CODES.PROPOSAL_NOT_FOUND, `Proposal not found: ${id}`);
    if (proposal.status !== 'pending') throw laccError(LACC_ERROR_CODES.PROPOSAL_NOT_PENDING, `Proposal ${id} is already ${proposal.status}.`);
    const updated = updateProposalStatus(this.db, id, 'rejected')!;
    appendAudit(this.db, 'user', 'proposal.rejected', `proposal=${id} path=${proposal.relativePath}`);
    return updated;
  }
  // aliases
  approveProposal = this.approve;
  rejectProposal = this.reject;

  listAudit(limit?: number): AuditEntry[] { return storeListAudit(this.db, limit); }
  auditList = this.listAudit;
  resourcesSnapshot(): ResourceSnapshot { return snapshotResources(this.osLayer); }
  snapshotResources(): ResourceSnapshot { return this.resourcesSnapshot(); }

  async whenIdle(): Promise<void> {
    while (this.processing || this.queue.length > 0 || this.running.size > 0) {
      await new Promise<void>((resolve) => this.idleWaiters.push(resolve));
    }
  }
  private notifyIdle(): void {
    const waiters = this.idleWaiters.splice(0);
    waiters.forEach((w) => w());
  }

  private async kick(): Promise<void> {
    if (this.processing) return;
    this.processing = true;
    try {
      while (this.queue.length > 0) {
        const id = this.queue.shift()!;
        const task = storeGetTask(this.db, id);
        if (!task || task.status !== 'queued') continue;
        const entryPromise = this.runTask(id);
        // runTask registers itself in running map synchronously before first await? Ensure map set inside runTask start.
        await entryPromise;
      }
    } finally {
      this.processing = false;
      this.notifyIdle();
    }
  }

  private async runTask(id: string): Promise<void> {
    const cfg = this.getConfig();
    const initial = storeGetTask(this.db, id);
    if (!initial || !cfg) return;
    const controller = new AbortController();
    const entry: RunningEntry = { controller, cancelled: false, timedOut: false, promise: Promise.resolve() };
    this.running.set(id, entry);
    entry.promise = (async () => {
      // actual work is in runTaskBody; this wrapper is replaced below
    })();
    // We run body directly and store its promise:
    const bodyPromise = this.runTaskBody(id, cfg, entry);
    entry.promise = bodyPromise;
    // Also update map entry promise for cancel() awaiters that already captured? cancel reads entry.promise at call time, so fine.
    try { await bodyPromise; } finally { this.running.delete(id); this.notifyIdle(); }
  }

  private async runTaskBody(id: string, cfg: EndpointConfig, entry: RunningEntry): Promise<void> {
    const controller = entry.controller;
    updateTask(this.db, id, { status: 'running', startedAt: this.nowFn() });
    appendTaskLog(this.db, id, 'info', 'Task started');
    const task = storeGetTask(this.db, id)!;
    const adapter = this.adapterFactory(cfg);
    let chunkCount = 0; let chunkChars = 0;
    const timeoutTimer = setTimeout(() => { entry.timedOut = true; controller.abort(); }, cfg.timeoutMs);
    // Abort race promise
    let abortReject: ((e: Error) => void) | null = null;
    const abortPromise = new Promise<never>((_res, rej) => { abortReject = rej; });
    const onAbort = () => { const e = new Error('The operation was aborted'); e.name = 'AbortError'; abortReject?.(e); };
    if (controller.signal.aborted) onAbort(); else controller.signal.addEventListener('abort', onAbort, { once: true });
    try {
      const result = await Promise.race([
        adapter.generate({
          model: task.model, prompt: task.prompt, signal: controller.signal,
          onChunk: (text: string) => { chunkCount++; chunkChars += text.length; },
        }),
        abortPromise,
      ]);
      clearTimeout(timeoutTimer);
      appendTaskLog(this.db, id, 'adapter', `Adapter produced ${chunkCount} chunk(s), ${chunkChars} chars`);
      appendTaskLog(this.db, id, 'info', 'Task completed');
      updateTask(this.db, id, { status: 'completed', output: result.text, error: null, finishedAt: this.nowFn() });
      // Proposals extraction
      this.extractProposals(id, task.workspaceRoot, result.text);
    } catch (err) {
      clearTimeout(timeoutTimer);
      if (entry.cancelled) {
        appendTaskLog(this.db, id, 'info', 'Task cancelled by user');
        updateTask(this.db, id, { status: 'cancelled', finishedAt: this.nowFn() });
        appendAudit(this.db, 'user', 'task.cancelled', `task=${id} (running)`);
      } else if (entry.timedOut) {
        const msg = `${LACC_ERROR_CODES.ENDPOINT_TIMEOUT}: Request to the local model endpoint timed out after ${cfg.timeoutMs}ms.`;
        appendTaskLog(this.db, id, 'error', msg);
        updateTask(this.db, id, { status: 'failed', error: msg, finishedAt: this.nowFn() });
      } else if (isLaccError(err)) {
        const le = err as LaccError;
        const msg = `${le.code}: ${le.message}`;
        appendTaskLog(this.db, id, 'error', msg);
        updateTask(this.db, id, { status: 'failed', error: msg, finishedAt: this.nowFn() });
      } else if (err instanceof Error && err.name === 'AbortError') {
        // Abort without cancel/timeout flags: treat as timeout if timedOut else cancelled? Default to timeout message when timeoutMs elapsed not known.
        // If entry flags not set, this is adapter's own abort — map to ENDPOINT_TIMEOUT
        const msg = `${LACC_ERROR_CODES.ENDPOINT_TIMEOUT}: Request was aborted.`;
        appendTaskLog(this.db, id, 'error', msg);
        updateTask(this.db, id, { status: 'failed', error: msg, finishedAt: this.nowFn() });
      } else {
        const msg = `${LACC_ERROR_CODES.ADAPTER_ERROR}: ${err instanceof Error ? err.message : String(err)}`;
        appendTaskLog(this.db, id, 'error', msg);
        updateTask(this.db, id, { status: 'failed', error: msg, finishedAt: this.nowFn() });
      }
    } finally {
      clearTimeout(timeoutTimer);
      controller.signal.removeEventListener('abort', onAbort);
    }
  }

  private extractProposals(taskId: string, workspaceRoot: string, output: string): void {
    PROPOSE_RE.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = PROPOSE_RE.exec(output)) !== null) {
      const rawPath = match[1]!.replace(/^["']|["']$/g, '');
      const content = match[2]!;
      // containment
      try {
        resolveInWorkspace(workspaceRoot, rawPath);
      } catch (err) {
        const msg = isLaccError(err) ? err.message : String(err);
        appendTaskLog(this.db, taskId, 'error', `Proposal rejected: path outside workspace (${rawPath}): ${msg}`);
        appendAudit(this.db, 'system', 'proposal.rejected-path', `task=${taskId} path=${rawPath}`);
        continue;
      }
      if (content.length > MAX_PROPOSAL_CHARS) {
        appendTaskLog(this.db, taskId, 'error', `Proposal skipped: content for ${rawPath} exceeds ${MAX_PROPOSAL_CHARS} chars`);
        continue;
      }
      const existing = readExistingFile(workspaceRoot, rawPath);
      const diff = createDiff(rawPath, existing, content);
      const proposal = insertProposal(this.db, { taskId, relativePath: rawPath, proposedContent: content, diff });
      appendAudit(this.db, 'system', 'proposal.created', `proposal=${proposal.id} task=${taskId} path=${rawPath}`);
    }
  }
}
