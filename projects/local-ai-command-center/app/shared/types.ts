// Shared domain contract for the Local AI Command Center.
// The renderer only ever sees these types via the flat `window.lacc` API
// (LaccApi below); the main process validates every input with zod before
// it reaches the store/engine.

/** 'live' talks HTTP to the configured loopback endpoint; 'mock' is the
 * deterministic offline adapter used for setup mode and tests. */
export type AdapterMode = 'live' | 'mock';

export interface EndpointConfig {
  mode: AdapterMode;
  /** Base URL of the local runtime, e.g. http://127.0.0.1:11434 (Ollama-style).
   * Loopback hosts only — the app never calls a non-local address. */
  baseUrl: string;
  /** Selected model name; must be one the endpoint reports (or mock list). */
  model: string;
  /** Per-request timeout in milliseconds (100..120000). */
  timeoutMs: number;
  /** Absolute path of the scoped workspace root tasks/proposals are bound to. */
  workspaceRoot: string;
}

export interface HealthResult {
  ok: boolean;
  mode: AdapterMode;
  /** Round-trip time of the health probe; null when the probe never answered. */
  latencyMs: number | null;
  models: string[];
  /** Actionable explanation when ok is false; null when ok. */
  message: string | null;
  checkedAt: string;
}

export type TaskStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface Task {
  id: string;
  prompt: string;
  model: string;
  workspaceRoot: string;
  status: TaskStatus;
  /** Model output text; null until the task completes. */
  output: string | null;
  /** Actionable failure reason (named-code message); null unless failed. */
  error: string | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export type TaskLogLevel = 'info' | 'adapter' | 'error';

export interface TaskLogEntry {
  id: string;
  taskId: string;
  seq: number;
  ts: string;
  level: TaskLogLevel;
  message: string;
}

export type ProposalStatus = 'pending' | 'approved' | 'rejected';

/**
 * A proposed file change produced by a task. A proposal is NEVER written to
 * disk while pending or after rejection; only an explicit approval applies
 * it, and only to `relativePath` resolved inside the task's workspace root.
 */
export interface Proposal {
  id: string;
  taskId: string;
  /** Path relative to the workspace root (never absolute, never escaping). */
  relativePath: string;
  /** Full proposed new file content. */
  proposedContent: string;
  /** Unified-diff-style text of existing content -> proposed content. */
  diff: string;
  /**
   * SHA-256 hex hash of the target file's content at the moment the diff
   * was created; null when the file did not exist then. Approval re-reads
   * the file and refuses to apply the proposal (PROPOSAL_FILE_CHANGED)
   * when the current content no longer matches this hash, so an edit made
   * while the proposal was pending is never silently overwritten.
   */
  originalHash: string | null;
  status: ProposalStatus;
  createdAt: string;
  decidedAt: string | null;
}

export type AuditActor = 'user' | 'system';

export interface AuditEntry {
  id: string;
  seq: number;
  ts: string;
  actor: AuditActor;
  /** e.g. 'config.saved', 'task.submitted', 'task.cancelled',
   * 'proposal.approved', 'proposal.rejected', 'proposal.applied'. */
  event: string;
  detail: string;
}

export interface GpuSnapshot {
  status: 'unavailable';
  /** Honest reason GPU figures are not reported (never fabricated). */
  reason: string;
}

export interface ResourceSnapshot {
  cpuCount: number;
  cpuModel: string;
  /** 1-minute load average; null on platforms that do not report one. */
  loadAvg1m: number | null;
  totalMemBytes: number;
  freeMemBytes: number;
  gpu: GpuSnapshot;
  sampledAt: string;
}

export interface SubmitTaskInput {
  prompt: string;
  /** Optional model override; defaults to the configured model. */
  model?: string;
}

/** Flat preload API exposed as `window.lacc`. */
export interface LaccApi {
  configGet(): Promise<EndpointConfig | null>;
  configSave(config: EndpointConfig): Promise<EndpointConfig>;
  endpointHealth(): Promise<HealthResult>;
  endpointModels(): Promise<string[]>;
  tasksSubmit(input: SubmitTaskInput): Promise<Task>;
  tasksList(): Promise<Task[]>;
  tasksGet(id: string): Promise<Task>;
  tasksCancel(id: string): Promise<Task>;
  tasksLogs(id: string): Promise<TaskLogEntry[]>;
  proposalsList(): Promise<Proposal[]>;
  proposalsGet(id: string): Promise<Proposal>;
  proposalsApprove(id: string): Promise<Proposal>;
  proposalsReject(id: string): Promise<Proposal>;
  auditList(limit?: number): Promise<AuditEntry[]>;
  resourcesSnapshot(): Promise<ResourceSnapshot>;
  pickDirectory(): Promise<string | null>;
}

export type LaccMethodName = keyof LaccApi;

export const LACC_IPC_CHANNELS: Record<LaccMethodName, string> = {
  configGet: 'lacc:config-get',
  configSave: 'lacc:config-save',
  endpointHealth: 'lacc:endpoint-health',
  endpointModels: 'lacc:endpoint-models',
  tasksSubmit: 'lacc:tasks-submit',
  tasksList: 'lacc:tasks-list',
  tasksGet: 'lacc:tasks-get',
  tasksCancel: 'lacc:tasks-cancel',
  tasksLogs: 'lacc:tasks-logs',
  proposalsList: 'lacc:proposals-list',
  proposalsGet: 'lacc:proposals-get',
  proposalsApprove: 'lacc:proposals-approve',
  proposalsReject: 'lacc:proposals-reject',
  auditList: 'lacc:audit-list',
  resourcesSnapshot: 'lacc:resources-snapshot',
  pickDirectory: 'lacc:pick-directory',
};

/** Maximum accepted task prompt length (characters). */
export const MAX_PROMPT_CHARS = 32_000;
/** Maximum accepted proposed file content length (characters). */
export const MAX_PROPOSAL_CHARS = 200_000;

/**
 * Proposal convention: when a model response contains a fenced block of the
 * form
 *
 *     ```propose path=relative/file.txt
 *     <full proposed file content>
 *     ```
 *
 * the engine turns it into a pending Proposal for human review. The path is
 * untrusted model output: it is containment-checked against the workspace
 * root before the proposal is stored, and the content is only ever written
 * to disk after an explicit user approval.
 */
export const PROPOSE_FENCE = 'propose';
