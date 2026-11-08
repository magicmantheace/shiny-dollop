/**
 * Main-process lifecycle regression test: on macOS, closing the last window
 * must NOT close the WorldStore — the app stays alive, 'activate' creates a
 * new window against the already-registered IPC handlers, and every database
 * operation used to fail with "database is not open". The store must close
 * only when the app actually quits ('before-quit').
 *
 * Electron is mocked; the WorldStore and IPC handlers are the real ones.
 */
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';

type Handler = (...args: never[]) => unknown;

const harness = vi.hoisted(() => ({
  appHandlers: new Map<string, Handler>(),
  ipcHandlers: new Map<string, Handler>(),
  state: { windows: 0, userData: '' },
}));

vi.mock('electron', () => {
  class MockBrowserWindow {
    constructor() {
      harness.state.windows += 1;
    }

    static getAllWindows(): unknown[] {
      return Array.from({ length: harness.state.windows }, () => ({}));
    }

    on(): void {}

    loadURL(): Promise<void> {
      return Promise.resolve();
    }

    loadFile(): Promise<void> {
      return Promise.resolve();
    }
  }
  return {
    app: {
      whenReady: () => Promise.resolve(),
      on: (event: string, cb: Handler) => {
        harness.appHandlers.set(event, cb);
      },
      getPath: () => harness.state.userData,
      quit: () => {},
    },
    BrowserWindow: MockBrowserWindow,
    ipcMain: {
      handle: (channel: string, fn: Handler) => {
        harness.ipcHandlers.set(channel, fn);
      },
    },
  };
});

const originalPlatform = process.platform;

beforeAll(async () => {
  // Simulate macOS for the duration of this module's import of main.ts.
  Object.defineProperty(process, 'platform', { value: 'darwin' });
  harness.state.userData = mkdtempSync(join(tmpdir(), 'wbm-main-lifecycle-'));
  await import('../../electron/main');
  await vi.waitFor(() => {
    expect(harness.ipcHandlers.size).toBeGreaterThan(0);
  });
});

afterAll(() => {
  harness.appHandlers.get('before-quit')?.();
  Object.defineProperty(process, 'platform', { value: originalPlatform });
  rmSync(harness.state.userData, { recursive: true, force: true });
});

describe('electron main lifecycle (macOS semantics)', () => {
  it('keeps the database usable across last-window-close + activate, and closes it on quit', () => {
    const listEntities = harness.ipcHandlers.get('wbm:entities.list');
    expect(listEntities).toBeDefined();
    const list = (): unknown => listEntities?.(null as never, {} as never);

    expect(list()).toMatchObject({ ok: true });

    // Close the last window: the app (and its store) must stay alive.
    harness.appHandlers.get('window-all-closed')?.();
    harness.state.windows = 0; // the OS destroyed the window

    // Reactivate: a new window is created against the same IPC handlers.
    harness.appHandlers.get('activate')?.();
    expect(harness.state.windows).toBe(1);
    expect(list()).toMatchObject({ ok: true });

    // Actual quit closes the store.
    harness.appHandlers.get('before-quit')?.();
    expect(list()).toMatchObject({ ok: false });
  });
});
