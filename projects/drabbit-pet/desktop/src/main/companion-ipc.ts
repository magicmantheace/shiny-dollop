import { ipcMain } from 'electron';
import { CompanionChannels } from '../shared/ipc-channels.js';
import { parseSetEnabledPayload } from '../shared/validation.js';
import type { CompanionState, IpcResult } from '../shared/api-types.js';
import type { CompanionService } from './server/companion-service.js';

/**
 * Registers the `companion:*` invoke handlers. Same envelope style as
 * the pet handlers: lifecycle outcomes (including a bind failure)
 * come back as CompanionState data, never as thrown errors.
 */

function ok(data: CompanionState): IpcResult<CompanionState> {
  return { ok: true, data };
}

function fail(code: string, message: string): IpcResult<never> {
  return { ok: false, error: { code, message } };
}

export function registerCompanionIpc(deps: { companion: CompanionService }): void {
  const { companion } = deps;

  ipcMain.handle(CompanionChannels.getState, () => ok(companion.getState()));

  ipcMain.handle(CompanionChannels.setEnabled, async (_event, payload: unknown) => {
    const parsed = parseSetEnabledPayload(payload);
    if (!parsed.ok) return fail(parsed.error.code, parsed.error.message);
    return ok(await companion.setEnabled(parsed.value.enabled));
  });

  ipcMain.handle(CompanionChannels.regenerateToken, async () =>
    ok(await companion.regenerateToken()),
  );
}
