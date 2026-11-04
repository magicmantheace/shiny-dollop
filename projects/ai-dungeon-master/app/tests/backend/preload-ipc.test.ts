import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AIDM_ERROR_CODES, aidmError } from '../../shared/errors.js';
import type { AidmApi } from '../../shared/types.js';

const bridge = vi.hoisted(() => ({
  api: undefined as AidmApi | undefined,
  invoke: vi.fn(),
}));

vi.mock('electron', () => ({
  contextBridge: {
    exposeInMainWorld: (_name: string, api: unknown) => {
      bridge.api = api as AidmApi;
    },
  },
  ipcRenderer: {
    invoke: bridge.invoke,
  },
}));

import '../../electron/preload/preload.js';

describe('preload IPC envelope unwrapping', () => {
  beforeEach(() => {
    bridge.invoke.mockReset();
  });

  it('returns the value from a successful IPC envelope', async () => {
    bridge.invoke.mockResolvedValue({ ok: true, value: [{ id: 'camp-1', name: 'One' }] });
    await expect(bridge.api?.campaignsList()).resolves.toEqual([{ id: 'camp-1', name: 'One' }]);
    expect(bridge.invoke).toHaveBeenCalledWith('aidm:campaigns-list');
  });

  it('rejects with the structured AidmError from a failed IPC envelope', async () => {
    const error = aidmError(AIDM_ERROR_CODES.DICE_NOTATION_INVALID, 'Dice notation is invalid.');
    bridge.invoke.mockResolvedValue({ ok: false, error });
    await expect(
      bridge.api?.diceRoll('camp-1', { notation: 'banana' }),
    ).rejects.toEqual(error);
    expect(bridge.invoke).toHaveBeenCalledWith('aidm:dice-roll', 'camp-1', {
      notation: 'banana',
    });
  });
});
