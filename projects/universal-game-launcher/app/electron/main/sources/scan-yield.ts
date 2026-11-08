/**
 * Yield to the event loop so IPC messages (e.g. scan cancellation) queued
 * behind a long scan get processed. setImmediate fires after pending I/O,
 * which is exactly the responsiveness guarantee scans need.
 */
export function yieldToEventLoop(): Promise<void> {
  return new Promise((resolve) => setImmediate(resolve));
}
