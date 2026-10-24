import { createServer, type Server } from 'node:http';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { HttpFeedClient, normalizeBaseUrl } from '../../electron/main/feedClient';
import { FixtureFeedServer } from '../../electron/main/fixtureServer';

let server: FixtureFeedServer;
let client: HttpFeedClient;

beforeAll(async () => {
  server = new FixtureFeedServer();
  await server.listen(0);
  client = new HttpFeedClient(server.baseUrl);
});
afterAll(async () => {
  await server.close();
});

describe('HttpFeedClient against the fixture Feed server (real contract over HTTP)', () => {
  it('health + descent match the contract', async () => {
    const health = await client.health();
    expect(health.status).toBe('ok');
    expect(health.world).toBe('The Underreach');
    expect(health.descent_id).toBe('descent-fixture-001');
    const descent = await client.descent();
    expect(descent.current_stratum).toBe(3);
    expect(descent.starting_descender_count).toBe(8);
  });

  it('descenders, profile (with relationships), and history flow', async () => {
    const list = await client.descenders();
    expect(list).toHaveLength(8);
    const profile = await client.descender('mira-vane');
    expect(profile.relationships?.length).toBeGreaterThanOrEqual(1);
    const history = await client.descenderLedger('mira-vane');
    expect(history.length).toBeGreaterThanOrEqual(3);
    expect(history.every((e) => e.actor_ids.includes('mira-vane'))).toBe(true);
  });

  it('parties, search and ledger cursor semantics flow', async () => {
    expect(await client.parties()).toHaveLength(2);
    const found = await client.search('selka');
    expect(found.descenders.map((d) => d.descender_id)).toEqual(['selka-morrow']);
    const events = await client.ledgerEvents({ afterTick: 1230, limit: 100 });
    expect(events.length).toBeGreaterThanOrEqual(1);
    expect(events.every((e) => e.tick > 1230)).toBe(true);
    const died = await client.ledgerEvents({ eventType: 'DESCENDER_DIED' });
    expect(died).toHaveLength(1);
  });

  it('unknown descender maps the server 404 to FEED_NOT_FOUND', async () => {
    await expect(client.descender('nobody')).rejects.toMatchObject({ code: 'FEED_NOT_FOUND' });
  });

  it('READ-ONLY: every request the client ever issued was a GET, and no session/write endpoint was touched', () => {
    expect(server.requests.length).toBeGreaterThan(0);
    expect(server.requests.every((r) => r.method === 'GET')).toBe(true);
    const paths = server.requests.map((r) => r.path);
    expect(paths.some((p) => p.includes('/live/follow') || p.includes('/live/release'))).toBe(false);
    expect(paths.some((p) => /simulate|advance|tick|write|mutat/i.test(p))).toBe(false);
  });
});

describe('HttpFeedClient failure handling (raw stub servers)', () => {
  async function withStub(handler: (res: import('node:http').ServerResponse) => void, fn: (baseUrl: string) => Promise<void>): Promise<void> {
    const stub: Server = createServer((_req, res) => handler(res));
    await new Promise<void>((resolve) => stub.listen(0, '127.0.0.1', () => resolve()));
    const port = (stub.address() as { port: number }).port;
    try {
      await fn(`http://127.0.0.1:${port}`);
    } finally {
      await new Promise<void>((resolve) => stub.close(() => resolve()));
    }
  }

  it('rejects oversized responses', async () => {
    await withStub((res) => {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(' '.repeat(3_000_000));
    }, async (baseUrl) => {
      await expect(new HttpFeedClient(baseUrl).health()).rejects.toMatchObject({ code: 'FEED_RESPONSE_TOO_LARGE' });
    });
  });

  it('rejects contract-violating payloads', async () => {
    await withStub((res) => {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok', world: 'The Underreach', service: 'The Feed', descent_id: 'x', tick: 'soon' }));
    }, async (baseUrl) => {
      await expect(new HttpFeedClient(baseUrl).health()).rejects.toMatchObject({ code: 'FEED_CONTRACT_INVALID' });
    });
  });

  it('times out instead of hanging', async () => {
    await withStub(() => {
      // Never respond.
    }, async (baseUrl) => {
      await expect(new HttpFeedClient(baseUrl, { timeoutMs: 120 }).health()).rejects.toMatchObject({ code: 'FEED_TIMEOUT' });
    });
  });

  it('times out when headers arrive but the body stalls', async () => {
    await withStub((res) => {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.write('{"status":"ok"');
      // Body never ends: fetch() has resolved, res.text() is pending.
    }, async (baseUrl) => {
      await expect(new HttpFeedClient(baseUrl, { timeoutMs: 120 }).health()).rejects.toMatchObject({ code: 'FEED_TIMEOUT' });
    });
  });

  it('reports unreachable servers actionably', async () => {
    await expect(new HttpFeedClient('http://127.0.0.1:1', { timeoutMs: 500 }).health())
      .rejects.toMatchObject({ code: 'FEED_UNREACHABLE' });
  });
});

describe('normalizeBaseUrl', () => {
  it('accepts and normalizes http(s) URLs', () => {
    expect(normalizeBaseUrl('http://127.0.0.1:8000/')).toBe('http://127.0.0.1:8000');
    expect(normalizeBaseUrl('  https://example.test/feed  ')).toBe('https://example.test/feed');
  });
  it('rejects empty, non-http, and credential-bearing URLs', () => {
    expect(() => normalizeBaseUrl('')).toThrowError(expect.objectContaining({ code: 'BASE_URL_INVALID' }));
    expect(() => normalizeBaseUrl('ftp://example.test')).toThrowError(expect.objectContaining({ code: 'BASE_URL_INVALID' }));
    expect(() => normalizeBaseUrl('http://user:pass@example.test')).toThrowError(expect.objectContaining({ code: 'BASE_URL_INVALID' }));
    expect(() => normalizeBaseUrl('not a url')).toThrowError(expect.objectContaining({ code: 'BASE_URL_INVALID' }));
  });
});
