// Bounded in-memory Live Ledger buffer.
//
// Backpressure safety: the buffer has a hard capacity. Ingesting more
// events than the capacity drops the OLDEST events and counts them in
// `droppedCount`, so a fast Feed (or a slow renderer) can never grow
// memory without bound. Events are deduplicated by canonical event ID
// and kept in deterministic (tick, id) order — the same order the Ledger
// itself uses.

import type { LedgerEvent } from '../../shared/contract.js';

export const DEFAULT_FEED_CAPACITY = 500;

function compareEvents(a: LedgerEvent, b: LedgerEvent): number {
  return a.tick - b.tick || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
}

export class FeedStore {
  private readonly capacity: number;
  private events: LedgerEvent[] = [];
  private readonly seen = new Set<string>();
  /**
   * Deduplication state for EVICTED events. Evicted ids used to be
   * deleted from `seen`, so when a poll re-requested the cursor tick
   * (deliberately, for tick-granular resume) the same evicted events
   * were accepted, evicted and counted as drops AGAIN on every poll —
   * the loss count grew indefinitely on an idle Feed. Two bounded
   * mechanisms now remember them:
   *  - `evictedIds`: a FIFO tombstone set (capped, see below);
   *  - `evictionWatermark`: the greatest (tick, id) ever evicted.
   *    Evictions always remove a sorted prefix of the buffer, so any
   *    replayed event at or below the watermark that is not currently
   *    buffered was already counted once and must be ignored.
   */
  private readonly evictedIds = new Set<string>();
  private evictionWatermark: LedgerEvent | null = null;
  droppedCount = 0;
  /** Catch-up windows that still filled the maximum retrieval limit after
   *  widening, so events in them may have been silently omitted by the
   *  server's last-`limit` semantics. Counted separately from droppedCount
   *  (bounded-buffer evictions, whose exact count is known): here the exact
   *  number of missed events is unknowable from this client, so the honest
   *  signal is the number of truncated windows, surfaced in the snapshot. */
  truncatedCatchUps = 0;

  constructor(capacity: number = DEFAULT_FEED_CAPACITY) {
    this.capacity = Math.max(1, capacity);
  }

  get size(): number {
    return this.events.length;
  }

  /** Highest tick buffered, or null when empty. This is the resume cursor:
   *  the ledger cursor is tick-granular (after_tick), so on resume the
   *  engine re-requests from cursor-1 and relies on ID dedupe — no gaps
   *  for events sharing the cursor tick, no duplicates in the buffer. */
  get cursorTick(): number | null {
    const last = this.events[this.events.length - 1];
    return last ? last.tick : null;
  }

  /** Ingest a batch; returns how many NEW events were accepted. */
  ingest(batch: Iterable<LedgerEvent>): number {
    let added = 0;
    for (const event of batch) {
      if (this.seen.has(event.id)) continue;
      // Already evicted once and counted: a replay (overlapping poll of
      // the cursor tick) must not accept or count it again.
      if (this.evictedIds.has(event.id)) continue;
      if (
        this.evictionWatermark &&
        compareEvents(event, this.evictionWatermark) <= 0
      ) {
        continue;
      }
      this.seen.add(event.id);
      this.events.push(event);
      added += 1;
    }
    if (added > 0) {
      this.events.sort(compareEvents);
      if (this.events.length > this.capacity) {
        const excess = this.events.length - this.capacity;
        const dropped = this.events.splice(0, excess);
        for (const event of dropped) {
          this.seen.delete(event.id);
          this.evictedIds.add(event.id);
        }
        const lastDropped = dropped[dropped.length - 1];
        if (
          lastDropped &&
          (!this.evictionWatermark ||
            compareEvents(lastDropped, this.evictionWatermark) > 0)
        ) {
          this.evictionWatermark = lastDropped;
        }
        // Bound the tombstone set itself (FIFO): the watermark above
        // still covers anything trimmed from it, since evictions are a
        // sorted prefix.
        const tombstoneCap = Math.max(1024, this.capacity * 2);
        while (this.evictedIds.size > tombstoneCap) {
          const oldest = this.evictedIds.values().next().value as string;
          this.evictedIds.delete(oldest);
        }
        this.droppedCount += excess;
      }
    }
    return added;
  }

  snapshot(): LedgerEvent[] {
    return [...this.events];
  }

  /** Record a catch-up window that hit the retrieval limit (see above). */
  noteTruncatedCatchUp(): void {
    this.truncatedCatchUps += 1;
  }

  clear(): void {
    this.events = [];
    this.seen.clear();
    this.evictedIds.clear();
    this.evictionWatermark = null;
    this.droppedCount = 0;
    this.truncatedCatchUps = 0;
  }
}

/** Pure exponential backoff: base * 2^attempt, capped. attempt is 0-based. */
export function nextBackoffMs(attempt: number, baseMs: number, maxMs: number): number {
  return Math.min(maxMs, baseMs * 2 ** Math.max(0, attempt));
}
