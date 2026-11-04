import { ipcMain } from 'electron';
import { PetChannels } from '../shared/ipc-channels.js';
import { parseActionPayload } from '../shared/validation.js';
import type { IpcResult } from '../shared/api-types.js';
import { dispatchAction } from './action-dispatch.js';
import type { PetService } from './pet-service.js';

/**
 * Registers the `pet:*` invoke handlers. Every handler returns the
 * IpcResult envelope; core PetErrors become `{ ok: false, error }`
 * with the core's typed code — the UI shows them, nothing throws
 * across the boundary.
 */

export interface IpcDeps {
  service: PetService;
  openPanel: () => void;
}

function ok<T>(data: T): IpcResult<T> {
  return { ok: true, data };
}

function fail(code: string, message: string): IpcResult<never> {
  return { ok: false, error: { code, message } };
}

export function registerPetIpc(deps: IpcDeps): void {
  ipcMain.handle(PetChannels.getSummary, () => ok(deps.service.getSummary()));

  ipcMain.handle(PetChannels.events, () => ok(deps.service.getEvents(50)));

  ipcMain.handle(PetChannels.action, (_event, payload: unknown) => {
    const parsed = parseActionPayload(payload);
    if (!parsed.ok) return fail(parsed.error.code, parsed.error.message);
    return dispatchAction(deps.service, parsed.value.kind);
  });

  ipcMain.handle(PetChannels.openPanel, () => {
    deps.openPanel();
    return ok(null);
  });
}
