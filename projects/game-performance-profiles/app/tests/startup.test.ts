/**
 * Startup sequencing tests: IPC handlers must be registered BEFORE the
 * window starts loading the renderer. The renderer's data hook fires its
 * initial IPC requests on mount, which can happen before loadFile()
 * resolves — registering after the load races those requests and strands
 * the app on its load-error screen ("No handler registered").
 */
import { describe, expect, it, vi } from 'vitest';
import { startAppWindow } from '../electron/main/startup.js';

interface FakeWindow {
  sent: Array<{ event: string; payload: unknown }>;
}

describe('startAppWindow', () => {
  it('registers handlers before creating/loading the window', async () => {
    const order: string[] = [];
    const win: FakeWindow = { sent: [] };
    const result = await startAppWindow<FakeWindow>({
      registerHandlers: () => {
        order.push('register');
      },
      createWindow: async () => {
        order.push('createWindow');
        return win;
      },
      sendToWindow: (w, event, payload) => {
        w.sent.push({ event, payload });
      },
    });
    expect(order).toEqual(['register', 'createWindow']);
    expect(result).toBe(win);
  });

  it('forwards progress events to the window once it exists', async () => {
    let emit: ((event: string, payload: unknown) => void) | undefined;
    const win: FakeWindow = { sent: [] };
    const sendToWindow = vi.fn((w: FakeWindow, event: string, payload: unknown) => {
      w.sent.push({ event, payload });
    });
    await startAppWindow<FakeWindow>({
      registerHandlers: (e) => {
        emit = e;
      },
      createWindow: async () => win,
      sendToWindow,
    });
    emit!('gpp:activation-progress', { phase: 'applied' });
    expect(sendToWindow).toHaveBeenCalledTimes(1);
    expect(win.sent).toEqual([{ event: 'gpp:activation-progress', payload: { phase: 'applied' } }]);
  });

  it('drops (never throws on) events emitted before the window exists', async () => {
    let emit: ((event: string, payload: unknown) => void) | undefined;
    let releaseWindow: ((w: FakeWindow) => void) | undefined;
    const win: FakeWindow = { sent: [] };
    const pending = startAppWindow<FakeWindow>({
      registerHandlers: (e) => {
        emit = e;
      },
      createWindow: () =>
        new Promise<FakeWindow>((resolve) => {
          releaseWindow = resolve;
        }),
      sendToWindow: (w, event, payload) => {
        w.sent.push({ event, payload });
      },
    });
    // Window still loading: emitting must not dereference a missing window.
    expect(() => emit!('gpp:activation-progress', { phase: 'applying' })).not.toThrow();
    releaseWindow!(win);
    await pending;
    expect(win.sent).toEqual([]);
  });
});
