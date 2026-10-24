import { contextBridge, ipcRenderer } from 'electron';
import type {
  AuditEntry,
  EndpointConfig,
  HealthResult,
  LaccApi,
  LaccMethodName,
  Proposal,
  ResourceSnapshot,
  SubmitTaskInput,
  Task,
  TaskLogEntry,
} from '../../shared/types.js';

// Sandboxed preload: Electron's sandboxed renderer only allows requiring
// `electron` (and a few built-ins) — it cannot require local modules such as
// `./channels.js` or `../../shared/types.js`. The channel map is therefore
// inlined here so the compiled preload.js is a single self-contained script
// whose only runtime require is `electron`. This map MUST stay identical to
// LACC_IPC_CHANNELS in shared/types.ts (guarded by tests/backend/preload.test.ts);
// main-process code continues to import the canonical map via channels.ts.
const LACC_METHOD_CHANNELS: Record<LaccMethodName, string> = {
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

// The main side returns a structured envelope as data —
// { ok: true, value } | { ok: false, error: { code, message } } — because a
// { code, message } object THROWN through ipcMain.handle loses its code
// (Electron forwards only the message). Unwrap it here so renderer callers
// keep the declared API contract: success values directly, failures as a
// thrown { code, message }.
type IpcEnvelope<T> =
  | { ok: true; value: T }
  | { ok: false; error: { code: string; message: string } };

async function invoke<T>(channel: string, ...args: unknown[]): Promise<T> {
  const result = (await ipcRenderer.invoke(channel, ...args)) as
    | IpcEnvelope<T>
    | T;
  if (
    result !== null &&
    typeof result === 'object' &&
    'ok' in result &&
    typeof (result as { ok: unknown }).ok === 'boolean'
  ) {
    const env = result as IpcEnvelope<T>;
    if (env.ok) return env.value;
    throw env.error;
  }
  // Not an envelope (should not happen with the current main side): pass
  // the value through untouched rather than breaking the call.
  return result as T;
}

const lacc: LaccApi = {
  configGet: () => invoke<EndpointConfig | null>(LACC_METHOD_CHANNELS.configGet),
  configSave: (config) => invoke<EndpointConfig>(LACC_METHOD_CHANNELS.configSave, config),
  endpointHealth: () => invoke<HealthResult>(LACC_METHOD_CHANNELS.endpointHealth),
  endpointModels: () => invoke<string[]>(LACC_METHOD_CHANNELS.endpointModels),
  tasksSubmit: (input: SubmitTaskInput) => invoke<Task>(LACC_METHOD_CHANNELS.tasksSubmit, input),
  tasksList: () => invoke<Task[]>(LACC_METHOD_CHANNELS.tasksList),
  tasksGet: (id) => invoke<Task>(LACC_METHOD_CHANNELS.tasksGet, id),
  tasksCancel: (id) => invoke<Task>(LACC_METHOD_CHANNELS.tasksCancel, id),
  tasksLogs: (id) => invoke<TaskLogEntry[]>(LACC_METHOD_CHANNELS.tasksLogs, id),
  proposalsList: () => invoke<Proposal[]>(LACC_METHOD_CHANNELS.proposalsList),
  proposalsGet: (id) => invoke<Proposal>(LACC_METHOD_CHANNELS.proposalsGet, id),
  proposalsApprove: (id) => invoke<Proposal>(LACC_METHOD_CHANNELS.proposalsApprove, id),
  proposalsReject: (id) => invoke<Proposal>(LACC_METHOD_CHANNELS.proposalsReject, id),
  auditList: (limit) => invoke<AuditEntry[]>(LACC_METHOD_CHANNELS.auditList, limit),
  resourcesSnapshot: () => invoke<ResourceSnapshot>(LACC_METHOD_CHANNELS.resourcesSnapshot),
  pickDirectory: () => invoke<string | null>(LACC_METHOD_CHANNELS.pickDirectory),
};
contextBridge.exposeInMainWorld('lacc', lacc);
