import { describe, expect, it } from 'vitest';
import type { LedgerEvent } from '../../shared/contract';
import { FeedStore, nextBackoffMs } from '../../electron/main/feedStore';

function ev(id: string, tick: number): LedgerEvent {
  return {
    id, descent_id: 'd', stratum_number: 1, tick, event_type: 'DESCENDER_MOVED', summary: `event ${id}`,
    actor_ids: [], sector_id: null,
    semantic: { importance_score: 0, rarity_score: 0, danger_level: 0, reversal: false, relationship_impact: 0, audience_interest_tags: [], causal_parent_ids: [] },
    canonical: true,
  };
}

describe('FeedStore', () => {
  it('keeps events in deterministic (tick, id) order regardless of ingest order', () => {
    const store = new FeedStore();
    store.ingest([ev('b', 5), ev('a', 5), ev('c', 3)]);
    expect(store.snapshot().map((e) => e.id)).toEqual(['c', 'a', 'b']);
    expect(store.cursorTick).toBe(5);
  });

  it('dedupes by event ID, including overlapping resume batches', () => {
    const store = new FeedStore();
    expect(store.ingest([ev('a', 10), ev('b', 10)])).toBe(2);
    // Resume re-requests from cursor-1, so already-seen events arrive again.
    expect(store.ingest([ev('b', 10), ev('c', 10)])).toBe(1);
    expect(store.snapshot().map((e) => e.id)).toEqual(['a', 'b', 'c']);
  });

  it('bounds memory under backpressure: capacity is a hard cap, drops are counted', () => {
    const store = new FeedStore(10);
    const batch = Array.from({ length: 1000 }, (_, i) => ev(`e${i}`, i));
    store.ingest(batch);
    expect(store.size).toBe(10);
    expect(store.droppedCount).toBe(990);
    // The newest events survive.
    expect(store.snapshot().map((e) => e.id)).toEqual(batch.slice(-10).map((e) => e.id));
    expect(store.cursorTick).toBe(999);
    // Further ingestion stays bounded.
    store.ingest([ev('x', 1000)]);
    expect(store.size).toBe(10);
    expect(store.droppedCount).toBe(991);
  });

  it('cursor is null when empty', () => {
    expect(new FeedStore().cursorTick).toBeNull();
  });
});

describe('nextBackoffMs', () => {
  it('doubles from the base and caps at the max', () => {
    expect(nextBackoffMs(0, 100, 1000)).toBe(100);
    expect(nextBackoffMs(1, 100, 1000)).toBe(200);
    expect(nextBackoffMs(2, 100, 1000)).toBe(400);
    expect(nextBackoffMs(3, 100, 1000)).toBe(800);
    expect(nextBackoffMs(4, 100, 1000)).toBe(1000);
    expect(nextBackoffMs(20, 100, 1000)).toBe(1000);
  });
});
