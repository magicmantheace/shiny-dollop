// Shared contract — Desktop Automation Builder.
// Canonical source of truth. Both the backend (Electron main) and the
// renderer import these types. The backend worker owns this file's evolution;
// the renderer worker must not fork it.

export type StepKind =
  | 'file-copy'
  | 'file-move-to-trash'
  | 'folder-create'
  | 'run-approved-script'
  | 'log-message';

export interface StepBase {
  id: string;
  label: string;
}

export interface FileCopyStep extends StepBase {
  kind: 'file-copy';
  /** Path relative to the workflow's sandboxRoot (or absolute — still confined). */
  from: string;
  to: string;
}

export interface FileMoveToTrashStep extends StepBase {
  kind: 'file-move-to-trash';
  /** Path to move. Never deleted outright: moved into the sandbox's .dab-trash folder. */
  path: string;
}

export interface FolderCreateStep extends StepBase {
  kind: 'folder-create';
  path: string;
}

export interface RunApprovedScriptStep extends StepBase {
  kind: 'run-approved-script';
  /** Must match an entry in the approved-script allowlist. */
  scriptId: string;
  args: string[];
}

export interface LogMessageStep extends StepBase {
  kind: 'log-message';
  message: string;
}

export type Step =
  | FileCopyStep
  | FileMoveToTrashStep
  | FolderCreateStep
  | RunApprovedScriptStep
  | LogMessageStep;

export interface WorkflowVersionSnapshot {
  version: number;
  name: string;
  sandboxRoot: string;
  steps: Step[];
  createdAt: string;
}

export interface Workflow {
  id: string;
  name: string;
  sandboxRoot: string;
  steps: Step[];
  version: number;
  versions: WorkflowVersionSnapshot[];
  createdAt: string;
  updatedAt: string;
}

export interface ApprovedScript {
  id: string;
  name: string;
  path: string;
  approvedAt: string;
}

export type StepOutcome =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'skipped'
  | 'cancelled';

export interface StepLog {
  stepId: string;
  kind: StepKind;
  label: string;
  outcome: StepOutcome;
  startedAt?: string;
  finishedAt?: string;
  /** Human-readable detail: bytes copied, script exit code, error text, … */
  detail?: string;
}

export type RunStatus =
  | 'pending'
  | 'awaiting-approval'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface Run {
  id: string;
  workflowId: string;
  workflowVersion: number;
  status: RunStatus;
  steps: StepLog[];
  startedAt?: string;
  finishedAt?: string;
  dryRun: boolean;
}

export interface PreviewAction {
  stepId: string;
  kind: StepKind;
  label: string;
  /** Plain-language description of what the step would do. */
  description: string;
}

/**
 * Flat window.dab preload API. Every method returns a Promise.
 * Errors are thrown as DabError-shaped objects { code, message }.
 */
export interface DabApi {
  workflowsList(): Promise<Workflow[]>;
  workflowsCreate(name: string, sandboxRoot: string): Promise<Workflow>;
  workflowsGet(id: string): Promise<Workflow | null>;
  workflowsUpdate(
    id: string,
    patch: { name?: string; sandboxRoot?: string; steps?: Step[] },
  ): Promise<Workflow>;
  workflowsDelete(id: string): Promise<boolean>;
  workflowsExport(id: string): Promise<string>;
  workflowsImport(json: string): Promise<Workflow>;
  scriptsList(): Promise<ApprovedScript[]>;
  scriptsRegister(name: string, filePath: string): Promise<ApprovedScript>;
  scriptsUnregister(id: string): Promise<boolean>;
  /** Dry-run: returns planned actions, writes nothing to the filesystem. */
  runsPreview(workflowId: string): Promise<PreviewAction[]>;
  /**
   * approved=false → returns the run in `awaiting-approval` with preview,
   * no side effects. approved=true → creates the run, starts execution in
   * the background, and resolves immediately with the `running` record;
   * poll runsGet / cancel with runsCancel while it executes. Throws
   * APPROVAL_REQUIRED when a step is destructive-ish and approval was
   * not given.
   */
  runsStart(workflowId: string, approved: boolean): Promise<Run>;
  runsCancel(runId: string): Promise<Run>;
  /**
   * New run resuming from the failed step of a failed run, executing the
   * failed run's archived workflow version (never a later edit). Resolves
   * immediately with the `running` record, like runsStart.
   */
  runsRetry(runId: string): Promise<Run>;
  runsGet(runId: string): Promise<Run | null>;
  runsList(workflowId?: string): Promise<Run[]>;
  pickDirectory(): Promise<string | null>;
}

export const DAB_IPC_CHANNELS = [
  'dab:workflows:list',
  'dab:workflows:create',
  'dab:workflows:get',
  'dab:workflows:update',
  'dab:workflows:delete',
  'dab:workflows:export',
  'dab:workflows:import',
  'dab:scripts:list',
  'dab:scripts:register',
  'dab:scripts:unregister',
  'dab:runs:preview',
  'dab:runs:start',
  'dab:runs:cancel',
  'dab:runs:retry',
  'dab:runs:get',
  'dab:runs:list',
  'dab:dialog:pick-directory',
] as const;

export type DabIpcChannel = (typeof DAB_IPC_CHANNELS)[number];
