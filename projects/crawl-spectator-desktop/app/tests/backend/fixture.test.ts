import { describe, expect, it } from 'vitest';
import { SpectatorError } from '../../shared/errors';
import { FixtureFeed } from '../../electron/main/fixture';

describe('FixtureFeed', () => {
  it('is deterministic: two instances produce identical data', async () => {
    const a = new FixtureFeed();
    const b = new FixtureFeed();
    expect(await a.descenders()).toEqual(await b.descenders());
    expect(await a.descent()).toEqual(await b.descent());
    expect(a.allEvents()).toEqual(b.allEvents());
    expect(await a.health()).toEqual(await b.health());
  });

  it('directory filters by status and stratum, and strips social data', async () => {
    const feed = new FixtureFeed();
    const fallen = await feed.descenders({ status: 'fallen' });
    expect(fallen.map((d) => d.descender_id)).toEqual(['dovran-pell']);
    const stratum3 = await feed.descenders({ stratumNumber: 3 });
    expect(stratum3.map((d) => d.descender_id)).toEqual(['mira-vane', 'ossian-rell', 'tamsin-okafor']);
    for (const d of await feed.descenders()) {
      expect(d.relationships).toBeUndefined();
    }
  });

  it('profile includes relationships; unknown descenders are FEED_NOT_FOUND', async () => {
    const feed = new FixtureFeed();
    const profile = await feed.descender('mira-vane');
    expect(profile.relationships?.some((r) => r.target_id === 'ossian-rell')).toBe(true);
    await expect(feed.descender('nobody')).rejects.toMatchObject({ code: 'FEED_NOT_FOUND' });
    await expect(feed.descenderLedger('nobody')).rejects.toBeInstanceOf(SpectatorError);
  });

  it('descender history only contains that descender\'s events', async () => {
    const feed = new FixtureFeed();
    const history = await feed.descenderLedger('dovran-pell');
    expect(history.length).toBeGreaterThanOrEqual(1);
    expect(history.every((e) => e.actor_ids.includes('dovran-pell'))).toBe(true);
    expect(history.some((e) => e.event_type === 'DESCENDER_DIED')).toBe(true);
  });

  it('ledgerEvents honors after_tick (exclusive), event_type (public or legacy), and last-limit', async () => {
    const feed = new FixtureFeed();
    const after = await feed.ledgerEvents({ afterTick: 1220, limit: 100 });
    expect(after.length).toBeGreaterThanOrEqual(1);
    expect(after.every((e) => e.tick > 1220)).toBe(true);
    const diedPublic = await feed.ledgerEvents({ eventType: 'DESCENDER_DIED' });
    const diedLegacy = await feed.ledgerEvents({ eventType: 'CRAWLER_DIED' });
    expect(diedPublic.map((e) => e.id)).toEqual(diedLegacy.map((e) => e.id));
    expect(diedPublic.length).toBe(1);
    const lastTwo = await feed.ledgerEvents({ limit: 2 });
    expect(lastTwo.map((e) => e.tick)).toEqual([1236, 1240]);
  });

  it('advance() appends deterministic live events with increasing ticks and unique ids', async () => {
    const a = new FixtureFeed();
    const b = new FixtureFeed();
    const e1 = a.advance();
    expect(e1.tick).toBe(1241);
    expect(b.advance()).toEqual(e1);
    a.advance();
    a.advance();
    const all = a.allEvents();
    expect(new Set(all.map((e) => e.id)).size).toBe(all.length);
    const ticks = all.map((e) => e.tick);
    expect([...ticks].sort((x, y) => x - y)).toEqual(ticks);
    expect((await a.health()).tick).toBe(1243);
  });

  it('search matches descender ids and event content; blank queries are rejected', async () => {
    const feed = new FixtureFeed();
    const result = await feed.search('mira');
    expect(result.descenders.map((d) => d.descender_id)).toEqual(['mira-vane']);
    expect(result.events.length).toBeGreaterThanOrEqual(1);
    await expect(feed.search('   ')).rejects.toMatchObject({ code: 'INPUT_INVALID' });
  });
});
