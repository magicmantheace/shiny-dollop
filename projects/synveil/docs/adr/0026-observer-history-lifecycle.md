# ADR 0026: Observer history & lifecycle — in-core sampler, ephemeral only

- Status: Accepted
- Date: 2026-11-07
- Supersedes: none
- Superseded by: none
- Related: [ADR 0023](0023-physical-validation-parked-boot-update-freeze.md)
  (boot/update freeze; this work stays outside the frozen zones),
  `docs/OBSERVER_HISTORY_DESIGN.md` (the design this ADR accepts),
  `docs/OBSERVER.md` (the stateless observer this extends).

## Context

The observer (`synveil.observe/v1`) is deliberately
stateless: every response is derived from kernel files at
request time, and the 2026-11 interval metrics sample twice
inside one request. Four Phase 3 roadmap items cannot be
built that way — process lifecycle event/delta tracking,
event normalization, ephemeral telemetry storage, and
historical aggregation — because all four need a component
that remembers observations across requests. The design
proposal in `docs/OBSERVER_HISTORY_DESIGN.md` posed four
questions: where the sampler lives, its cadence and bounds,
how history is exposed, and the first aggregation set.

On 2026-11-07 the owner accepted the proposal as
recommended, with one amendment: **the sampler is off by
default until a consumer exists.**

## Decision

1. **Sampler inside veil-core.** A bounded sampler thread
   in the core (which already supervises the system and
   owns the audit journal) takes an observe snapshot at a
   fixed **5 s** cadence using the existing producer code —
   no new kernel parsing — and diffs consecutive process
   snapshots by the (pid, start_time_ticks) identity the
   snapshot already guarantees.
2. **Lifecycle events, normalized, telemetry-only.**
   `process_started` / `process_exited` events (exits carry
   the final cumulative counters) are normalized into the
   audit record envelope family as `synveil.observe-event/v1`
   records and kept in a bounded in-memory ring of **1024
   events**. Events are telemetry, not audit: they do **not**
   enter the hash-chained audit journal. Processes that
   start and exit between samples are missed by construction;
   sub-cadence truth (eBPF/netlink) is a different, larger
   proposal and is not authorized here.
3. **Ephemeral aggregates.** Windowed aggregates live in
   memory only: **1 min buckets, mean/max**, for the four
   windowed metrics (utilization, throughput, bandwidth,
   power), hard-bounded, never persisted. A core restart
   clears all history. No on-disk telemetry store is
   created; the state-partition budget is untouched.
4. **Exposure.** History is served by a new read-only
   `observe-history` request, separate from the existing
   observe response.
5. **Off by default (owner amendment).** The sampler does
   not run unless enabled by policy, and stays off until a
   consumer for the history exists. Acceptance of this ADR
   does not switch it on.

## Consequences

- The first implementation slice is lifecycle events only
  (sampler + process diff + ring + `observe-history`),
  host-tested with fixture snapshot pairs and natively
  validated in QEMU. Storage/aggregation follow as their
  own slices.
- Nothing in this ADR touches the ADR 0023 frozen zones:
  no boot, update, or authentication change is authorized,
  and the supervision/session infrastructure is unchanged —
  the sampler is a thread inside the existing core process,
  enabled by policy, not a new supervised service.
