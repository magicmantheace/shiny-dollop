// Tiny local HTTP server that speaks the real Feed API contract, backed by
// the deterministic FixtureFeed dataset. Used by integration tests and the
// smoke run to exercise HttpFeedClient over the wire; the app's demo mode
// uses FixtureFeed in-process instead (no port needed on the user's box).
//
// The HTTP surface is GET-only, exactly like the read surface of the real
// API this client consumes. Every request is recorded in `requests` so
// tests can prove the client never issues a non-GET request and never
// calls the server's POST session endpoints.

import { createServer, type Server } from 'node:http';
import type { AddressInfo, Socket } from 'node:net';
import { FixtureFeed } from './fixture.js';

export interface RecordedRequest {
  method: string;
  path: string;
}

export class FixtureFeedServer {
  readonly feed: FixtureFeed;
  readonly requests: RecordedRequest[] = [];
  private server: Server | null = null;
  private sockets = new Set<Socket>();
  port = 0;

  constructor(feed: FixtureFeed = new FixtureFeed()) {
    this.feed = feed;
  }

  get baseUrl(): string {
    return `http://127.0.0.1:${this.port}`;
  }

  async listen(port = 0): Promise<number> {
    this.server = createServer((req, res) => {
      void this.handle(req.method ?? 'GET', req.url ?? '/', res);
    });
    this.server.on('connection', (socket) => {
      this.sockets.add(socket);
      socket.on('close', () => this.sockets.delete(socket));
    });
    await new Promise<void>((resolve, reject) => {
      this.server!.once('error', reject);
      this.server!.listen(port, '127.0.0.1', () => resolve());
    });
    this.port = (this.server.address() as AddressInfo).port;
    return this.port;
  }

  /** Close the server and destroy live sockets (simulates the Feed going away). */
  async close(): Promise<void> {
    for (const socket of this.sockets) socket.destroy();
    this.sockets.clear();
    const server = this.server;
    this.server = null;
    if (server) await new Promise<void>((resolve) => server.close(() => resolve()));
  }

  private async handle(
    method: string,
    rawUrl: string,
    res: import('node:http').ServerResponse,
  ): Promise<void> {
    const url = new URL(rawUrl, 'http://fixture.local');
    this.requests.push({ method, path: url.pathname });
    const send = (status: number, body: unknown): void => {
      const text = JSON.stringify(body);
      res.writeHead(status, { 'content-type': 'application/json' });
      res.end(text);
    };
    try {
      if (method !== 'GET') {
        send(405, { detail: 'method not allowed: the fixture Feed surface is read-only' });
        return;
      }
      const feed = this.feed;
      const path = url.pathname;
      if (path === '/health') return send(200, await feed.health());
      if (path === '/api/feed/descent') return send(200, await feed.descent());
      if (path === '/api/feed/descenders') {
        const status = url.searchParams.get('status') ?? undefined;
        const stratum = url.searchParams.get('stratum_number');
        const limit = url.searchParams.get('limit');
        return send(200, await feed.descenders({
          ...(status ? { status } : {}),
          ...(stratum ? { stratumNumber: Number(stratum) } : {}),
          ...(limit ? { limit: Number(limit) } : {}),
        }));
      }
      const profileMatch = /^\/api\/feed\/descenders\/([^/]+)$/.exec(path);
      if (profileMatch) return send(200, await feed.descender(decodeURIComponent(profileMatch[1]!)));
      const ledgerMatch = /^\/api\/feed\/descenders\/([^/]+)\/ledger$/.exec(path);
      if (ledgerMatch) {
        const limit = url.searchParams.get('limit');
        return send(200, await feed.descenderLedger(decodeURIComponent(ledgerMatch[1]!), limit ? Number(limit) : 200));
      }
      if (path === '/api/feed/parties') {
        return send(200, await feed.parties(url.searchParams.get('active_only') !== 'false'));
      }
      if (path === '/api/feed/ledger/events') {
        const limit = url.searchParams.get('limit');
        const afterTick = url.searchParams.get('after_tick');
        const eventType = url.searchParams.get('event_type');
        return send(200, await feed.ledgerEvents({
          ...(limit ? { limit: Number(limit) } : {}),
          ...(afterTick !== null ? { afterTick: Number(afterTick) } : {}),
          ...(eventType ? { eventType } : {}),
        }));
      }
      if (path === '/api/feed/search') {
        const q = url.searchParams.get('q') ?? '';
        if (!q.trim()) return send(422, { detail: 'query must contain non-whitespace characters' });
        const limit = url.searchParams.get('limit');
        return send(200, await feed.search(q, limit ? Number(limit) : 25));
      }
      return send(404, { detail: 'not found' });
    } catch (err) {
      if (err instanceof Error && err.name === 'SpectatorError') {
        const code = (err as { code?: string }).code;
        return send(code === 'FEED_NOT_FOUND' ? 404 : 422, { detail: err.message });
      }
      return send(500, { detail: 'fixture server error' });
    }
  }
}
