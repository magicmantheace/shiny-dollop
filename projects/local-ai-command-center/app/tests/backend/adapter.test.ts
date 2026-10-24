import { describe, expect, it, vi } from 'vitest';
import { MockAdapter, OllamaAdapter } from '../../electron/main/adapter.js';
import { isLaccError } from '../../shared/errors.js';
import { makeFixture } from './helpers.js';

describe('MockAdapter', () => {
  it('succeeds, contains prompt, emits chunks', async () => {
    const a = new MockAdapter({ delayMs: 1 });
    const chunks: string[] = [];
    const res = await a.generate({ model: 'mock-echo-1', prompt: 'hello world', signal: new AbortController().signal, onChunk: (t) => chunks.push(t) });
    expect(res.text).toContain('hello world');
    expect(res.text).toContain('mock-echo-1');
    expect(chunks.length).toBeGreaterThan(0);
    const h = await a.health(new AbortController().signal);
    expect(h.models).toEqual(['mock-echo-1', 'mock-coder-7b']);
  });
  it('[mock:fail] throws ADAPTER_ERROR', async () => {
    const a = new MockAdapter({ delayMs: 1 });
    await expect(a.generate({ model: 'mock-echo-1', prompt: 'x [mock:fail]', signal: new AbortController().signal })).rejects.toMatchObject({ code: 'ADAPTER_ERROR' });
  });
  it('[mock:hang] aborts with AbortError', async () => {
    const a = new MockAdapter({ delayMs: 1 });
    const ctrl = new AbortController();
    const p = a.generate({ model: 'mock-echo-1', prompt: '[mock:hang] wait', signal: ctrl.signal });
    setTimeout(() => ctrl.abort(), 20);
    await expect(p).rejects.toMatchObject({ name: 'AbortError' });
  });
});
describe('OllamaAdapter', () => {
  it('rejects non-loopback', () => {
    expect(() => new OllamaAdapter('http://example.com:11434', 1000)).toThrowError(expect.objectContaining({ code: 'CONFIG_INVALID' }));
    try { new OllamaAdapter('https://8.8.8.8:11434', 1000); expect.unreachable(); } catch (e) { expect(isLaccError(e) && e.code).toBe('CONFIG_INVALID'); }
  });
  it('dead port health is ENDPOINT_UNREACHABLE via engine', async () => {
    const { engine, db, config } = makeFixture({ mode: 'live', baseUrl: 'http://127.0.0.1:1', timeoutMs: 2000 });
    engine.saveConfig(config);
    const health = await engine.health();
    expect(health.ok).toBe(false);
    expect(health.message).toContain('ENDPOINT_UNREACHABLE');
    // direct adapter
    const a = new OllamaAdapter('http://127.0.0.1:1', 2000);
    await expect(a.health(new AbortController().signal)).rejects.toMatchObject({ code: 'ENDPOINT_UNREACHABLE' });
    db.close();
  });
});

describe('OllamaAdapter redirect containment', () => {
  function stubFetchReturning(status: number, payload: unknown) {
    const fetchFn = vi.fn(async (..._args: unknown[]) => ({ status, json: async () => payload }));
    vi.stubGlobal('fetch', fetchFn);
    return fetchFn;
  }

  it('does not follow a redirect from health: a 307 is rejected, not forwarded', async () => {
    const fetchFn = stubFetchReturning(307, { models: [] });
    const a = new OllamaAdapter('http://127.0.0.1:11434', 1000);
    await expect(a.health(new AbortController().signal)).rejects.toMatchObject({ code: 'ENDPOINT_INVALID_RESPONSE' });
    expect(fetchFn).toHaveBeenCalledTimes(1);
    const init = fetchFn.mock.calls[0]?.[1] as { redirect?: string } | undefined;
    expect(['manual', 'error']).toContain(init?.redirect);
    vi.unstubAllGlobals();
  });

  it('does not follow a redirect from generate: prompt/model are never forwarded externally', async () => {
    const fetchFn = stubFetchReturning(308, { response: 'forwarded' });
    const a = new OllamaAdapter('http://127.0.0.1:11434', 1000);
    await expect(
      a.generate({ model: 'm', prompt: 'secret prompt', signal: new AbortController().signal }),
    ).rejects.toMatchObject({ code: 'ENDPOINT_INVALID_RESPONSE' });
    expect(fetchFn).toHaveBeenCalledTimes(1);
    const init = fetchFn.mock.calls[0]?.[1] as { redirect?: string } | undefined;
    expect(['manual', 'error']).toContain(init?.redirect);
    vi.unstubAllGlobals();
  });
});
