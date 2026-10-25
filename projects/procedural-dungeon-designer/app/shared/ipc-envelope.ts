// Structured IPC result envelope.
//
// Why this exists: Electron serializes errors thrown through
// `ipcMain.handle` down to (at most) their message before they reach the
// renderer, so throwing a { code, message } PddError from a handler loses
// the code — `BUDGET_EXCEEDED` never reaches `formatError`. Handlers
// therefore RETURN failures as response data inside this envelope, which
// crosses `ipcRenderer.invoke` intact, and the preload unwraps it,
// re-throwing the named error on the renderer side of the bridge.
//
// This module is the canonical implementation used by the main process
// and the tests. The sandboxed preload cannot import it at runtime, so
// preload.ts carries an inline copy of the unwrap logic; a backend test
// guards that the copy exists and throws the envelope's error.

import { isPddError, type PddError } from './errors.js';

export interface IpcSuccessEnvelope<T> {
  ok: true;
  value: T;
}

export interface IpcErrorEnvelope {
  ok: false;
  error: PddError;
}

export type IpcEnvelope<T> = IpcSuccessEnvelope<T> | IpcErrorEnvelope;

export function successEnvelope<T>(value: T): IpcSuccessEnvelope<T> {
  return { ok: true, value };
}

export function errorEnvelope(error: PddError): IpcErrorEnvelope {
  return { ok: false, error };
}

export function isIpcEnvelope(value: unknown): value is IpcEnvelope<unknown> {
  if (typeof value !== 'object' || value === null) return false;
  const envelope = value as { ok?: unknown; value?: unknown; error?: unknown };
  if (envelope.ok === true) return 'value' in envelope;
  if (envelope.ok === false) return isPddError(envelope.error);
  return false;
}

/**
 * Renderer-side half of the contract: return the success value, or throw
 * the envelope's { code, message } PddError so callers see exactly the
 * named failure the service produced.
 */
export function unwrapIpcEnvelope<T>(envelope: IpcEnvelope<T>): T {
  if (envelope.ok) return envelope.value;
  throw envelope.error;
}
