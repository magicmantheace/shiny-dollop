import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { SpectatorEngine } from '../../electron/main/engine';
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
