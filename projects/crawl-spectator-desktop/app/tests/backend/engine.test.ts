import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import type { LedgerEvent } from '../../shared/contract';
import { SpectatorError } from '../../shared/errors';
import type { ReplayQuery } from '../../shared/types';
import { SpectatorEngine } from '../../electron/main/engine';
import type { FeedSource } from '../../electron/main/feedClient';
import { FixtureFeed } from '../../electron/main/fixture';
import { FixtureFeedServer } from '../../electron/main/fixtureServer';
import { openPrefsDatabase } from '../../electron/main/prefs';

let dir: string;
beforeAll(async () => {
  dir = await mkdtemp(join(tmpdir(), 'spectator-engine-test-'));
});
afterAll(async () => {
  await rm(dir, { recursive: true, force: true });
});

async function waitFor(cond: () => boolean, timeoutMs = 6000): Promise<void> {
  const start = Date.now();
  while (!cond()) {
    if (Date.now() - start > timeoutMs) throw new Error('waitFor timed out');
    await new Promise((r) => setTimeout(r, 25));
  }
}

describe('SpectatorEngine — demo mode', () => {
  it('connects, streams live fixture events, serves profile/search/replay, and follows locally', async () => {
    const db = openPrefsDatabase(join(dir, 'demo.sqlite'));
    const engine = new SpectatorEngine(db, { pollIntervalMs: 30, backoffBaseMs: 30, backoffMaxMs: 120 });
    const status = await engine.connectDemo();
    expect(status.state).toBe('connected');
    expect(status.mode).toBe('demo');
    expect(status.message).toContain('DEMO MODE');

    const initial = engine.feedSnapshot();
    expect(initial.events.length).toBe(17); // scripted fixture history
    expect(initial.cursorTick).toBe(1240);

    // Poll loop advances the fixture and appends new live events.
    await waitFor(() => engine.feedSnapshot().events.length > 17);
    const grown = engine.feedSnapshot();
    const ids = new Set(grown.events.map((e) => e.id));
    expect(ids.size).toBe(grown.events.length);

    const profile = await engine.getProfile('ossian-rell');
    expect(profile.current_party_id).toBe('party-ember-pact');
    const found = await engine.search('ossian');
    expect(found.descenders.map((d) => d.descender_id)).toEqual(['ossian-rell']);
    const replay = await engine.getReplay({ afterTick: 1236, limit: 10 });
    expect(replay.every((e) => e.tick > 1236)).toBe(true);

    engine.follow('mira-vane');
    const highlights = await engine.getHighlights();
    expect(highlights.length).toBeGreaterThanOrEqual(1);
    expect(highlights.every((e) => e.actor_ids.includes('mira-vane'))).toBe(true);

    await engine.disconnect();
    expect(engine.status.state).toBe('disconnected');
    await expect(engine.listDescenders()).rejects.toMatchObject({ code: 'NOT_CONNECTED' });
    db.close();
  });
});

describe('SpectatorEngine — live mode with disconnect/reconnect', () => {
  it('survives the Feed going away, reconnects with backoff, and resumes the cursor without duplicates or gaps', async () => {
    const feed = new FixtureFeed();
    const server1 = new FixtureFeedServer(feed);
    await server1.listen(0);
    const port = server1.port;

    const db = openPrefsDatabase(join(dir, 'live.sqlite'));
    const engine = new SpectatorEngine(db, { pollIntervalMs: 40, backoffBaseMs: 40, backoffMaxMs: 160 });
    const status = await engine.connectLive(server1.baseUrl);
    expect(status.state).toBe('connected');
    expect(status.mode).toBe('live');
    const before = engine.feedSnapshot().events.length;
    expect(before).toBe(17);

    // Feed goes away.
    await server1.close();
    await waitFor(() => engine.status.state === 'error');
    expect(engine.status.reconnectAttempts).toBeGreaterThanOrEqual(0);

    // While it is down, the world moves on (three new events appear server-side).
    feed.advance();
    feed.advance();
    feed.advance();

    // Feed comes back on the same port with the same data.
    const server2 = new FixtureFeedServer(feed);
    await server2.listen(port);
    await waitFor(() => engine.status.state === 'connected');

    // Catch-up after reconnect: no duplicates, and the three missed events arrived.
    await waitFor(() => engine.feedSnapshot().events.length >= before + 3);
    const events = engine.feedSnapshot().events;
    expect(new Set(events.map((e) => e.id)).size).toBe(events.length);
    expect(events.some((e) => e.tick === 1243)).toBe(true);

    await engine.disconnect();
    await server2.close();
    db.close();
  });

  it('an unreachable live URL lands in error state (not a hang or crash)', async () => {
    const db = openPrefsDatabase(join(dir, 'down.sqlite'));
    const engine = new SpectatorEngine(db, { pollIntervalMs: 40, backoffBaseMs: 30, backoffMaxMs: 60 });
    const status = await engine.connectLive('http://127.0.0.1:1');
    expect(status.state).toBe('error');
    expect(status.message).toContain('FEED_UNREACHABLE');
    await engine.disconnect();
    db.close();
  });

  it('rejects invalid base URLs before any connection attempt', async () => {
    const db = openPrefsDatabase(join(dir, 'bad.sqlite'));
    const engine = new SpectatorEngine(db, {});
    await expect(engine.connectLive('ftp://example.test')).rejects.toMatchObject({ code: 'BASE_URL_INVALID' });
    db.close();
  });
});

// -- stub source for source-switch / catch-up regressions --------------------

function stubEvent(seq: number, tick: number): LedgerEvent {
  return {
    id: `stub-${seq}`, descent_id: 'descent-stub-001', stratum_number: 1, tick,
    event_type: 'ENCOUNTER_TRIGGERED', summary: `stub event ${seq}`, actor_ids: [], sector_id: null,
    semantic: { importance_score: 0.4, rarity_score: 0.1, danger_level: 0.2, reversal: false, relationship_impact: 0, audience_interest_tags: [], causal_parent_ids: [] },
    canonical: true,
  };
}

class StubFeed implements FeedSource {
  events: LedgerEvent[] = [];
  healthFailures = 0;
  currentTick = 0;
  private seq = 0;
  addEvents(count: number, fromTick: number): void {
    for (let i = 0; i < count; i += 1) {
      this.seq += 1;
      this.events.push(stubEvent(this.seq, fromTick + i));
    }
    this.currentTick = fromTick + count - 1;
  }
  async health() {
    if (this.healthFailures > 0) {
      this.healthFailures -= 1;
      throw new SpectatorError('FEED_UNREACHABLE', 'stub feed is down');
    }
    return { status: 'ok', world: 'The Underreach', service: 'The Feed', descent_id: 'descent-stub-001', tick: this.currentTick };
  }
  async descent() {
    return {
      id: 'descent-stub-001', world: 'The Underreach', competition: 'The Descent', broadcast: 'The Feed',
      record: 'The Ledger', status: 'active', current_tick: this.currentTick, current_stratum: 1, stratum_count: 5,
      starting_descender_count: 1, surviving_descender_count: 1, eliminated_descender_count: 0,
      ruleset_id: 'stub', ruleset_version: '1.0.0',
    };
  }
  async descenders() { return []; }
  async descender(): Promise<never> { throw new SpectatorError('FEED_NOT_FOUND', 'none'); }
  async descenderLedger() { return []; }
  async parties() { return []; }
  async ledgerEvents(query: ReplayQuery = {}) {
    let rows = [...this.events];
    if (query.afterTick !== undefined && query.afterTick !== null) rows = rows.filter((e) => e.tick > query.afterTick!);
    rows.sort((a, b) => a.tick - b.tick || a.id.localeCompare(b.id));
    // Contract semantics: the LAST `limit` matching events, not a first page.
    return rows.slice(-(query.limit ?? 100)).map((e) => ({ ...e }));
  }
  async search(query: string) { return { query, descenders: [], events: [] }; }
}

describe('SpectatorEngine — switching sources (regression)', () => {
  it('a failed initial live health check after demo does NOT resume from the demo cursor', async () => {
    const db = openPrefsDatabase(join(dir, 'switch.sqlite'));
    const stub = new StubFeed();
    stub.addEvents(5, 1); // live server is only at tick 5
    stub.healthFailures = 1; // the first (establish) health check fails
    const engine = new SpectatorEngine(db, {
      pollIntervalMs: 30, backoffBaseMs: 30, backoffMaxMs: 60,
      clientFactory: () => stub,
    });
    const demo = await engine.connectDemo();
    expect(demo.state).toBe('connected');
    expect(engine.feedSnapshot().cursorTick).toBe(1240); // fixture cursor

    const status = await engine.connectLive('http://127.0.0.1:9');
    expect(status.state).toBe('error');
    // Source-specific state was cleared when the new connection started,
    // before establish() ran — no demo events/cursor remain to resume from.
    const cleared = engine.feedSnapshot();
    expect(cleared.events).toHaveLength(0);
    expect(cleared.cursorTick).toBeNull();

    // Automatic reconnect performs a full initial sync for the live source:
    // it loads the live events at ticks 1-5 instead of requesting
    // after_tick=1239 and showing fixture events under a LIVE banner.
    await waitFor(() => engine.status.state === 'connected');
    const live = engine.feedSnapshot();
    expect(live.events).toHaveLength(5);
    expect(live.events.every((e) => e.id.startsWith('stub-'))).toBe(true);
    expect(live.cursorTick).toBe(5);
    await engine.disconnect();
    db.close();
  });
});

describe('SpectatorEngine — polling catch-up truncation (regression)', () => {
  it('widens a full 300-event poll batch to 1000 and loses nothing', async () => {
    const db = openPrefsDatabase(join(dir, 'widen.sqlite'));
    const stub = new StubFeed();
    stub.addEvents(10, 1);
    const engine = new SpectatorEngine(db, {
      pollIntervalMs: 30, backoffBaseMs: 30, backoffMaxMs: 60,
      clientFactory: () => stub,
    });
    await engine.connectLive('http://127.0.0.1:9');
    expect(engine.feedSnapshot().events).toHaveLength(10);
    stub.addEvents(350, 11); // 350 new events between polls (> the 300 poll limit)
    await waitFor(() => engine.feedSnapshot().events.length === 360);
    expect(engine.feedSnapshot().truncatedCatchUps).toBe(0);
    expect(engine.feedSnapshot().cursorTick).toBe(360);
    await engine.disconnect();
    db.close();
  });

  it('reports truncation explicitly when even the widened 1000-event window fills', async () => {
    const db = openPrefsDatabase(join(dir, 'truncated.sqlite'));
    const stub = new StubFeed();
    stub.addEvents(10, 1);
    const engine = new SpectatorEngine(db, {
      pollIntervalMs: 30, backoffBaseMs: 30, backoffMaxMs: 60, feedCapacity: 5000,
      clientFactory: () => stub,
    });
    await engine.connectLive('http://127.0.0.1:9');
    stub.addEvents(1100, 11); // more than even the widened limit can cover
    await waitFor(() => engine.feedSnapshot().truncatedCatchUps >= 1);
    const snapshot = engine.feedSnapshot();
    expect(snapshot.cursorTick).toBe(1110);
    // The loss is reported, not hidden: snapshot counter + status warning.
    expect(engine.status.message).toContain('retrieval limit');
    await engine.disconnect();
    db.close();
  });
});
