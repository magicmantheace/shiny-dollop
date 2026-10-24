import { ZodError } from 'zod';
import { LACC_ERROR_CODES, isLaccError, laccError, type LaccError, type LaccErrorCode } from '../../shared/errors.js';
import type { LaccMethodName } from '../../shared/types.js';
import { LACC_METHOD_CHANNELS } from '../preload/channels.js';
import type { TaskEngine } from './engine.js';
import { auditListSchema, configSaveSchema, proposalsApproveSchema, proposalsGetSchema, proposalsRejectSchema, tasksCancelSchema, tasksGetSchema, tasksLogsSchema, tasksSubmitSchema } from './schemas.js';

export interface IpcMainLike {
  handle(channel: string, listener: (event: unknown, ...args: unknown[]) => Promise<unknown>): void;
}
export type DialogPicker = () => Promise<string | null>;
type Handler = (...args: unknown[]) => Promise<unknown>;

function toPlain(err: unknown, fallback: LaccErrorCode): LaccError {
  if (isLaccError(err)) return { code: err.code, message: err.message };
  if (err instanceof ZodError) return laccError(fallback, `Invalid input: ${err.issues.map((i) => i.message).join('; ') || err.message}`);
  return laccError(fallback, err instanceof Error ? err.message : String(err));
}

export function createHandlers(engine: TaskEngine, pickDirectory: DialogPicker): Record<string, Handler> {
  const byMethod: Record<LaccMethodName, Handler> = {
    configGet: async () => engine.getConfig(),
    configSave: async (...args) => {
      try { const [cfg] = configSaveSchema.parse(args); return engine.saveConfig(cfg); }
      catch (e) { if (e instanceof ZodError) throw laccError(LACC_ERROR_CODES.CONFIG_INVALID, `Invalid input: ${e.issues.map((i) => i.message).join('; ')}`); throw e; }
    },
    endpointHealth: async () => engine.health(),
    endpointModels: async () => engine.models(),
    tasksSubmit: async (...args) => {
      try { const [parsed] = tasksSubmitSchema.parse(args); const input = parsed.model !== undefined ? { prompt: parsed.prompt, model: parsed.model } : { prompt: parsed.prompt }; return engine.submit(input); }
      catch (e) { if (e instanceof ZodError) throw laccError(LACC_ERROR_CODES.TASK_INVALID, `Invalid input: ${e.issues.map((i) => i.message).join('; ')}`); throw e; }
    },
    tasksList: async () => engine.listTasks(),
    tasksGet: async (...args) => { const [id] = tasksGetSchema.parse(args); return engine.getTask(id); },
    tasksCancel: async (...args) => { const [id] = tasksCancelSchema.parse(args); return engine.cancel(id); },
    tasksLogs: async (...args) => { const [id] = tasksLogsSchema.parse(args); return engine.listTaskLogs(id); },
    proposalsList: async () => engine.listProposals(),
    proposalsGet: async (...args) => { const [id] = proposalsGetSchema.parse(args); return engine.getProposal(id); },
    proposalsApprove: async (...args) => { const [id] = proposalsApproveSchema.parse(args); return engine.approve(id); },
    proposalsReject: async (...args) => { const [id] = proposalsRejectSchema.parse(args); return engine.reject(id); },
    auditList: async (...args) => {
      // auditList may be called with no args or [undefined]
      const filtered = args.length === 0 || args[0] === undefined ? [] : args;
      if (filtered.length === 0) return engine.listAudit();
      const [limit] = auditListSchema.parse(filtered);
      return engine.listAudit(limit);
    },
    resourcesSnapshot: async () => engine.resourcesSnapshot(),
    pickDirectory: async () => pickDirectory(),
  };
  const table: Record<string, Handler> = {};
  for (const [method, channel] of Object.entries(LACC_METHOD_CHANNELS) as [LaccMethodName, string][]) {
    const handler = byMethod[method];
    const fallback: LaccErrorCode = method === 'configSave' ? LACC_ERROR_CODES.CONFIG_INVALID : method === 'tasksSubmit' ? LACC_ERROR_CODES.TASK_INVALID : LACC_ERROR_CODES.ADAPTER_ERROR;
    table[channel] = async (...args: unknown[]) => {
      try { return await handler(...args); } catch (err) { throw toPlain(err, fallback); }
    };
  }
  // Ensure LACC_METHOD_CHANNELS is same mapping
  void LACC_METHOD_CHANNELS;
  return table;
}

export function registerIpcHandlers(ipcMain: IpcMainLike, engine: TaskEngine, dialogPicker?: DialogPicker): void {
  const picker: DialogPicker = dialogPicker ?? (async () => null);
  const table = createHandlers(engine, picker);
  for (const [channel, handler] of Object.entries(table)) {
    ipcMain.handle(channel, async (_event, ...args) => handler(...args));
  }
}
