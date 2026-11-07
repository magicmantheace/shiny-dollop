# Observer history & lifecycle — design

Status: **Accepted (2026-11-07)** — see
[ADR 0026](adr/0026-observer-history-lifecycle.md) for the
decision record and the owner's answers to the questions
below. This document records the accepted design for the
remaining Phase 3 observer items. The first slice
(lifecycle events) is authorized by the acceptance;
storage/aggregation follow as their own slices.

## Context

The observer (`synveil.observe/v1`) is deliberately
stateless: every response is derived from kernel files at
request time, and the interval metrics shipped in
2026-11 (disk throughput, network bandwidth, interval
power, per-process attribution) sample twice *inside one
request*. Four roadmap items cannot be built that way:

- process lifecycle event/delta tracking,
- event normalization,
- ephemeral telemetry storage,
- historical aggregation.

All four need a component that remembers observations
across requests. The open design question is where that
memory lives and who owns the sampling cadence.

## Proposed shape

**A sampler inside veil-core, off by default.** The core
already supervises the system and owns the audit journal.
A bounded sampler thread, when enabled by policy (owner
amendment, 2026-11-07: the sampler stays **off by default
until a consumer exists** — acceptance of this design does
not switch it on):

1. Take an observe snapshot at a fixed cadence
   (proposal: 5 s) using the same producer code — no new
   kernel parsing.
2. Diff consecutive process snapshots by
   (pid, start_time_ticks) identity — the identity the
   snapshot already guarantees — and emit lifecycle events
   (`process_started`, `process_exited` with final
   cumulative counters) into a bounded in-memory ring
   (proposal: 1024 events). Short-lived processes that
   start and exit between samples are *missed by
   construction* and the design says so; catching them
   would need eBPF or netlink process events, which is a
   different, larger proposal.
3. Normalize events into the audit record envelope family
   (`synveil.observe-event/v1`) so consumers handle one
   record discipline; events are telemetry, not audit —
   they do not enter the hash-chained journal.
4. Keep an ephemeral aggregate store in memory only:
   per-metric ring buffers of windowed aggregates
   (1 min buckets: mean/max for utilization, throughput,
   bandwidth, power) with a hard size bound and no
   persistence. A new read-only request
   (`observe-history`) serves events and aggregates;
   nothing is written to disk, and a core restart clears
   everything — that is what "ephemeral" buys: history
   without a telemetry database on the state partition.

## Explicit non-goals

- No persistence across reboot, no on-disk telemetry
  store (that would reopen the state-partition budget and
  the retention questions the audit design answered only
  for the journal).
- No sub-cadence lifecycle truth (no eBPF/netlink in this
  proposal).
- No policy, evaluator, or optimization consumer; this is
  observation only, per the Phase 3 scope.

## Owner answers (2026-11-07)

The questions this proposal posed, and the owner's
answers, verbatim in substance:

1. **Sampling ownership**: sampler inside veil-core, as
   proposed.
2. **Cadence and bounds**: 5 s cadence, 1024-event ring,
   1 min buckets accepted — with the amendment that the
   sampler is **off by default until a consumer exists**.
3. **Exposure**: a separate read-only `observe-history`
   request, as proposed.
4. **Aggregation set**: 1 min mean/max buckets for the
   four windowed metrics (utilization, throughput,
   bandwidth, power), as proposed.

## First slice (authorized by the acceptance)

Lifecycle events only: the sampler + process diff + ring,
served read-only, host-tested with fixture snapshot pairs
and natively validated with the observe QEMU gate extended
to start and stop a known process between samples.
Storage/aggregation would follow as their own slices.
