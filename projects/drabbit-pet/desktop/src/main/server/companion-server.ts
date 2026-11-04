import { timingSafeEqual } from 'node:crypto';
import http from 'node:http';
import type { PetEvent } from 'drabbit-core';
import type {
  ActionKind,
  ActionOutcome,
  CompanionServerStats,
  IpcResult,
  PetSummary,
} from '../../shared/api-types.js';
import { parseActionPayload } from '../../shared/validation.js';
import type { Clock } from '../pet-service.js';
import type { CompanionConfig } from './companion-config.js';

/**
 * The companion HTTP server (P3): a second front door to the SAME pet
 * the care panel drives. Pure Node stdlib `http`, Electron-free — it
 * is constructed with providers over the one PetService and can be
 * started/stopped in plain Node, which is how the tests drive it.
 *
 * Wire protocol: see docs/DESIGN.md ("Companion wire protocol").
 * Every /v1/* request needs `Authorization: Bearer <token>`; the
 * token comes from the config provider per request, so the value the
 * CompanionService currently holds is always the one enforced.
 */

export const MAX_BODY_BYTES = 64 * 1024;

export interface CompanionServerDeps {
  /** Current companion config (host/port read at start; token per request). */
  getConfig: () => CompanionConfig;
  /** Advance the pet to now (the server responds with current state). */
  tick: () => void;
  getSummary: () => PetSummary;
  getEventsSince: (since: number) => { events: PetEvent[]; cursor: number };
  getEventCursor: () => number;
  /** The shared action dispatcher — identical semantics to IPC. */
  dispatch: (kind: ActionKind) => IpcResult<ActionOutcome>;
  clock: Clock;
}

interface ErrorBody {
  ok: false;
  error: { code: string; message: string };
}

function errorBody(code: string, message: string): ErrorBody {
  return { ok: false, error: { code, message } };
}

/** Map a dispatch error code to its HTTP status (docs/DESIGN.md). */
function statusForErrorCode(code: string): number {
  if (code === 'bad_payload') return 400;
  if (code === 'internal') return 500;
  return 409; // core PetError codes: the action is invalid for this state
}

export class CompanionServer {
  private server: http.Server | null = null;
  private stats: CompanionServerStats | null = null;

  constructor(private readonly deps: CompanionServerDeps) {}

  get running(): boolean {
    return this.server !== null;
  }

  /** The port actually bound (differs from config when port 0 is used in tests). */
  get boundPort(): number | null {
    const addr = this.server?.address();
    return addr && typeof addr === 'object' ? addr.port : null;
  }

  getStats(): CompanionServerStats | null {
    return this.stats ? { ...this.stats } : null;
  }

  start(): Promise<void> {
    if (this.server) return Promise.resolve();
    const { host, port } = this.deps.getConfig();
    const server = http.createServer((req, res) => {
      this.handle(req, res).catch(() => {
        // A handler bug must never take the server (or the app) down.
        if (!res.headersSent) {
          this.sendJson(res, 500, errorBody('internal', 'Internal server error.'));
        } else {
          res.end();
        }
      });
    });
    server.on('clientError', (_err, socket) => {
      socket.destroy();
    });
    this.server = server;
    this.stats = {
      startedAt: this.deps.clock.now(),
      requestCount: 0,
      authFailures: 0,
      lastClient: null,
    };
    return new Promise<void>((resolve, reject) => {
      const onError = (err: Error) => {
        if (this.server === server) this.server = null;
        reject(err);
      };
      server.once('error', onError);
      server.listen(port, host, () => {
        server.removeListener('error', onError);
        server.on('error', () => undefined); // post-listen errors: stay alive
        resolve();
      });
    });
  }

  stop(): Promise<void> {
    const server = this.server;
    if (!server) return Promise.resolve();
    this.server = null;
    return new Promise<void>((resolve) => {
      server.close(() => resolve());
      // Don't let keep-alive sockets hold the port hostage.
      server.closeIdleConnections?.();
    });
  }

  // -- request handling ---------------------------------------------------

  private async handle(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    const url = new URL(req.url ?? '/', 'http://companion.invalid');
    const pathname = url.pathname;

    if (!pathname.startsWith('/v1/')) {
      this.sendJson(res, 404, errorBody('not_found', `No such route: ${req.method} ${pathname}`));
      return;
    }

    if (this.stats) {
      this.stats.requestCount += 1;
      this.stats.lastClient = req.socket.remoteAddress ?? null;
    }

    if (!this.authorized(req)) {
      if (this.stats) this.stats.authFailures += 1;
      this.sendJson(res, 401, errorBody('unauthorized', 'Missing or invalid bearer token.'));
      return;
    }

    if (req.method === 'GET' && pathname === '/v1/status') {
      this.deps.tick();
      this.sendJson(res, 200, { ok: true, serverNow: this.deps.clock.now(), pet: this.deps.getSummary() });
      return;
    }

    if (req.method === 'GET' && pathname === '/v1/events') {
      this.handleEvents(url, res);
      return;
    }

    if (req.method === 'POST' && pathname === '/v1/actions') {
      await this.handleAction(req, res);
      return;
    }

    this.sendJson(res, 404, errorBody('not_found', `No such route: ${req.method} ${pathname}`));
  }

  private authorized(req: http.IncomingMessage): boolean {
    const token = this.deps.getConfig().token;
    if (!token) return false; // no token generated yet → nothing is authorized
    const header = req.headers.authorization;
    if (!header || !header.startsWith('Bearer ')) return false;
    const presented = Buffer.from(header.slice('Bearer '.length), 'utf8');
    const expected = Buffer.from(token, 'utf8');
    if (presented.length !== expected.length) return false;
    return timingSafeEqual(presented, expected);
  }

  private handleEvents(url: URL, res: http.ServerResponse): void {
    const raw = url.searchParams.get('since');
    this.deps.tick();
    const cursor = this.deps.getEventCursor();
    if (raw === null || raw === '') {
      // Bootstrap: no backlog, just the cursor to poll from.
      this.sendJson(res, 200, { ok: true, serverNow: this.deps.clock.now(), events: [], cursor });
      return;
    }
    if (!/^\d+$/.test(raw)) {
      this.sendJson(
        res,
        400,
        errorBody('bad_query', `Query parameter "since" must be a non-negative integer, got: ${raw}`),
      );
      return;
    }
    const result = this.deps.getEventsSince(Number(raw));
    this.sendJson(res, 200, {
      ok: true,
      serverNow: this.deps.clock.now(),
      events: result.events,
      cursor: result.cursor,
    });
  }

  private async handleAction(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    const body = await this.readBody(req);
    if (body.tooLarge) {
      this.sendJson(res, 413, errorBody('too_large', `Request body exceeds ${MAX_BODY_BYTES} bytes.`));
      return;
    }
    let payload: unknown;
    try {
      payload = JSON.parse(body.text);
    } catch {
      this.sendJson(res, 400, errorBody('bad_json', 'Request body is not valid JSON.'));
      return;
    }
    const parsed = parseActionPayload(payload);
    if (!parsed.ok) {
      this.sendJson(res, 400, errorBody(parsed.error.code, parsed.error.message));
      return;
    }
    if (parsed.value.kind === 'new-egg') {
      // Deliberate (docs/DESIGN.md): starting the next generation is a
      // desktop-side decision, never a remote one.
      this.sendJson(
        res,
        403,
        errorBody('desktop_only', 'Starting a new egg is a desktop-only action.'),
      );
      return;
    }
    const result = this.deps.dispatch(parsed.value.kind);
    if (!result.ok) {
      this.sendJson(
        res,
        statusForErrorCode(result.error.code),
        errorBody(result.error.code, result.error.message),
      );
      return;
    }
    this.sendJson(res, 200, {
      ok: true,
      serverNow: this.deps.clock.now(),
      pet: result.data.summary,
      events: result.data.events,
    });
  }

  /** Read the whole body, draining (but discarding) past the size cap. */
  private readBody(req: http.IncomingMessage): Promise<{ text: string; tooLarge: boolean }> {
    return new Promise((resolve, reject) => {
      const chunks: Buffer[] = [];
      let size = 0;
      let tooLarge = false;
      req.on('data', (chunk: Buffer) => {
        size += chunk.length;
        if (size > MAX_BODY_BYTES) {
          tooLarge = true;
          chunks.length = 0;
          return;
        }
        if (!tooLarge) chunks.push(chunk);
      });
      req.on('end', () => {
        resolve({ text: tooLarge ? '' : Buffer.concat(chunks).toString('utf8'), tooLarge });
      });
      req.on('error', reject);
    });
  }

  private sendJson(res: http.ServerResponse, status: number, body: unknown): void {
    const text = JSON.stringify(body);
    res.writeHead(status, {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(text),
    });
    res.end(text);
  }
}
