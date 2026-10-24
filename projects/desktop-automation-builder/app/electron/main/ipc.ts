// IPC handlers: one per DAB_IPC_CHANNELS entry. Every input is zod-validated
// here in the main process; failures are thrown as { code, message } using
// DAB_ERROR_CODES so the renderer can act on them.
import { stat } from 'node:fs/promises';
import { resolve } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { ZodError } from 'zod';
import {
  DAB_ERROR_CODES,
  dabError,
  type DabError,
  type DabErrorCode,
} from '../../shared/errors.js';
import type {
  DabIpcChannel,
  Run,
  Workflow,
} from '../../shared/types.js';
import { DAB_METHOD_CHANNELS } from '../preload/channels.js';
import { cancelRun, isDabError, previewWorkflow, retryRun, startRun } from './executor.js';
import {
  runIdSchema,
  runsListSchema,
  runsPreviewSchema,
  runsStartSchema,
  scriptIdSchema,
  scriptsRegisterSchema,
  stepSchema,
  workflowsCreateSchema,
  workflowsDeleteSchema,
  workflowsExportSchema,
  workflowsGetSchema,
  workflowsImportSchema,
  workflowsUpdateSchema,
} from './schemas.js';
import {
  createWorkflow,
  deleteWorkflow,
  getRun,
  getWorkflow,
  listRuns,
  listScripts,
  listWorkflows,
  registerScript,
  unregisterScript,
  updateWorkflow,
} from './store.js';
import { exportWorkflowJson, importWorkflowJson } from './transfer.js';

export interface IpcContext {
  db: DatabaseSync;
  pickDirectory: () => Promise<string | null>;
}

export interface IpcMainLike {
  handle(channel: string, listener: (event: unknown, ...args: unknown[]) => Promise<unknown>): void;
}

function toDabError(err: unknown, fallback: DabErrorCode): DabError {
  if (isDabError(err)) return { code: err.code, message: err.message };
  if (err instanceof ZodError) {
    return dabError(DAB_ERROR_CODES.WORKFLOW_INVALID, `Invalid input: ${err.message}`);
  }
  const message = err instanceof Error ? err.message : String(err);
  return dabError(fallback, message);
}

type Handler = (...args: unknown[]) => Promise<unknown>;

/** Build the handler table; `registerIpcHandlers` wires it to an ipcMain. */
export function createHandlers(ctx: IpcContext): Record<DabIpcChannel, Handler> {
  const { db } = ctx;

  const workflowsList: Handler = async () => listWorkflows(db);

  const workflowsCreate: Handler = async (...args) => {
    const [name, sandboxRoot] = workflowsCreateSchema.parse(args);
    return createWorkflow(db, { name, sandboxRoot: resolve(sandboxRoot) });
  };

  const workflowsGet: Handler = async (...args) => {
    const [id] = workflowsGetSchema.parse(args);
    return getWorkflow(db, id);
  };

  const workflowsUpdate: Handler = async (...args) => {
    const [id, patch] = workflowsUpdateSchema.parse(args);
    if (patch.steps !== undefined) {
      // Validate each step against the discriminated union up front so a bad
      // step can never be persisted.
      patch.steps.forEach((s) => stepSchema.parse(s));
    }
    const updated = updateWorkflow(db, id, {
      ...(patch.name !== undefined ? { name: patch.name } : {}),
      ...(patch.sandboxRoot !== undefined ? { sandboxRoot: resolve(patch.sandboxRoot) } : {}),
      ...(patch.steps !== undefined ? { steps: patch.steps } : {}),
    });
    if (!updated) throw dabError(DAB_ERROR_CODES.WORKFLOW_NOT_FOUND, `Workflow not found: ${id}`);
    return updated;
  };

  const workflowsDelete: Handler = async (...args) => {
    const [id] = workflowsDeleteSchema.parse(args);
    return deleteWorkflow(db, id);
  };

  const workflowsExport: Handler = async (...args) => {
    const [id] = workflowsExportSchema.parse(args);
    const wf: Workflow | null = getWorkflow(db, id);
    if (!wf) throw dabError(DAB_ERROR_CODES.WORKFLOW_NOT_FOUND, `Workflow not found: ${id}`);
    try {
      return exportWorkflowJson(wf);
    } catch (err) {
      throw dabError(
        DAB_ERROR_CODES.EXPORT_FAILED,
        `Export failed: ${err instanceof Error ? err.message : String(err)}`,
      );
    }
  };

  const workflowsImport: Handler = async (...args) => {
    const [json] = workflowsImportSchema.parse(args);
    return importWorkflowJson(db, json);
  };

  const scriptsList: Handler = async () => listScripts(db);

  const scriptsRegister: Handler = async (...args) => {
    const [name, filePath] = scriptsRegisterSchema.parse(args);
    const abs = resolve(filePath);
    let st;
    try {
      st = await stat(abs);
    } catch {
      st = null;
    }
    if (!st || !st.isFile()) {
      throw dabError(DAB_ERROR_CODES.SCRIPT_NOT_FOUND, `Script file not found: ${abs}`);
    }
    return registerScript(db, name, abs);
  };

  const scriptsUnregister: Handler = async (...args) => {
    const [id] = scriptIdSchema.parse(args);
    return unregisterScript(db, id);
  };

  const runsPreview: Handler = async (...args) => {
    const [workflowId] = runsPreviewSchema.parse(args);
    const wf = getWorkflow(db, workflowId);
    if (!wf) throw dabError(DAB_ERROR_CODES.WORKFLOW_NOT_FOUND, `Workflow not found: ${workflowId}`);
    return previewWorkflow(db, wf);
  };

  const runsStart: Handler = async (...args) => {
    const [workflowId, approved] = runsStartSchema.parse(args);
    const run: Run = await startRun(db, workflowId, { approved });
    return run;
  };

  const runsCancel: Handler = async (...args) => {
    const [runId] = runIdSchema.parse(args);
    return cancelRun(db, runId);
  };

  const runsRetry: Handler = async (...args) => {
    const [runId] = runIdSchema.parse(args);
    return retryRun(db, runId);
  };

  const runsGet: Handler = async (...args) => {
    const [runId] = runIdSchema.parse(args);
    return getRun(db, runId);
  };

  const runsList: Handler = async (...args) => {
    const [workflowId] = runsListSchema.parse(args);
    return listRuns(db, workflowId);
  };

  const pickDirectory: Handler = async () => ctx.pickDirectory();

  const byMethod: Record<keyof typeof DAB_METHOD_CHANNELS, Handler> = {
    workflowsList,
    workflowsCreate,
    workflowsGet,
    workflowsUpdate,
    workflowsDelete,
    workflowsExport,
    workflowsImport,
    scriptsList,
    scriptsRegister,
    scriptsUnregister,
    runsPreview,
    runsStart,
    runsCancel,
    runsRetry,
    runsGet,
    runsList,
    pickDirectory,
  };

  const table = {} as Record<DabIpcChannel, Handler>;
  for (const [method, channel] of Object.entries(DAB_METHOD_CHANNELS) as [
    keyof typeof DAB_METHOD_CHANNELS,
    DabIpcChannel,
  ][]) {
    const handler = byMethod[method];
    table[channel] = async (...args: unknown[]) => {
      try {
        return await handler(...args);
      } catch (err) {
        throw toDabError(err, DAB_ERROR_CODES.STEP_FAILED);
      }
    };
  }
  return table;
}

export function registerIpcHandlers(ipcMain: IpcMainLike, ctx: IpcContext): void {
  const table = createHandlers(ctx);
  for (const [channel, handler] of Object.entries(table) as [DabIpcChannel, Handler][]) {
    ipcMain.handle(channel, async (_event, ...args) => handler(...args));
  }
}
