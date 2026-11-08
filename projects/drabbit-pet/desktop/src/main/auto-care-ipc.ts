import { ipcMain } from 'electron';
import { AutoCareChannels } from '../shared/ipc-channels.js';
import { parseSetEnabledPayload } from '../shared/validation.js';
import type { AutoCareState, IpcResult } from '../shared/api-types.js';
import type { AutoCareService } from './auto-care.js';

/**
 * Registers the `autocare:*` invoke handlers. Same envelope style
 * as the other handlers.
 */

function ok(data: AutoCareState): IpcResult<AutoCareState> {
  return { ok: true, data };
}

function fail(code: string, message: string): IpcResult<never> {
  return { ok: false, error: { code, message } };
}

export function registerAutoCareIpc(deps: { autoCare: AutoCareService }): void {
  const { autoCare } = deps;

  ipcMain.handle(AutoCareChannels.getState, () => ok(autoCare.getState()));

  ipcMain.handle(AutoCareChannels.setEnabled, (_event, payload: unknown) => {
    const parsed = parseSetEnabledPayload(payload);
    if (!parsed.ok) return fail(parsed.error.code, parsed.error.message);
    return ok(autoCare.setEnabled(parsed.value.enabled));
  });
}
