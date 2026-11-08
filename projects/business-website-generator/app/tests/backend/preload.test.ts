/**
 * Preload contract test: window.bwg exposes EXACTLY the methods declared in
 * shared/types.ts BwgApi, and each one forwards to the correct IPC channel.
 */
import { describe, expect, it, vi } from 'vitest';

const exposed: Record<string, unknown> = {};
const invokeCalls: { channel: string; args: unknown[] }[] = [];

vi.mock('electron', () => ({
  contextBridge: {
    exposeInMainWorld: (key: string, api: unknown) => {
      exposed[key] = api;
    },
  },
  ipcRenderer: {
    invoke: (channel: string, ...args: unknown[]) => {
      invokeCalls.push({ channel, args });
      return Promise.resolve(null);
    },
  },
  ipcMain: { handle: vi.fn() },
}));

await import('../../electron/preload.js');

import type { BwgApi } from '../../shared/types.js';

type AnyFn = (...args: never[]) => unknown;

function methodPaths(obj: object, prefix = ''): string[] {
  const out: string[] = [];
  for (const key of Object.keys(obj).sort()) {
    const path = prefix ? `${prefix}.${key}` : key;
    const value = (obj as Record<string, unknown>)[key];
    if (typeof value === 'function') out.push(path);
    else if (value && typeof value === 'object') out.push(...methodPaths(value as object, path));
  }
  return out;
}

/** The exact method list Worker B codes against (mirrors BwgApi). */
const EXPECTED_METHODS = [
  'dialog.pickDirectory',
  'export.run',
  'export.validate',
  'preview.render',
  'sites.create',
  'sites.delete',
  'sites.get',
  'sites.list',
  'sites.setTheme',
  'sites.updateProfile',
  'themes.list',
];

describe('window.bwg contract', () => {
  it('exposes bwg on the window', () => {
    expect(exposed['bwg']).toBeDefined();
  });

  it('exposes exactly the BwgApi method set — no more, no fewer', () => {
    const api = exposed['bwg'] as BwgApi;
    expect(methodPaths(api)).toEqual(EXPECTED_METHODS);
  });

  it('forwards each method to its IPC channel with the right args', async () => {
    const api = exposed['bwg'] as unknown as Record<string, Record<string, AnyFn>>;
    invokeCalls.length = 0;

    await api.sites.list();
    await api.sites.create({ name: 'x', businessType: 'trades', themeId: 'trades' });
    await api.sites.get('id-1');
    await api.sites.updateProfile('id-1', { tagline: 'hi' });
    await api.sites.delete('id-1');
    await api.sites.setTheme('id-1', 'trades');
    await api.themes.list();
    await api.preview.render('id-1');
    await api.export.validate('id-1');
    await api.export.run('id-1', '/tmp/out');
    await api.dialog.pickDirectory();

    expect(invokeCalls.map((c) => c.channel)).toEqual([
      'bwg:sites:list',
      'bwg:sites:create',
      'bwg:sites:get',
      'bwg:sites:updateProfile',
      'bwg:sites:delete',
      'bwg:sites:setTheme',
      'bwg:themes:list',
      'bwg:preview:render',
      'bwg:export:validate',
      'bwg:export:run',
      'bwg:dialog:pickDirectory',
    ]);
    expect(invokeCalls[1].args).toEqual([{ name: 'x', businessType: 'trades', themeId: 'trades' }]);
    expect(invokeCalls[9].args).toEqual(['id-1', '/tmp/out']);
  });
});
