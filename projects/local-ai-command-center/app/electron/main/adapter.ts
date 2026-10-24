import { LACC_ERROR_CODES, laccError, isLaccError } from '../../shared/errors.js';
import type { EndpointConfig } from '../../shared/types.js';

export interface GenerateRequest { model: string; prompt: string; signal: AbortSignal; onChunk?: (text: string) => void; }
export interface RuntimeAdapter {
  health(signal: AbortSignal): Promise<{ models: string[] }>;
  generate(req: GenerateRequest): Promise<{ text: string }>;
}
function abortError(): Error { const e = new Error('The operation was aborted'); e.name = 'AbortError'; return e; }
function throwIfAborted(signal?: AbortSignal): void { if (signal?.aborted) throw abortError(); }
function isAbort(err: unknown): boolean { return err instanceof Error && (err.name === 'AbortError' || err.name === 'TimeoutError'); }

function validateLoopback(baseUrl: string): URL {
  let url: URL;
  try { url = new URL(baseUrl); } catch { throw laccError(LACC_ERROR_CODES.CONFIG_INVALID, `Invalid endpoint base URL: ${baseUrl}`); }
  const host = url.hostname.replace(/^\[|\]$/g, '').toLowerCase();
  if (host !== 'localhost' && host !== '127.0.0.1' && host !== '::1') {
    throw laccError(LACC_ERROR_CODES.CONFIG_INVALID, `Endpoint must be a loopback address (localhost, 127.0.0.1, or ::1); got host "${url.hostname}".`);
  }
  return url;
}

export class MockAdapter implements RuntimeAdapter {
  private readonly delayMs: number;
  constructor(opts?: { delayMs?: number }) { this.delayMs = opts?.delayMs ?? 5; }
  async health(signal: AbortSignal): Promise<{ models: string[] }> {
    throwIfAborted(signal);
    return { models: ['mock-echo-1', 'mock-coder-7b'] };
  }
  async generate(req: GenerateRequest): Promise<{ text: string }> {
    const { prompt, model, signal, onChunk } = req;
    throwIfAborted(signal);
    if (prompt.includes('[mock:fail]')) throw laccError(LACC_ERROR_CODES.ADAPTER_ERROR, 'Mock adapter failure requested by [mock:fail] marker.');
    if (prompt.includes('[mock:hang]')) {
      await new Promise<never>((_resolve, reject) => {
        if (signal.aborted) { reject(abortError()); return; }
        const onAbort = () => reject(abortError());
        signal.addEventListener('abort', onAbort, { once: true });
      });
    }
    const text = `Mock response (model ${model}):\n${prompt}`;
    // Emit a few chunks
    const chunkSize = Math.max(1, Math.ceil(text.length / 3));
    for (let i = 0; i < text.length; i += chunkSize) {
      throwIfAborted(signal);
      if (this.delayMs > 0) {
        await new Promise<void>((resolve, reject) => {
          const t = setTimeout(resolve, this.delayMs);
          signal.addEventListener('abort', () => { clearTimeout(t); reject(abortError()); }, { once: true });
        });
      }
      throwIfAborted(signal);
      onChunk?.(text.slice(i, i + chunkSize));
    }
    return { text };
  }
}

export class OllamaAdapter implements RuntimeAdapter {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  constructor(baseUrl: string, timeoutMs = 30000) {
    validateLoopback(baseUrl);
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.timeoutMs = timeoutMs;
  }
  private unreachable(): ReturnType<typeof laccError> {
    return laccError(LACC_ERROR_CODES.ENDPOINT_UNREACHABLE, `Could not reach the local model endpoint at ${this.baseUrl} — is the runtime (e.g. Ollama) running?`);
  }
  private rejectRedirect(res: Response): void {
    // Redirects are never followed (see the fetch calls): a 307/308 from the
    // configured loopback endpoint could otherwise forward the prompt/model
    // to an arbitrary external host without validateLoopback ever seeing it.
    if (res.status >= 300 && res.status < 400) {
      throw laccError(LACC_ERROR_CODES.ENDPOINT_INVALID_RESPONSE, `Endpoint at ${this.baseUrl} returned an HTTP ${res.status} redirect. Redirects are not followed, because the destination cannot be verified as loopback.`);
    }
  }
  async health(signal: AbortSignal): Promise<{ models: string[] }> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}/api/tags`, { signal, redirect: 'manual' });
    } catch (err) {
      if (isAbort(err) || (err instanceof Error && signal.aborted)) throw laccError(LACC_ERROR_CODES.ENDPOINT_TIMEOUT, `Health probe to ${this.baseUrl} timed out or was aborted.`);
      throw this.unreachable();
    }
    this.rejectRedirect(res);
    let data: unknown;
    try { data = await res.json(); } catch { throw laccError(LACC_ERROR_CODES.ENDPOINT_INVALID_RESPONSE, `Endpoint at ${this.baseUrl} returned a non-JSON response.`); }
    if (!data || typeof data !== 'object' || !Array.isArray((data as { models?: unknown }).models)) {
      throw laccError(LACC_ERROR_CODES.ENDPOINT_INVALID_RESPONSE, `Endpoint at ${this.baseUrl} returned an unexpected response shape.`);
    }
    const models = (data as { models: unknown[] }).models.map((mm) => {
      if (!mm || typeof mm !== 'object' || typeof (mm as { name?: unknown }).name !== 'string') throw laccError(LACC_ERROR_CODES.ENDPOINT_INVALID_RESPONSE, `Endpoint at ${this.baseUrl} returned a model entry without a name.`);
      return (mm as { name: string }).name;
    });
    return { models };
  }
  async generate(req: GenerateRequest): Promise<{ text: string }> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}/api/generate`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ model: req.model, prompt: req.prompt, stream: false }),
        signal: req.signal,
        redirect: 'manual',
      });
    } catch (err) {
      if (isAbort(err) || req.signal.aborted) {
        // If caller aborted (cancel/timeout handled upstream), propagate AbortError so engine can distinguish? But spec says map timeout to ENDPOINT_TIMEOUT.
        // Check: if signal aborted, rethrow AbortError to let engine decide timeout vs cancel.
        throw abortError();
      }
      throw this.unreachable();
    }
    this.rejectRedirect(res);
    let data: unknown;
    try { data = await res.json(); } catch { throw laccError(LACC_ERROR_CODES.ENDPOINT_INVALID_RESPONSE, `Endpoint at ${this.baseUrl} returned a non-JSON response.`); }
    if (!data || typeof data !== 'object' || typeof (data as { response?: unknown }).response !== 'string') {
      throw laccError(LACC_ERROR_CODES.ENDPOINT_INVALID_RESPONSE, `Endpoint at ${this.baseUrl} returned an unexpected generate response shape.`);
    }
    const text = (data as { response: string }).response;
    req.onChunk?.(text);
    return { text };
  }
}

export function createAdapter(config: EndpointConfig): RuntimeAdapter {
  if (config.mode === 'mock') return new MockAdapter();
  validateLoopback(config.baseUrl);
  return new OllamaAdapter(config.baseUrl, config.timeoutMs);
}
export { isLaccError };
