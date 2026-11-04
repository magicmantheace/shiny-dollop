import http from 'node:http';
import { afterEach, describe, expect, it } from 'vitest';
import { createSave, type SaveEnvelope } from 'drabbit-core';
import { dispatchAction } from '../src/main/action-dispatch.js';
import { PetService } from '../src/main/pet-service.js';
import { SaveStore } from '../src/main/save-store.js';
import { CompanionConfigStore } from '../src/main/server/companion-config.js';
import { CompanionServer } from '../src/main/server/companion-server.js';
import { CompanionService } from '../src/main/server/companion-service.js';
import { FakeClock, tmpDir } from './helpers.js';

const T0 = 1_700_000_000_000;
const MIN = 60_000;
const TOKEN = 'test-token-one';
const TOKEN2 = 'test-token-two';

const closers: Array<() => Promise<void>> = [];
afterEach(async () => {
  while (closers.length > 0) {
    await closers.pop()?.();
  }
});

function makeService(clock: FakeClock, initialEnvelope?: SaveEnvelope): PetService {
  return new PetService({
    store: new SaveStore(tmpDir()),
    clock,
    ...(initialEnvelope ? { initialEnvelope } : {}),
  });
}

/** A service whose pet hatched at T0+10min (clock parked there). */
function hatchedService(): { service: PetService; clock: FakeClock } {
  const clock = new FakeClock(T0);
  const service = makeService(clock);
  clock.set(T0 + 10 * MIN);
  service.doAction('hatch');
  return { service, clock };
}

function deadService(): PetService {
  const clock = new FakeClock(T0);
  const env: SaveEnvelope = createSave({ id: 'gone-1', name: 'Pip', fur: 'ember' }, T0);
  env.pet.stage = 'dead';
  env.pet.diedAt = T0;
  env.pet.deathCause = 'neglect';
  return makeService(clock, env);
}

function makeServer(
  service: PetService,
  clock: FakeClock,
  token: string,
  port = 0,
): CompanionServer {
  const server = new CompanionServer({
    getConfig: () => ({ enabled: true, host: '127.0.0.1', port, token }),
    tick: () => service.tick(),
    getSummary: () => service.getSummary(),
    getEventsSince: (since) => service.getEventsSince(since),
    getEventCursor: () => service.getEventCursor(),
    dispatch: (kind) => dispatchAction(service, kind),
    clock,
  });
  closers.push(() => server.stop());
  return server;
}

interface HttpResult {
  status: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  body: any;
}

async function call(
  port: number,
  method: string,
  route: string,
  opts: { token?: string; body?: unknown; rawBody?: string } = {},
): Promise<HttpResult> {
  const headers: Record<string, string> = {};
  if (opts.token !== undefined) headers.authorization = `Bearer ${opts.token}`;
  const init: RequestInit = { method, headers };
  if (opts.rawBody !== undefined) {
    init.body = opts.rawBody;
  } else if (opts.body !== undefined) {
    init.body = JSON.stringify(opts.body);
    headers['content-type'] = 'application/json';
  }
  const res = await fetch(`http://127.0.0.1:${port}${route}`, init);
  const text = await res.text();
  return { status: res.status, body: text ? JSON.parse(text) : null };
}

/** Find a currently-free TCP port (for the service-level tests). */
function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const probe = http.createServer();
    probe.once('error', reject);
    probe.listen(0, '127.0.0.1', () => {
      const addr = probe.address();
      const port = addr && typeof addr === 'object' ? addr.port : 0;
      probe.close(() => resolve(port));
    });
  });
}

describe('CompanionServer auth', () => {
  it('401 without a token and with a wrong token; stats count both', async () => {
    const { service, clock } = hatchedService();
    const server = makeServer(service, clock, TOKEN);
    await server.start();
    const port = server.boundPort as number;

    const noToken = await call(port, 'GET', '/v1/status');
    expect(noToken.status).toBe(401);
    expect(noToken.body).toEqual({
      ok: false,
      error: { code: 'unauthorized', message: expect.any(String) },
    });

    const wrong = await call(port, 'GET', '/v1/status', { token: 'nope' });
    expect(wrong.status).toBe(401);

    const stats = server.getStats();
    expect(stats?.requestCount).toBe(2);
    expect(stats?.authFailures).toBe(2);
    expect(stats?.lastClient).toContain('127.0.0.1');
    expect(stats?.startedAt).toBe(T0 + 10 * MIN);
  });
});

describe('CompanionServer status + actions', () => {
  it('status returns the PetSummary shape', async () => {
    const { service, clock } = hatchedService();
    const server = makeServer(service, clock, TOKEN);
    await server.start();
    const port = server.boundPort as number;

    const res = await call(port, 'GET', '/v1/status', { token: TOKEN });
    expect(res.status).toBe(200);
    expect(res.body.ok).toBe(true);
    expect(res.body.serverNow).toBe(T0 + 10 * MIN);
    expect(Object.keys(res.body.pet).sort()).toEqual(
      [
        'id', 'name', 'fur', 'stage', 'adultForm', 'mood', 'needs', 'health',
        'careScore', 'ageMs', 'asleep', 'sick', 'messes', 'readyToHatch',
        'generation', 'deathCause',
      ].sort(),
    );
    expect(res.body.pet.stage).toBe('baby');
    expect(res.body.pet.needs.hunger).toBe(80);
  });

  it('a remote feed changes the pet state and matches the IPC result', async () => {
    const { service, clock } = hatchedService();
    const server = makeServer(service, clock, TOKEN);
    await server.start();
    const port = server.boundPort as number;

    const res = await call(port, 'POST', '/v1/actions', {
      token: TOKEN,
      body: { kind: 'feed-meal' },
    });
    expect(res.status).toBe(200);
    expect(res.body.ok).toBe(true);
    expect(res.body.pet.needs.hunger).toBe(100); // 80 + 35, clamped
    expect(res.body.pet.needs.cleanliness).toBe(98);
    expect(res.body.events.map((e: { kind: string }) => e.kind)).toContain('fed');

    // The shared state really moved — the IPC door sees the same pet.
    expect(service.getSummary().needs.hunger).toBe(100);

    // Parity: the same action through the IPC dispatcher on a twin pet
    // produces the identical outcome (summary + event kinds).
    const twin = hatchedService();
    const ipcResult = dispatchAction(twin.service, 'feed-meal');
    expect(ipcResult.ok).toBe(true);
    if (ipcResult.ok) {
      expect(res.body.pet).toEqual(ipcResult.data.summary);
      expect(res.body.events.map((e: { kind: string }) => e.kind)).toEqual(
        ipcResult.data.events.map((e) => e.kind),
      );
    }
  });

  it('wrong-stage remote action errors identically to IPC (409, same code)', async () => {
    const { service, clock } = hatchedService();
    const server = makeServer(service, clock, TOKEN);
    await server.start();
    const port = server.boundPort as number;

    const res = await call(port, 'POST', '/v1/actions', {
      token: TOKEN,
      body: { kind: 'medicine' }, // not sick
    });
    expect(res.status).toBe(409);
    expect(res.body.ok).toBe(false);
    expect(res.body.error.code).toBe('not_sick');

    const ipcResult = dispatchAction(hatchedService().service, 'medicine');
    expect(ipcResult.ok).toBe(false);
    if (!ipcResult.ok) {
      expect(ipcResult.error.code).toBe(res.body.error.code);
      expect(ipcResult.error.message).toBe(res.body.error.message);
    }
  });

  it('new-egg is desktop-only: 403 desktop_only, even for a dead pet', async () => {
    const service = deadService();
    const clock = new FakeClock(T0);
    const server = makeServer(service, clock, TOKEN);
    await server.start();
    const port = server.boundPort as number;

    const res = await call(port, 'POST', '/v1/actions', {
      token: TOKEN,
      body: { kind: 'new-egg' },
    });
    expect(res.status).toBe(403);
    expect(res.body.error.code).toBe('desktop_only');
    // Nothing happened: the pet is still dead, generation unchanged.
    expect(service.getSummary().stage).toBe('dead');
    expect(service.getSummary().generation).toBe(1);
  });
});

describe('CompanionServer events cursor', () => {
  it('bootstrap returns just the cursor; polling returns only newer events', async () => {
    const { service, clock } = hatchedService();
    const server = makeServer(service, clock, TOKEN);
    await server.start();
    const port = server.boundPort as number;

    const boot = await call(port, 'GET', '/v1/events', { token: TOKEN });
    expect(boot.status).toBe(200);
    expect(boot.body.events).toEqual([]);
    const cursor = boot.body.cursor as number;
    expect(cursor).toBe(service.getEventCursor());
    expect(cursor).toBeGreaterThan(0); // hatching already produced events

    const played = await call(port, 'POST', '/v1/actions', {
      token: TOKEN,
      body: { kind: 'play' },
    });
    expect(played.status).toBe(200);

    const delta = await call(port, 'GET', `/v1/events?since=${cursor}`, { token: TOKEN });
    expect(delta.status).toBe(200);
    expect(delta.body.events.map((e: { kind: string }) => e.kind)).toContain('played');
    expect(delta.body.cursor).toBeGreaterThan(cursor);

    const caughtUp = await call(port, 'GET', `/v1/events?since=${delta.body.cursor}`, {
      token: TOKEN,
    });
    expect(caughtUp.body.events).toEqual([]);

    const all = await call(port, 'GET', '/v1/events?since=0', { token: TOKEN });
    expect(all.body.events.length).toBe(delta.body.cursor);
    expect(all.body.events.map((e: { kind: string }) => e.kind)).toContain('hatched');
  });

  it('a malformed since is a 400 bad_query', async () => {
    const { service, clock } = hatchedService();
    const server = makeServer(service, clock, TOKEN);
    await server.start();
    const port = server.boundPort as number;
    const res = await call(port, 'GET', '/v1/events?since=abc', { token: TOKEN });
    expect(res.status).toBe(400);
    expect(res.body.error.code).toBe('bad_query');
  });
});

describe('CompanionServer protocol edges', () => {
  it('unknown routes are 404 JSON (with and without the /v1 prefix)', async () => {
    const { service, clock } = hatchedService();
    const server = makeServer(service, clock, TOKEN);
    await server.start();
    const port = server.boundPort as number;

    const inNs = await call(port, 'GET', '/v1/nope', { token: TOKEN });
    expect(inNs.status).toBe(404);
    expect(inNs.body.error.code).toBe('not_found');

    const outside = await call(port, 'GET', '/nope');
    expect(outside.status).toBe(404);
    expect(outside.body.error.code).toBe('not_found');
  });

  it('non-JSON body → 400 bad_json; malformed payload → 400 bad_payload', async () => {
    const { service, clock } = hatchedService();
    const server = makeServer(service, clock, TOKEN);
    await server.start();
    const port = server.boundPort as number;

    const notJson = await call(port, 'POST', '/v1/actions', { token: TOKEN, rawBody: 'feed me' });
    expect(notJson.status).toBe(400);
    expect(notJson.body.error.code).toBe('bad_json');

    const badKind = await call(port, 'POST', '/v1/actions', {
      token: TOKEN,
      body: { kind: 'dance' },
    });
    expect(badKind.status).toBe(400);
    expect(badKind.body.error.code).toBe('bad_payload');
  });

  it('oversized body → 413 too_large', async () => {
    const { service, clock } = hatchedService();
    const server = makeServer(service, clock, TOKEN);
    await server.start();
    const port = server.boundPort as number;

    const big = JSON.stringify({ kind: 'play', padding: 'x'.repeat(70 * 1024) });
    const res = await call(port, 'POST', '/v1/actions', { token: TOKEN, rawBody: big });
    expect(res.status).toBe(413);
    expect(res.body.error.code).toBe('too_large');
  });

  it('stop frees the port for a new server', async () => {
    const { service, clock } = hatchedService();
    const port = await freePort();
    const first = makeServer(service, clock, TOKEN, port);
    await first.start();
    await first.stop();
    const second = makeServer(service, clock, TOKEN, port);
    await expect(second.start()).resolves.toBeUndefined();
    const res = await call(port, 'GET', '/v1/status', { token: TOKEN });
    expect(res.status).toBe(200);
  });
});

describe('CompanionService lifecycle', () => {
  async function makeCompanion(): Promise<{
    companion: CompanionService;
    store: CompanionConfigStore;
    service: PetService;
    clock: FakeClock;
    port: number;
  }> {
    const dir = tmpDir();
    const clock = new FakeClock(T0);
    const service = makeService(clock);
    const store = new CompanionConfigStore(dir);
    const port = await freePort();
    store.save({ enabled: false, host: '127.0.0.1', port, token: '' });
    const companion = new CompanionService({ store, service, clock });
    closers.push(() => companion.shutdown());
    return { companion, store, service, clock, port };
  }

  it('starts disabled with no token; first enable mints one and serves', async () => {
    const { companion, port } = await makeCompanion();
    const initial = await companion.init();
    expect(initial.status).toBe('off');
    expect(initial.enabled).toBe(false);
    expect(initial.token).toBe('');

    const on = await companion.setEnabled(true);
    expect(on.status).toBe('on');
    expect(on.enabled).toBe(true);
    expect(on.token.length).toBeGreaterThan(30);
    expect(on.url).toBe(`http://127.0.0.1:${port}`);

    const res = await call(port, 'GET', '/v1/status', { token: on.token });
    expect(res.status).toBe(200);
    expect(res.body.pet.name).toBe('Pip');
  });

  it('token regeneration: old token 401s immediately, new token works', async () => {
    const { companion, port } = await makeCompanion();
    await companion.init();
    const on = await companion.setEnabled(true);
    const oldToken = on.token;
    expect((await call(port, 'GET', '/v1/status', { token: oldToken })).status).toBe(200);

    const regen = await companion.regenerateToken();
    expect(regen.status).toBe('on');
    expect(regen.token).not.toBe(oldToken);

    expect((await call(port, 'GET', '/v1/status', { token: oldToken })).status).toBe(401);
    expect((await call(port, 'GET', '/v1/status', { token: regen.token })).status).toBe(200);
  });

  it('disabling stops the server and frees the port', async () => {
    const { companion, service, clock, port } = await makeCompanion();
    await companion.init();
    await companion.setEnabled(true);
    const off = await companion.setEnabled(false);
    expect(off.status).toBe('off');
    expect(off.stats).toBeNull();

    const replacement = makeServer(service, clock, TOKEN2, port);
    await expect(replacement.start()).resolves.toBeUndefined();
  });

  it('a bind failure surfaces as an error state, not a crash', async () => {
    const { companion, service, clock, port } = await makeCompanion();
    const blocker = makeServer(service, clock, TOKEN2, port);
    await blocker.start();

    await companion.init();
    const on = await companion.setEnabled(true);
    expect(on.status).toBe('error');
    expect(on.error).toContain('EADDRINUSE');
    expect(on.enabled).toBe(true); // switch stays on; toggling retries

    await blocker.stop();
    const retry = await companion.setEnabled(true);
    expect(retry.status).toBe('on');
  });
});
