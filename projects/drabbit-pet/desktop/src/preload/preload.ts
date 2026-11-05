/**
 * Preload script. Runs sandboxed; exposes ONLY the narrow typed
 * `window.drabbit` API — no raw ipcRenderer, no Node APIs.
 *
 * NOTE: a sandboxed preload may only require `electron`, so the
 * channel names are inlined here instead of imported from
 * src/shared/ipc-channels.ts. Keep them in sync — the values must
 * match PetChannels exactly.
 */
import { contextBridge, ipcRenderer, type IpcRendererEvent } from 'electron';
import type {
  ActionKind,
  ActionOutcome,
  BridgeReaction,
  ChangedEvent,
  CompanionState,
  DrabbitApi,
  IpcResult,
  PetSummary,
  RoamState,
} from '../shared/api-types.js';
import type { PetEvent } from 'drabbit-core';

const CH = {
  getSummary: 'pet:getSummary',
  action: 'pet:action',
  events: 'pet:events',
  openPanel: 'pet:openPanel',
  changed: 'pet:changed',
  roamState: 'pet:roamState',
  bridgeReaction: 'pet:bridgeReaction',
  companionGetState: 'companion:getState',
  companionSetEnabled: 'companion:setEnabled',
  companionRegenerateToken: 'companion:regenerateToken',
} as const;

async function invoke<T>(channel: string, payload?: unknown): Promise<T> {
  const result = (await ipcRenderer.invoke(channel, payload)) as IpcResult<T>;
  if (!result || typeof result !== 'object' || !('ok' in result)) {
    throw new Error('Malformed IPC response.');
  }
  if (!result.ok) {
    const err = new Error(result.error.message) as Error & { code: string };
    err.code = result.error.code;
    throw err;
  }
  return result.data;
}

const api: DrabbitApi = {
  getSummary: () => invoke<PetSummary>(CH.getSummary),
  getEvents: () => invoke<PetEvent[]>(CH.events),
  action: (kind: ActionKind) => invoke<ActionOutcome>(CH.action, { kind }),
  openPanel: () => invoke<null>(CH.openPanel).then(() => undefined),
  onChanged: (cb) => {
    const listener = (_e: IpcRendererEvent, payload: ChangedEvent) => cb(payload);
    ipcRenderer.on(CH.changed, listener);
    return () => {
      ipcRenderer.removeListener(CH.changed, listener);
    };
  },
  onRoamState: (cb) => {
    const listener = (_e: IpcRendererEvent, payload: RoamState) => cb(payload);
    ipcRenderer.on(CH.roamState, listener);
    return () => {
      ipcRenderer.removeListener(CH.roamState, listener);
    };
  },
  onBridgeReaction: (cb) => {
    const listener = (_e: IpcRendererEvent, payload: BridgeReaction) => cb(payload);
    ipcRenderer.on(CH.bridgeReaction, listener);
    return () => {
      ipcRenderer.removeListener(CH.bridgeReaction, listener);
    };
  },
  getCompanionState: () => invoke<CompanionState>(CH.companionGetState),
  setCompanionEnabled: (enabled: boolean) =>
    invoke<CompanionState>(CH.companionSetEnabled, { enabled }),
  regenerateCompanionToken: () => invoke<CompanionState>(CH.companionRegenerateToken),
};

contextBridge.exposeInMainWorld('drabbit', api);
