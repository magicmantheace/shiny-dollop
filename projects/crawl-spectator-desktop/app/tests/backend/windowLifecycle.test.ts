import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { App, BrowserWindow } from 'electron';
import { describe, expect, it, vi } from 'vitest';
import {
  registerWindowLifecycle,
  shouldQuitOnAllWindowsClosed,
  shouldRecreateWindowOnActivate,
} from '../../electron/main/windowLifecycle';

type Handler = () => void;

/** Minimal fake Electron App that records the handlers main.ts registers. */
function fakeApp() {
  const handlers = new Map<string, Handler>();
  const app = {
    on: vi.fn((event: string, handler: Handler) => {
      handlers.set(event, handler);
    }),
    quit: vi.fn(),
  };
  return { app: app as unknown as App, handlers };
}

const fakeWindow = {} as BrowserWindow;

describe('window lifecycle (macOS activate)', () => {
  it('recreates the window on activate when none exists (closed window leaves mainWindow null)', () => {
    const { app, handlers } = fakeApp();
    let mainWindow: BrowserWindow | null = fakeWindow;
    const createWindow = vi.fn(() => {
      mainWindow = fakeWindow;
    });
    registerWindowLifecycle(app, { getMainWindow: () => mainWindow, createWindow, platform: 'darwin' });

    // Simulate the window closing: main.ts sets its reference to null, and
    // on darwin `window-all-closed` must NOT quit the process.
    mainWindow = null;
    handlers.get('window-all-closed')?.();
    expect(app.quit as ReturnType<typeof vi.fn>).not.toHaveBeenCalled();

    // Reactivating the still-running app (Dock click) recreates a window.
    handlers.get('activate')?.();
    expect(createWindow).toHaveBeenCalledTimes(1);
    expect(mainWindow).toBe(fakeWindow);
  });

  it('does not create a second window on activate when one already exists', () => {
    const { app, handlers } = fakeApp();
    const createWindow = vi.fn();
    registerWindowLifecycle(app, { getMainWindow: () => fakeWindow, createWindow, platform: 'darwin' });

    handlers.get('activate')?.();
    expect(createWindow).not.toHaveBeenCalled();
  });

  it('quits on window-all-closed outside macOS', () => {
    for (const platform of ['win32', 'linux'] as const) {
      const { app, handlers } = fakeApp();
      registerWindowLifecycle(app, { getMainWindow: () => null, createWindow: vi.fn(), platform });
      handlers.get('window-all-closed')?.();
      expect(app.quit as ReturnType<typeof vi.fn>).toHaveBeenCalledTimes(1);
    }
  });

  it('exposes the platform decisions directly', () => {
    expect(shouldQuitOnAllWindowsClosed('darwin')).toBe(false);
    expect(shouldQuitOnAllWindowsClosed('win32')).toBe(true);
    expect(shouldRecreateWindowOnActivate(null)).toBe(true);
    expect(shouldRecreateWindowOnActivate(fakeWindow)).toBe(false);
  });

  it('main.ts wires the lifecycle (including the activate handler) into boot', () => {
    const mainSource = readFileSync(join(__dirname, '..', '..', 'electron', 'main', 'main.ts'), 'utf8');
    expect(mainSource).toContain('registerWindowLifecycle(app,');
  });
});
