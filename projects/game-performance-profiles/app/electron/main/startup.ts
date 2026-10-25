/**
 * Startup sequencing for the Electron main process.
 *
 * The IPC handlers MUST be registered before the renderer starts loading:
 * the renderer's data hook fires its initial IPC requests as soon as it
 * mounts, which can happen before loadFile() resolves — if registration
 * waits until after the load, those requests reject with "No handler
 * registered" and the app lands on its load-error screen with no retry.
 *
 * startAppWindow() therefore registers the handlers first and only then
 * creates/loads the window. The emit callback handed to the handlers
 * forwards to the window once it exists; progress events emitted before
 * that (impossible in practice — handlers can only run in response to
 * renderer requests, which require a loaded window) are dropped rather
 * than dereferencing a not-yet-created window.
 */

export interface StartupDeps<W> {
  /** Register all IPC handlers, given the progress-event emitter. */
  registerHandlers: (emit: (event: string, payload: unknown) => void) => void;
  /** Create the main window and start loading the renderer. */
  createWindow: () => Promise<W>;
  /** Send an event to an existing window. */
  sendToWindow: (win: W, event: string, payload: unknown) => void;
}

export async function startAppWindow<W>(deps: StartupDeps<W>): Promise<W> {
  const holder: { win: W | undefined } = { win: undefined };
  deps.registerHandlers((event, payload) => {
    if (holder.win !== undefined) deps.sendToWindow(holder.win, event, payload);
  });
  holder.win = await deps.createWindow();
  return holder.win;
}
