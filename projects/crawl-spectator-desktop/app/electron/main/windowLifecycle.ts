// Window lifecycle policy for the Electron main process.
//
// On macOS an app conventionally stays running after its last window is
// closed, and clicking its Dock icon fires `activate`, which must recreate
// a window when none exists. On other platforms closing the last window
// quits the app. Keeping these decisions here (instead of inline in
// main.ts) makes them unit-testable without launching Electron.

import type { App, BrowserWindow } from 'electron';

export interface WindowLifecycleDeps {
  /** Returns the current main window, or null once it has closed. */
  getMainWindow: () => BrowserWindow | null;
  /** Creates (and tracks) a new main window. */
  createWindow: () => void;
  /** Platform to evaluate the policy for; defaults to the running platform. */
  platform?: NodeJS.Platform;
}

/** Closing every window quits the app everywhere except macOS. */
export function shouldQuitOnAllWindowsClosed(platform: NodeJS.Platform): boolean {
  return platform !== 'darwin';
}

/** An activation should recreate a window only when no window exists. */
export function shouldRecreateWindowOnActivate(mainWindow: BrowserWindow | null): boolean {
  return mainWindow === null;
}

export function registerWindowLifecycle(app: App, deps: WindowLifecycleDeps): void {
  const platform = deps.platform ?? process.platform;
  app.on('window-all-closed', () => {
    if (shouldQuitOnAllWindowsClosed(platform)) app.quit();
  });
  app.on('activate', () => {
    if (shouldRecreateWindowOnActivate(deps.getMainWindow())) deps.createWindow();
  });
}
