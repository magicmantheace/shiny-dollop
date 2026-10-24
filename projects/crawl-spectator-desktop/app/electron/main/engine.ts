// Spectator engine: connection lifecycle, live Ledger polling, reconnect
// with backoff, and the local follow/preferences surface.
//
// Modes:
// - 'live': talks to a user-configured Underreach Feed API base URL through
//   HttpFeedClient (GET-only).
// - 'demo': uses an in-process FixtureFeed with invented data. The mode is
//   carried in every status object so the UI can label it unmistakably.
//
// Live updates are polled from GET /api/feed/ledger/events using the
// contract's tick cursor (after_tick). The cursor is tick-granular, so a
// resume re-requests from (cursor - 1) and the FeedStore dedupes by event
// ID: no duplicates, and no gap for events that share the cursor tick.

import type { DatabaseSync } from 'node:sqlite';
import { isHighlight } from '../../shared/contract.js';
import type { DescentSummary, Descender, LedgerEvent, Party, SearchResult } from '../../shared/contract.js';
import { SpectatorError, errorMessage } from '../../shared/errors.js';
import type { ConnectionStatus, FeedSnapshot, Prefs, PrefsEnvelope, ReplayQuery } from '../../shared/types.js';
import { HttpFeedClient, normalizeBaseUrl, type FeedSource } from './feedClient.js';
import { FeedStore, nextBackoffMs } from './feedStore.js';
import { FIXTURE_BASE_URL_LABEL, FixtureFeed } from './fixture.js';
import { exportPrefs, getPrefs, importPrefs, savePrefs } from './prefs.js';

export interface EngineDeps {
  clientFactory?: (baseUrl: string) => FeedSource;
  fixtureFactory?: () => FixtureFeed;
  pollIntervalMs?: number;
  backoffBaseMs?: number;
  backoffMaxMs?: number;
  feedCapacity?: number;
  sleep?: (ms: number) => Promise<void>;
}

const defaultSleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

export class SpectatorEngine {
  private readonly db: DatabaseSync;
  private readonly clientFactory: (baseUrl: string) => FeedSource;
  private readonly fixtureFactory: () => FixtureFeed;
  private readonly pollIntervalMs: number;
  private readonly backoffBaseMs: number;
  private readonly backoffMaxMs: number;
  private readonly sleep: (ms: number) => Promise<void>;

  readonly store: FeedStore;
  private source: FeedSource | null = null;
  private fixture: FixtureFeed | null = null;
  private descentCache: DescentSummary | null = null;
  private statusValue: ConnectionStatus = {
    state: 'disconnected',
    mode: null,
    baseUrl: null,
    message: 'Not connected. Connect to a live Feed API or start the demo to explore the spectator.',
    descentId: null,
    tick: null,
    reconnectAttempts: 0,
  };
  private runId = 0;
  private readonly statusListeners = new Set<(s: ConnectionStatus) => void>();
  private readonly feedListeners = new Set<(s: FeedSnapshot) => void>();

  constructor(db: DatabaseSync, deps: EngineDeps = {}) {
    this.db = db;
    this.clientFactory = deps.clientFactory ?? ((baseUrl) => new HttpFeedClient(baseUrl));
    this.fixtureFactory = deps.fixtureFactory ?? (() => new FixtureFeed());
    this.pollIntervalMs = deps.pollIntervalMs ?? 1500;
    this.backoffBaseMs = deps.backoffBaseMs ?? 500;
    this.backoffMaxMs = deps.backoffMaxMs ?? 8000;
    this.sleep = deps.sleep ?? defaultSleep;
    this.store = new FeedStore(deps.feedCapacity);
  }

  // -- subscriptions ---------------------------------------------------------
  onStatus(listener: (s: ConnectionStatus) => void): () => void {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  }
  onFeed(listener: (s: FeedSnapshot) => void): () => void {
    this.feedListeners.add(listener);
    return () => this.feedListeners.delete(listener);
  }
  private setStatus(patch: Partial<ConnectionStatus>): void {
    this.statusValue = { ...this.statusValue, ...patch };
    for (const listener of this.statusListeners) listener(this.statusValue);
  }
  private emitFeed(): void {
    const snapshot = this.feedSnapshot();
    for (const listener of this.feedListeners) listener(snapshot);
  }

  get status(): ConnectionStatus {
    return this.statusValue;
  }

  /** The demo fixture in use (demo mode only) — tests/smoke drive advance(). */
  get demoFeed(): FixtureFeed | null {
    return this.fixture;
  }

  // -- connection lifecycle ----------------------------------------------------

  async connectLive(baseUrlRaw: string): Promise<ConnectionStatus> {
    const baseUrl = normalizeBaseUrl(baseUrlRaw);
    savePrefs(this.db, { ...getPrefs(this.db), baseUrl });
    const run = ++this.runId;
    this.fixture = null;
    this.source = this.clientFactory(baseUrl);
    this.setStatus({ state: 'connecting', mode: 'live', baseUrl, message: `Connecting to the live Feed at ${baseUrl}…`, reconnectAttempts: 0 });
    await this.establish(run, 'live', baseUrl);
    return this.statusValue;
  }

  async connectDemo(): Promise<ConnectionStatus> {
    const run = ++this.runId;
    this.fixture = this.fixtureFactory();
    this.source = this.fixture;
    this.setStatus({
      state: 'connecting', mode: 'demo', baseUrl: FIXTURE_BASE_URL_LABEL,
      message: 'Starting demo mode with fixture data…', reconnectAttempts: 0,
    });
    await this.establish(run, 'demo', FIXTURE_BASE_URL_LABEL);
    return this.statusValue;
  }

  async disconnect(): Promise<ConnectionStatus> {
    this.runId += 1;
    this.source = null;
    this.fixture = null;
    this.setStatus({
      state: 'disconnected', mode: this.statusValue.mode, baseUrl: this.statusValue.baseUrl,
      message: 'Disconnected. Connect to a live Feed API or start the demo to explore the spectator.',
      reconnectAttempts: 0,
    });
    return this.statusValue;
  }

  private async establish(run: number, mode: 'live' | 'demo', baseUrl: string): Promise<void> {
    const source = this.source;
    if (!source) return;
    try {
      const health = await source.health();
      if (run !== this.runId) return;
      this.descentCache = await source.descent();
      if (run !== this.runId) return;
      this.store.clear();
      const initial = await source.ledgerEvents({ limit: 200 });
      if (run !== this.runId) return;
      this.store.ingest(initial);
      this.setStatus({
        state: 'connected', mode, baseUrl, descentId: health.descent_id, tick: health.tick, reconnectAttempts: 0,
        message: mode === 'demo'
          ? 'DEMO MODE — showing invented fixture data. No live Underreach is connected.'
          : `Connected to the live Feed at ${baseUrl}.`,
      });
      this.emitFeed();
      void this.pollLoop(run);
    } catch (err) {
      if (run !== this.runId) return;
      this.setStatus({ state: 'error', mode, baseUrl, message: `${errorMessage(err)} Reconnecting automatically…` });
      void this.reconnectLoop(run);
    }
  }

  private async pollLoop(run: number): Promise<void> {
    while (run === this.runId && this.source) {
      await this.sleep(this.pollIntervalMs);
      if (run !== this.runId || !this.source) return;
      try {
        if (this.fixture) this.fixture.advance();
        const cursor = this.store.cursorTick;
        const events = await this.source.ledgerEvents({
          limit: 300,
          afterTick: cursor === null ? null : Math.max(0, cursor - 1),
        });
        if (run !== this.runId) return;
        const added = this.store.ingest(events);
        const health = await this.source.health();
        if (run !== this.runId) return;
        this.setStatus({ tick: health.tick, descentId: health.descent_id });
        if (added > 0) this.emitFeed();
      } catch (err) {
        if (run !== this.runId) return;
        this.setStatus({ state: 'error', message: `${errorMessage(err)} Connection lost — reconnecting…` });
        await this.reconnectLoop(run);
        return;
      }
    }
  }

  private async reconnectLoop(run: number): Promise<void> {
    let attempt = 0;
    while (run === this.runId && this.source) {
      attempt += 1;
      this.setStatus({ reconnectAttempts: attempt });
      await this.sleep(nextBackoffMs(attempt - 1, this.backoffBaseMs, this.backoffMaxMs));
      if (run !== this.runId || !this.source) return;
      try {
        const health = await this.source.health();
        if (run !== this.runId) return;
        const cursor = this.store.cursorTick;
        const missed = await this.source.ledgerEvents({
          limit: 1000,
          afterTick: cursor === null ? null : Math.max(0, cursor - 1),
        });
        if (run !== this.runId) return;
        this.store.ingest(missed);
        const mode = this.statusValue.mode ?? 'live';
        const baseUrl = this.statusValue.baseUrl ?? '';
        this.setStatus({
          state: 'connected', descentId: health.descent_id, tick: health.tick, reconnectAttempts: 0,
          message: mode === 'demo'
            ? 'DEMO MODE — showing invented fixture data. No live Underreach is connected.'
            : `Reconnected to the live Feed at ${baseUrl}.`,
        });
        this.emitFeed();
        void this.pollLoop(run);
        return;
      } catch {
        // Still down: loop with the next backoff step.
      }
    }
  }

  // -- read surface (delegates to the connected source) ------------------------

  private requireSource(): FeedSource {
    if (!this.source || (this.statusValue.state !== 'connected' && this.statusValue.state !== 'error')) {
      throw new SpectatorError('NOT_CONNECTED', 'Not connected. Connect to a live Feed API or start demo mode first.');
    }
    return this.source;
  }

  async getDescent(): Promise<DescentSummary | null> {
    if (!this.source) return null;
    this.descentCache = await this.source.descent();
    return this.descentCache;
  }

  async listDescenders(): Promise<Descender[]> {
    return this.requireSource().descenders({ limit: 500 });
  }

  async getProfile(descenderId: string): Promise<Descender> {
    return this.requireSource().descender(descenderId);
  }

  async getHistory(descenderId: string, limit = 200): Promise<LedgerEvent[]> {
    return this.requireSource().descenderLedger(descenderId, limit);
  }

  async search(query: string): Promise<SearchResult> {
    return this.requireSource().search(query);
  }

  async listParties(): Promise<Party[]> {
    return this.requireSource().parties(true);
  }

  feedSnapshot(): FeedSnapshot {
    return {
      events: this.store.snapshot(),
      cursorTick: this.store.cursorTick,
      droppedCount: this.store.droppedCount,
      bufferedCount: this.store.size,
    };
  }

  /** Replay browser: query the Ledger directly (does not touch the live buffer). */
  async getReplay(query: ReplayQuery): Promise<LedgerEvent[]> {
    return this.requireSource().ledgerEvents({
      limit: Math.min(1000, Math.max(1, query.limit ?? 100)),
      afterTick: query.afterTick ?? null,
      eventType: query.eventType ?? null,
    });
  }

  /** Highlights: notable events (contract set) involving followed Descenders,
   *  computed locally from the Ledger — follows never leave this client. */
  async getHighlights(limit = 100): Promise<LedgerEvent[]> {
    const followed = new Set(getPrefs(this.db).followedDescenderIds);
    if (followed.size === 0) return [];
    const events = await this.requireSource().ledgerEvents({ limit: 1000 });
    return events.filter((event) => isHighlight(event, followed)).slice(-limit);
  }

  // -- preferences -------------------------------------------------------------

  getPrefs(): Prefs {
    return getPrefs(this.db);
  }

  follow(descenderId: string): Prefs {
    const prefs = getPrefs(this.db);
    if (!prefs.followedDescenderIds.includes(descenderId)) {
      return savePrefs(this.db, { ...prefs, followedDescenderIds: [...prefs.followedDescenderIds, descenderId] });
    }
    return prefs;
  }

  unfollow(descenderId: string): Prefs {
    const prefs = getPrefs(this.db);
    return savePrefs(this.db, { ...prefs, followedDescenderIds: prefs.followedDescenderIds.filter((id) => id !== descenderId) });
  }

  exportPrefs(): PrefsEnvelope {
    return exportPrefs(this.db);
  }

  importPrefs(envelope: unknown): Prefs {
    return importPrefs(this.db, envelope);
  }
}
