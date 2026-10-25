// Read-only HTTP adapter for the public Underreach Feed API.
//
// STRICTLY READ-ONLY: this class only ever issues GET requests. There is no
// code path here that can POST/PUT/PATCH/DELETE, and no method that touches
// the server's presentation-session endpoints (/api/feed/live/follow,
// /api/feed/live/release) or any simulation endpoint. A backend integration
// test records every request the fixture server receives while the client
// is exercised and asserts they are all GETs.

import {
  DescentSchema,
  DescenderListSchema,
  DescenderSchema,
  HealthSchema,
  LedgerEventListSchema,
  MAX_RESPONSE_BYTES,
  PartyListSchema,
  SearchResultSchema,
  parseContract,
} from '../../shared/contract.js';
import type { DescentSummary, Descender, FeedHealth, LedgerEvent, Party, SearchResult } from '../../shared/contract.js';
import { SpectatorError } from '../../shared/errors.js';
import type { ReplayQuery } from '../../shared/types.js';

/** The read surface this app consumes. Implemented by HttpFeedClient (live)
 *  and FixtureFeed (demo mode / tests). No mutating operations exist. */
export interface FeedSource {
  health(): Promise<FeedHealth>;
  descent(): Promise<DescentSummary>;
  descenders(params?: { status?: string; stratumNumber?: number; limit?: number }): Promise<Descender[]>;
  descender(descenderId: string): Promise<Descender>;
  descenderLedger(descenderId: string, limit?: number): Promise<LedgerEvent[]>;
  parties(activeOnly?: boolean): Promise<Party[]>;
  ledgerEvents(query?: ReplayQuery): Promise<LedgerEvent[]>;
  search(query: string, limit?: number): Promise<SearchResult>;
}

/** Validate + normalize a user-entered Feed API base URL. */
export function normalizeBaseUrl(raw: string): string {
  const trimmed = typeof raw === 'string' ? raw.trim() : '';
  if (!trimmed) {
    throw new SpectatorError('BASE_URL_INVALID', 'Enter the Feed API base URL, e.g. http://127.0.0.1:8000.');
  }
  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    throw new SpectatorError('BASE_URL_INVALID', `"${trimmed}" is not a valid URL. Use the form http://127.0.0.1:8000.`);
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new SpectatorError('BASE_URL_INVALID', 'The Feed API base URL must start with http:// or https://.');
  }
  if (url.username || url.password) {
    throw new SpectatorError('BASE_URL_INVALID', 'Do not embed credentials in the Feed API URL; this client never authenticates.');
  }
  return url.toString().replace(/\/+$/, '');
}

export interface HttpFeedClientOptions {
  timeoutMs?: number;
  maxResponseBytes?: number;
  fetchFn?: typeof fetch;
}

export class HttpFeedClient implements FeedSource {
  readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly maxBytes: number;
  private readonly fetchFn: typeof fetch;

  constructor(baseUrl: string, options: HttpFeedClientOptions = {}) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    this.timeoutMs = options.timeoutMs ?? 5000;
    this.maxBytes = options.maxResponseBytes ?? MAX_RESPONSE_BYTES;
    this.fetchFn = options.fetchFn ?? fetch;
  }

  /**
   * Read a response body INCREMENTALLY, counting bytes as they arrive
   * and cancelling the request the moment the safety limit is exceeded.
   * (`res.text()` buffered the entire body before any limit could be
   * checked, so an oversized or endless stream could exhaust memory in
   * the main process first.)
   */
  private async readBodyBounded(res: Response): Promise<string> {
    if (!res.body) {
      const text = await res.text();
      if (new TextEncoder().encode(text).byteLength > this.maxBytes) {
        throw new SpectatorError(
          'FEED_RESPONSE_TOO_LARGE',
          `The Feed API response exceeded the ${this.maxBytes}-byte safety limit and was discarded.`,
        );
      }
      return text;
    }
    const reader = res.body.getReader();
    const chunks: Uint8Array[] = [];
    let total = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > this.maxBytes) {
        try {
          await reader.cancel();
        } catch {
          // Best effort: the request is being abandoned either way.
        }
        throw new SpectatorError(
          'FEED_RESPONSE_TOO_LARGE',
          `The Feed API response exceeded the ${this.maxBytes}-byte safety limit and was discarded.`,
        );
      }
      chunks.push(value);
    }
    const merged = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      merged.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return new TextDecoder().decode(merged);
  }

  private async getJson(path: string): Promise<unknown> {
    const controller = new AbortController();
    // The timeout must cover the WHOLE request, including consuming the
    // body: fetch() resolves when headers arrive, so clearing the timer
    // there would let a stalled body hang the request (and any reconnect
    // waiting on it) forever instead of producing FEED_TIMEOUT.
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    let res: Response;
    let text: string;
    try {
      res = await this.fetchFn(`${this.baseUrl}${path}`, {
        method: 'GET',
        headers: { accept: 'application/json' },
        signal: controller.signal,
      });
      text = await this.readBodyBounded(res);
    } catch (err) {
      if (err instanceof SpectatorError) throw err;
      if (err instanceof Error && err.name === 'AbortError') {
        throw new SpectatorError(
          'FEED_TIMEOUT',
          `The Feed API at ${this.baseUrl} did not answer within ${this.timeoutMs} ms. Check that the Underreach Feed server is running, then reconnect.`,
        );
      }
      throw new SpectatorError(
        'FEED_UNREACHABLE',
        `Could not reach the Feed API at ${this.baseUrl}. Check the address and that the Underreach Feed server is running, then reconnect.`,
      );
    } finally {
      clearTimeout(timer);
    }
    if (res.status === 404) {
      throw new SpectatorError('FEED_NOT_FOUND', 'The Feed API reported that the requested item does not exist (404).');
    }
    if (!res.ok) {
      throw new SpectatorError('FEED_HTTP_ERROR', `The Feed API answered with HTTP ${res.status} for ${path}.`);
    }
    try {
      return JSON.parse(text) as unknown;
    } catch {
      throw new SpectatorError('FEED_CONTRACT_INVALID', 'The Feed API returned a response that was not valid JSON.');
    }
  }

  async health(): Promise<FeedHealth> {
    return parseContract(HealthSchema, await this.getJson('/health'), 'health');
  }

  async descent(): Promise<DescentSummary> {
    return parseContract(DescentSchema, await this.getJson('/api/feed/descent'), 'descent');
  }

  async descenders(params: { status?: string; stratumNumber?: number; limit?: number } = {}): Promise<Descender[]> {
    const q = new URLSearchParams();
    if (params.status) q.set('status', params.status);
    if (params.stratumNumber !== undefined) q.set('stratum_number', String(params.stratumNumber));
    q.set('limit', String(params.limit ?? 100));
    return parseContract(DescenderListSchema, await this.getJson(`/api/feed/descenders?${q}`), 'descender list');
  }

  async descender(descenderId: string): Promise<Descender> {
    return parseContract(
      DescenderSchema,
      await this.getJson(`/api/feed/descenders/${encodeURIComponent(descenderId)}`),
      'descender profile',
    );
  }

  async descenderLedger(descenderId: string, limit = 200): Promise<LedgerEvent[]> {
    return parseContract(
      LedgerEventListSchema,
      await this.getJson(`/api/feed/descenders/${encodeURIComponent(descenderId)}/ledger?limit=${limit}`),
      'descender history',
    );
  }

  async parties(activeOnly = true): Promise<Party[]> {
    return parseContract(PartyListSchema, await this.getJson(`/api/feed/parties?active_only=${activeOnly}`), 'party list');
  }

  async ledgerEvents(query: ReplayQuery = {}): Promise<LedgerEvent[]> {
    const q = new URLSearchParams();
    q.set('limit', String(query.limit ?? 100));
    if (query.eventType) q.set('event_type', query.eventType);
    if (query.afterTick !== undefined && query.afterTick !== null) q.set('after_tick', String(query.afterTick));
    return parseContract(LedgerEventListSchema, await this.getJson(`/api/feed/ledger/events?${q}`), 'ledger events');
  }

  async search(query: string, limit = 25): Promise<SearchResult> {
    const q = new URLSearchParams({ q: query, limit: String(limit) });
    return parseContract(SearchResultSchema, await this.getJson(`/api/feed/search?${q}`), 'search result');
  }
}
