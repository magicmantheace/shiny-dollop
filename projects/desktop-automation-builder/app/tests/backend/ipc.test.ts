// IPC surface: channel coverage, zod validation, and { code, message } errors.
// Uses a fake ipcMain — the handlers themselves are the real ones.
import { mkdirSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { DAB_IPC_CHANNELS, type DabApi, type DabIpcChannel } from '../../shared/types.js';
import { createHandlers, registerIpcHandlers, type IpcMainLike } from '../../electron/main/ipc.js';
import {
  DAB_METHOD_CHANNELS,
  assertChannelCoverage,
} from '../../electron/preload/channels.js';
import { makeFixture, type Fixture } from './helpers.js';

let fx: Fixture;

type Listener = (event: unknown, ...args: unknown[]) => Promise<unknown>;

beforeEach(() => {
  fx = makeFixture();
  mkdirSync(fx.sandbox, { recursive: true });
});

afterEach(() => fx.cleanup());

function wireHandlers(): Map<string, Listener> {
  const handlers = new Map<string, Listener>();
  const ipcMain: IpcMainLike = {
    handle(channel, listener) {
      handlers.set(channel, listener);
    },
  };
  registerIpcHandlers(ipcMain, { db: fx.db, pickDirectory: async () => null });
  return handlers;
}

async function invoke(
  handlers: Map<string, Listener>,
  channel: DabIpcChannel,
  ...args: unknown[]
): Promise<unknown> {
  const fn = handlers.get(channel);
  if (!fn) throw new Error(`no handler for ${channel}`);
  return fn(null, ...args);
}

describe('channel coverage', () => {
  it('every DabApi method maps 1:1 onto DAB_IPC_CHANNELS', () => {
    expect(() => assertChannelCoverage()).not.toThrow();
    const methods: (keyof DabApi)[] = [
      'workflowsList',
      'workflowsCreate',
      'workflowsGet',
      'workflowsUpdate',
      'workflowsDelete',
      'workflowsExport',
      'workflowsImport',
      'scriptsList',
      'scriptsRegister',
      'scriptsUnregister',
      'runsPreview',
      'runsStart',
      'runsCancel',
      'runsRetry',
      'runsGet',
      'runsList',
      'pickDirectory',
    ];
    expect(Object.keys(DAB_METHOD_CHANNELS).sort()).toEqual([...methods].sort());
    expect(new Set(Object.values(DAB_METHOD_CHANNELS))).toEqual(new Set(DAB_IPC_CHANNELS));
  });

  it('registers a handler for every channel', () => {
    const handlers = wireHandlers();
    for (const channel of DAB_IPC_CHANNELS) {
      expect(handlers.has(channel), channel).toBe(true);
    }
    expect(handlers.size).toBe(DAB_IPC_CHANNELS.length);
  });
});

describe('ipc validation and error shape', () => {
  it('rejects bad create input with a WORKFLOW_INVALID DabError', async () => {
    const handlers = wireHandlers();
    await expect(invoke(handlers, 'dab:workflows:create', '', fx.sandbox)).rejects.toMatchObject({
      code: 'WORKFLOW_INVALID',
    });
  });

  it('round-trips a workflow through create/get/list handlers', async () => {
    const handlers = wireHandlers();
    const created = (await invoke(handlers, 'dab:workflows:create', 'via-ipc', fx.sandbox)) as {
      id: string;
      name: string;
    };
    expect(created.name).toBe('via-ipc');
    const fetched = (await invoke(handlers, 'dab:workflows:get', created.id)) as { id: string };
    expect(fetched.id).toBe(created.id);
    const list = (await invoke(handlers, 'dab:workflows:list')) as unknown[];
    expect(list).toHaveLength(1);
    const missing = await invoke(handlers, 'dab:workflows:get', 'nope');
    expect(missing).toBeNull();
  });

  it('runsPreview of a missing workflow throws WORKFLOW_NOT_FOUND', async () => {
    const handlers = wireHandlers();
    await expect(invoke(handlers, 'dab:runs:preview', 'missing-id')).rejects.toMatchObject({
      code: 'WORKFLOW_NOT_FOUND',
    });
  });

  it('createHandlers table covers every channel too', () => {
    const table = createHandlers({ db: fx.db, pickDirectory: async () => null });
    expect(Object.keys(table).sort()).toEqual([...DAB_IPC_CHANNELS].sort());
  });
});
