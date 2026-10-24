import type {
  AuditEntry,
  EndpointConfig,
  HealthResult,
  LaccApi,
  Proposal,
  ResourceSnapshot,
  Task,
  TaskLogEntry,
} from '../../shared/types';

export function sampleConfig(): EndpointConfig {
  return {
    mode: 'mock',
    baseUrl: 'http://127.0.0.1:11434',
    model: 'llama3',
    timeoutMs: 15_000,
    workspaceRoot: '/workspace/demo',
  };
}

export function sampleResources(): ResourceSnapshot {
  return {
    cpuCount: 8,
    cpuModel: 'Test CPU 3000',
    loadAvg1m: 0.42,
    totalMemBytes: 16 * 1024 ** 3,
    freeMemBytes: 4 * 1024 ** 3,
    gpu: {
      status: 'unavailable',
      reason: 'GPU detection is not available in this build',
    },
    sampledAt: '2026-10-23T18:00:00.000Z',
  };
}

export function sampleHealth(overrides: Partial<HealthResult> = {}): HealthResult {
  return {
    ok: true,
    mode: 'mock',
    latencyMs: 12,
    models: ['llama3', 'mistral'],
    message: null,
    checkedAt: '2026-10-23T18:00:00.000Z',
    ...overrides,
  };
}

export function sampleTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-1',
    prompt: 'Summarise the readme',
    model: 'llama3',
    workspaceRoot: '/workspace/demo',
    status: 'completed',
    output: 'The readme describes the project.',
    error: null,
    createdAt: '2026-10-23T18:01:00.000Z',
    startedAt: '2026-10-23T18:01:01.000Z',
    finishedAt: '2026-10-23T18:01:05.000Z',
    ...overrides,
  };
}

export function sampleProposal(
  overrides: Partial<Proposal> = {},
): Proposal {
  return {
    id: 'prop-1',
    taskId: 'task-1',
    relativePath: 'notes/todo.txt',
    proposedContent: 'hello from the model\n',
    diff: '--- a/notes/todo.txt\n+++ b/notes/todo.txt\n@@ -0,0 +1 @@\n+hello from the model',
    originalHash: null,
    status: 'pending',
    createdAt: '2026-10-23T18:02:00.000Z',
    decidedAt: null,
    ...overrides,
  };
}

export function sampleAuditEntry(
  overrides: Partial<AuditEntry> = {},
): AuditEntry {
  return {
    id: 'audit-1',
    seq: 1,
    ts: '2026-10-23T18:03:00.000Z',
    actor: 'user',
    event: 'task.submitted',
    detail: 'Task task-1 submitted',
    ...overrides,
  };
}

export function sampleLogEntry(
  overrides: Partial<TaskLogEntry> = {},
): TaskLogEntry {
  return {
    id: 'log-1',
    taskId: 'task-1',
    seq: 1,
    ts: '2026-10-23T18:01:01.000Z',
    level: 'info',
    message: 'Task started',
    ...overrides,
  };
}

export interface FakeState {
  config: EndpointConfig | null;
  health: HealthResult;
  models: string[];
  tasks: Task[];
  proposals: Proposal[];
  audit: AuditEntry[];
  logs: Record<string, TaskLogEntry[]>;
  resources: ResourceSnapshot;
  pickedDirectory: string | null;
}

export interface FakeOptions {
  config?: EndpointConfig | null;
  health?: HealthResult;
  models?: string[];
  tasks?: Task[];
  proposals?: Proposal[];
  audit?: AuditEntry[];
  logs?: Record<string, TaskLogEntry[]>;
  resources?: ResourceSnapshot;
  pickedDirectory?: string | null;
  overrides?: Partial<LaccApi>;
}

export interface InstalledFake {
  api: LaccApi;
  calls: string[];
  callArgs: Record<string, unknown[]>;
  state: FakeState;
}

/**
 * Installs a hand-rolled fake window.lacc backed by in-memory state. Every
 * method records its name in `calls` and its arguments in `callArgs` before
 * running, unless replaced via `overrides`.
 */
export function installFakeLacc(options: FakeOptions = {}): InstalledFake {
  const calls: string[] = [];
  const callArgs: Record<string, unknown[]> = {};

  const state: FakeState = {
    config: options.config === undefined ? sampleConfig() : options.config,
    health: options.health ?? sampleHealth(),
    models: options.models ?? ['llama3', 'mistral'],
    tasks: options.tasks ?? [sampleTask()],
    proposals: options.proposals ?? [sampleProposal()],
    audit: options.audit ?? [sampleAuditEntry()],
    logs: options.logs ?? { 'task-1': [sampleLogEntry()] },
    resources: options.resources ?? sampleResources(),
    pickedDirectory:
      options.pickedDirectory === undefined
        ? '/workspace/picked'
        : options.pickedDirectory,
  };

  const wrap = <F extends (...args: never[]) => Promise<unknown>>(
    name: string,
    impl: F,
  ): F =>
    (async (...args: never[]) => {
      calls.push(name);
      (callArgs[name] ??= []).push(args);
      return impl(...args);
    }) as F;

  let taskCounter = 100;
  let auditSeq = 1000;
  const addAudit = (event: string, detail: string) => {
    state.audit = [
      {
        id: `audit-${++auditSeq}`,
        seq: auditSeq,
        ts: '2026-10-23T18:10:00.000Z',
        actor: 'user',
        event,
        detail,
      },
      ...state.audit,
    ];
  };

  const defaults: LaccApi = {
    configGet: wrap('configGet', async () =>
      state.config ? { ...state.config } : null,
    ),
    configSave: wrap('configSave', async (config: EndpointConfig) => {
      state.config = { ...config };
      addAudit('config.saved', 'Configuration saved');
      return { ...state.config };
    }),
    endpointHealth: wrap('endpointHealth', async () => ({ ...state.health })),
    endpointModels: wrap('endpointModels', async () => [...state.models]),
    tasksSubmit: wrap(
      'tasksSubmit',
      async (input: { prompt: string; model?: string }) => {
        const task: Task = {
          id: `task-${++taskCounter}`,
          prompt: input.prompt,
          model: input.model ?? state.config?.model ?? 'llama3',
          workspaceRoot: state.config?.workspaceRoot ?? '/workspace/demo',
          status: 'completed',
          output: `Mock output for: ${input.prompt}`,
          error: null,
          createdAt: '2026-10-23T18:05:00.000Z',
          startedAt: '2026-10-23T18:05:00.000Z',
          finishedAt: '2026-10-23T18:05:01.000Z',
        };
        state.tasks = [task, ...state.tasks];
        state.logs[task.id] = [
          sampleLogEntry({
            id: `log-${task.id}`,
            taskId: task.id,
            message: 'Task completed by the mock adapter',
          }),
        ];
        addAudit('task.submitted', `Task ${task.id} submitted`);
        return { ...task };
      },
    ),
    tasksList: wrap('tasksList', async () =>
      state.tasks.map((t) => ({ ...t })),
    ),
    tasksGet: wrap('tasksGet', async (id: string) => {
      const task = state.tasks.find((t) => t.id === id);
      if (!task) throw { code: 'TASK_NOT_FOUND', message: `No task ${id}` };
      return { ...task };
    }),
    tasksCancel: wrap('tasksCancel', async (id: string) => {
      const task = state.tasks.find((t) => t.id === id);
      if (!task) throw { code: 'TASK_NOT_FOUND', message: `No task ${id}` };
      if (task.status !== 'queued' && task.status !== 'running') {
        throw {
          code: 'TASK_NOT_CANCELLABLE',
          message: `Task ${id} is ${task.status} and cannot be cancelled`,
        };
      }
      const updated: Task = {
        ...task,
        status: 'cancelled',
        finishedAt: '2026-10-23T18:06:00.000Z',
      };
      state.tasks = state.tasks.map((t) => (t.id === id ? updated : t));
      addAudit('task.cancelled', `Task ${id} cancelled`);
      return { ...updated };
    }),
    tasksLogs: wrap('tasksLogs', async (id: string) =>
      (state.logs[id] ?? []).map((e) => ({ ...e })),
    ),
    proposalsList: wrap('proposalsList', async () =>
      state.proposals.map((p) => ({ ...p })),
    ),
    proposalsGet: wrap('proposalsGet', async (id: string) => {
      const proposal = state.proposals.find((p) => p.id === id);
      if (!proposal)
        throw { code: 'PROPOSAL_NOT_FOUND', message: `No proposal ${id}` };
      return { ...proposal };
    }),
    proposalsApprove: wrap('proposalsApprove', async (id: string) => {
      const proposal = state.proposals.find((p) => p.id === id);
      if (!proposal)
        throw { code: 'PROPOSAL_NOT_FOUND', message: `No proposal ${id}` };
      const updated: Proposal = {
        ...proposal,
        status: 'approved',
        decidedAt: '2026-10-23T18:07:00.000Z',
      };
      state.proposals = state.proposals.map((p) =>
        p.id === id ? updated : p,
      );
      addAudit('proposal.approved', `Proposal ${id} approved`);
      return { ...updated };
    }),
    proposalsReject: wrap('proposalsReject', async (id: string) => {
      const proposal = state.proposals.find((p) => p.id === id);
      if (!proposal)
        throw { code: 'PROPOSAL_NOT_FOUND', message: `No proposal ${id}` };
      const updated: Proposal = {
        ...proposal,
        status: 'rejected',
        decidedAt: '2026-10-23T18:07:00.000Z',
      };
      state.proposals = state.proposals.map((p) =>
        p.id === id ? updated : p,
      );
      addAudit('proposal.rejected', `Proposal ${id} rejected`);
      return { ...updated };
    }),
    auditList: wrap('auditList', async (limit?: number) =>
      state.audit.slice(0, limit ?? 50).map((e) => ({ ...e })),
    ),
    resourcesSnapshot: wrap('resourcesSnapshot', async () => ({
      ...state.resources,
    })),
    pickDirectory: wrap('pickDirectory', async () => state.pickedDirectory),
  };

  const api: LaccApi = { ...defaults, ...(options.overrides ?? {}) };

  Object.defineProperty(window, 'lacc', {
    value: api,
    configurable: true,
    writable: true,
  });
  return { api, calls, callArgs, state };
}
