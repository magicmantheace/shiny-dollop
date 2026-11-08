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
  /** True only after the CURRENT source completed its initial sync.
   *  Reconnects for an established source resume from the feed cursor;
   *  reconnects for a never-established source must do a full initial
   *  sync instead — resuming would reuse a previous source's cursor. */
  private established = false;
  /** Descent identity the buffered events/cursor belong to, taken from
   *  the health response at the last (fresh) sync. If a later health
   *  response names a different Descent, the buffer and cursor are for
   *  the OLD Descent and must never be resumed against the new one. */
  private establishedDescentId: string | null = null;
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

  /** Drop every piece of source-specific buffered state. Called when a
   *  NEW connection starts (before any request to the new source) and on
   *  disconnect, so a previous source's cursor/events/descent can never
   *  leak into the new source — e.g. demo events at tick 1240 must not
   *  become the resume cursor for a live server at tick 5. */
  private resetSourceState(): void {
    this.established = false;
    this.establishedDescentId = null;
    this.descentCache = null;
    this.store.clear();
    this.emitFeed();
  }

  /** True when the source is established but is now serving a different
   *  Descent than the one the buffered events/cursor belong to. */
  private descentChanged(healthDescentId: string): boolean {
    return this.established && this.establishedDescentId !== healthDescentId;
  }

  /** Full initial sync for the CURRENT source/descent: refresh the
   *  descent summary, drop every buffered event/cursor, and load the
   *  latest window with no resume cursor. Returns false when the run
   *  was superseded mid-sync (the caller must abandon this run). */
  private async syncInitial(run: number, source: FeedSource): Promise<boolean> {
    this.descentCache = await source.descent();
    if (run !== this.runId) return false;
    this.store.clear();
    const initial = await source.ledgerEvents({ limit: 200 });
    if (run !== this.runId) return false;
    this.store.ingest(initial);
    return true;
  }

  async connectLive(baseUrlRaw: string): Promise<ConnectionStatus> {
    const baseUrl = normalizeBaseUrl(baseUrlRaw);
    savePrefs(this.db, { ...getPrefs(this.db), baseUrl });
    const run = ++this.runId;
    this.fixture = null;
    this.source = this.clientFactory(baseUrl);
    this.resetSourceState();
    this.setStatus({ state: 'connecting', mode: 'live', baseUrl, descentId: null, tick: null, message: `Connecting to the live Feed at ${baseUrl}…`, reconnectAttempts: 0 });
    await this.establish(run, 'live', baseUrl);
    return this.statusValue;
  }

  async connectDemo(): Promise<ConnectionStatus> {
    const run = ++this.runId;
    this.fixture = this.fixtureFactory();
    this.source = this.fixture;
    this.resetSourceState();
    this.setStatus({
      state: 'connecting', mode: 'demo', baseUrl: FIXTURE_BASE_URL_LABEL, descentId: null, tick: null,
      message: 'Starting demo mode with fixture data…', reconnectAttempts: 0,
    });
    await this.establish(run, 'demo', FIXTURE_BASE_URL_LABEL);
    return this.statusValue;
  }

  async disconnect(): Promise<ConnectionStatus> {
    this.runId += 1;
    this.source = null;
    this.fixture = null;
    this.resetSourceState();
    this.setStatus({
      state: 'disconnected', mode: this.statusValue.mode, baseUrl: this.statusValue.baseUrl, descentId: null, tick: null,
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
      if (!(await this.syncInitial(run, source))) return;
      this.established = true;
      this.establishedDescentId = health.descent_id;
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

  /** Fetch events after the current cursor for catch-up.
   *
   *  The contract returns the LAST `limit` events after `after_tick`, not
   *  the first page — so a batch that fills the limit may have silently
   *  omitted older events in the window. When the first request fills its
   *  limit, widen once to `maxLimit`: if the widened batch comes back
   *  under that limit it provably covers the whole window. If it still
   *  fills `maxLimit`, coverage cannot be established from this client
   *  (the contract has no backward paging), so the window is reported as
   *  truncated instead of silently advancing the cursor past the loss. */
  private async fetchCatchUp(source: FeedSource, limit: number, maxLimit: number): Promise<{ events: LedgerEvent[]; truncated: boolean }> {
    const cursor = this.store.cursorTick;
    const afterTick = cursor === null ? null : Math.max(0, cursor - 1);
    const first = await source.ledgerEvents({ limit, afterTick });
    if (first.length < limit || limit >= maxLimit) {
      return { events: first, truncated: first.length >= maxLimit && limit >= maxLimit };
    }
    const widened = await source.ledgerEvents({ limit: maxLimit, afterTick });
    return { events: widened, truncated: widened.length >= maxLimit };
  }

  private noteTruncatedCatchUp(): void {
    this.store.noteTruncatedCatchUp();
    this.setStatus({
      message: 'Warning: a catch-up from the Feed hit the retrieval limit, so some events may have been missed. The missed count is not knowable from this client; reconnecting reloads the latest window.',
    });
    this.emitFeed();
  }

  private async pollLoop(run: number): Promise<void> {
    while (run === this.runId && this.source) {
      await this.sleep(this.pollIntervalMs);
      if (run !== this.runId || !this.source) return;
      try {
        if (this.fixture) this.fixture.advance();
        // Health FIRST: if the Feed at this URL now serves a different
        // Descent, the buffered events/cursor belong to the old Descent —
        // never request after_tick=<old cursor> against the new one.
        // Fresh-sync instead, exactly like the initial connection.
        const health = await this.source.health();
        if (run !== this.runId) return;
        if (this.descentChanged(health.descent_id)) {
          if (!(await this.syncInitial(run, this.source))) return;
          this.establishedDescentId = health.descent_id;
          this.setStatus({ tick: health.tick, descentId: health.descent_id });
          this.emitFeed();
          continue;
        }
        const { events, truncated } = await this.fetchCatchUp(this.source, 300, 1000);
        if (run !== this.runId) return;
        const added = this.store.ingest(events);
        if (truncated) this.noteTruncatedCatchUp();
        this.setStatus({ tick: health.tick, descentId: health.descent_id });
        if (added > 0 || truncated) this.emitFeed();
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
        let catchUpTruncated = false;
        if (!this.established || this.descentChanged(health.descent_id)) {
          // Either this source never completed its initial sync (e.g. the
          // first health check after switching sources failed), or the
          // Descent changed while we were disconnected. In both cases do
          // NOT resume from whatever cursor happens to be buffered — do
          // the full initial sync for THIS Descent instead.
          if (!(await this.syncInitial(run, this.source))) return;
        } else {
          const caught = await this.fetchCatchUp(this.source, 1000, 1000);
          if (run !== this.runId) return;
          this.store.ingest(caught.events);
          catchUpTruncated = caught.truncated;
        }
        this.established = true;
        this.establishedDescentId = health.descent_id;
        const mode = this.statusValue.mode ?? 'live';
        const baseUrl = this.statusValue.baseUrl ?? '';
        this.setStatus({
          state: 'connected', descentId: health.descent_id, tick: health.tick, reconnectAttempts: 0,
          message: mode === 'demo'
            ? 'DEMO MODE — showing invented fixture data. No live Underreach is connected.'
            : `Reconnected to the live Feed at ${baseUrl}.`,
        });
        if (catchUpTruncated) this.noteTruncatedCatchUp();
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
      truncatedCatchUps: this.store.truncatedCatchUps,
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
