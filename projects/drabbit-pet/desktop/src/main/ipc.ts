import { ipcMain } from 'electron';
import { PetError } from 'drabbit-core';
import { PetChannels } from '../shared/ipc-channels.js';
import { parseActionPayload } from '../shared/validation.js';
import type { IpcResult } from '../shared/api-types.js';
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
    try {
      return ok(deps.service.doAction(parsed.value.kind));
    } catch (err) {
      if (err instanceof PetError) return fail(err.code, err.message);
      return fail('internal', err instanceof Error ? err.message : String(err));
    }
  });

  ipcMain.handle(PetChannels.openPanel, () => {
    deps.openPanel();
    return ok(null);
  });
}
