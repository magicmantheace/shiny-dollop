# Observer History — Windowed Aggregation (Phase 3 slice, ADR 0026)

Evidence for the aggregation slice of the accepted observer
history design: the veil-core sampler folds its own rated
values into ephemeral in-memory 1-minute buckets (mean/max)
for `cpu.busy`, `memory.used`, `disk.throughput.bps` and
`net.throughput.bps`, served read-only through the existing
`observe-history` request as an `aggregates` object beside
the lifecycle events. The sampler is OFF BY DEFAULT (owner
amendment, 2026-11-07); aggregates are telemetry only —
never in the hash-chained audit journal, never written to
disk; a core restart clears the store. "Storage" in the
ADR 0026 design is this ephemeral store only; durable
storage is not part of the design.

## Source

- `abaeef7` — implementation (`src/veil-core/src/history.rs`,
  `src/veil-core/src/lib.rs`, `src/synctl/src/main.rs`):
  an `AggregateStore` (60 s buckets, 60 retained per series,
  max 64 series by (metric, name), store-wide dropped-bucket
  counting, out-of-order samples skipped) fed from the
  producer's own rated values; the response gains the
  `aggregates` block; the wire-limit fitting trims the
  globally oldest aggregate bucket before dropping any
  event (counted in `response_omitted_buckets`); synctl
  validates the block client-side.
- `4063b7f` — the observe QEMU gate asserts the aggregates:
  structure on every snapshot (60 s buckets, known
  metric/unit pairs, minute-aligned strictly increasing
  starts, mean ≤ max, bucket accounting balances) and
  content on the final snapshot (all four metric families
  present, cpu.busy max ≤ 10,000 bp, memory.used > 0).
- `2545428` — design-doc status (aggregation implemented;
  storage is ephemeral in-memory only).
- `05a31be`, `05a8216` — harness only (below); no guest
  code, no image rebuild.

Host tests at the final tip (re-run for this evidence):
veil-core lib 193 + synctl 10, plus 10 integration tests —
213 passed, 0 failed. (Full workspace: 230 tests, green at
the implementation commit.)

## Image

Joined native image
`a0c9f55b2e0fffaec1dc83eb8db4c41bcef91adc95581be7344012bc9dbd3eb5`
(sha256 re-verified against `out/native-joined/validation.json`
after the build), built at source `2545428` — i.e. the
implementation commit plus the host-side gate extension;
the later harness fixes are host-side test changes only.

## Native gate: SYNVEIL_OBSERVE_QEMU_PASS

`tests/smoke-native-observe.py`, run as `svrunner` with
`TMPDIR=/home/hatch/.st` (guest serial log retained in the
working dir `out/observe-proof/`). **Passed on attempt 2** of the
successful run; `result.json`: `passed: true`,
`failures: []`, pressure cpu / memory / io all `ready`,
probe pid 225 (started sequence 1, exited sequence 5).

The aggregation content, from the three snapshots of one
boot (one shared 1-minute bucket, accumulating at the 5 s
sampler cadence — `h0/h1/h2.json` in this directory):

| snapshot | samples in cpu.busy bucket | cpu.busy mean / max (bp) | memory.used mean / max (bytes) | series | retained buckets |
|---|---|---|---|---|---|
| h0 | 2 | 1571 / 2273 | 200,181,760 / 200,450,048 | 15 | 15 |
| h1 | 4 | 1211 / 2273 | 200,307,712 / 200,450,048 | 15 | 15 |
| h2 | 6 | 956 / 2273 | 200,389,973 / 200,556,544 | 15 | 15 |

Disk series are per device (loop0–loop7, vda, vda1, vda2)
and net series per interface (lo, sit0) — never summed
into a system total; all read 0 B/s in the idle guest.
`dropped_buckets: 0`, `omitted_series: 0` throughout.

## Regressions on the same image

All passed, each on its own marker:

- Joined baseline — `SYNVEIL_NATIVE_JOINED_QEMU_ENROLL_LOGIN_WESTON_PASS`
- Audit v2 — `SYNVEIL_AUDIT_V2_NATIVE_PASS`
- A/B round trip — `SYNVEIL_AB_QEMU_PROOF_PASS`
  (stages S0–S7 + S6b, on a fresh `tools/native_ab.py --build`
  release from the same tree)
- Shell — `SYNVEIL_SHELL_QEMU_PASS`
- Browser/files — `SYNVEIL_BROWSER_QEMU_PROOF_PASSED`
  (on a fresh `--browser` proof-disk build; B0–B7: HTTPS
  with bad-CA refusal, downloads persisted across cold
  reboot, update to v2/slot B and rollback to v1/slot A)

## What is proven

- The sampler folds its rated values into 1-minute
  mean/max buckets while it runs, and `observe-history`
  serves them with correct accounting (the same bucket
  accumulates 2 → 4 → 6 samples across the gate's three
  snapshots; means move, the max holds).
- All four ADR 0026 metric families are served with the
  accepted shapes; synctl accepts the block (any refusal
  would have emptied the `.err`-checked captures).
- The lifecycle events, the plain observe response
  (pressure all `ready`), and every neighbouring
  subsystem's QEMU acceptance are unchanged on the same
  image.

## What is not proven

- Bucket rollover across a minute boundary in the guest
  (the gate's ~35 s history window stays inside one
  bucket; rollover, hour retention and drop counting are
  host-unit-tested only).
- The wire-limit aggregate trim in the guest (unit-tested
  at host level only, like the event trim before it).
- Aggregation on the winged/multi-source edge cases and
  over long uptimes; no hardware claim: QEMU only.

## Gate history (harness and environment, not product)

The first gate run completed the whole guest flow but
failed `h0`: the fixture core had not yet bound its socket
when the first synctl ran (ENOENT), leaving h0 empty while
h1/h2 captured fine. Fixed host-side (`05a31be`): the
fixture line waits, bounded, for the socket file before
the first query. The first form of that wait used
`[ -S … ]`, which the QMP typist cannot type (no bracket
keys in its character map — typing aborted with
`KeyError('[')`); rewritten with typable characters only
and verified against the map (`05a8216`).

Several further runs were lost to the environment, not
the guest: parallel work on the same VM saturated the
host (load > 7 on 4 cores) and QMP keystrokes were
dropped mid-password in enrollment/login; a mid-task VM
reboot wiped the non-root runner user, the restored
libelf headers the kernel build needs, and parts of the
OVMF set (all restored per the standing recipe in
`~/TOOLS.md`); stale proof directories owned by the
pre-reboot runner uid needed the same ownership repair
the audit exporter's strict 0o700/owner checks demand.
The passing run above was taken on the quiet host with
all repairs in place; no assertion was weakened, skipped
or retried inside a boot — the gate's own boot attempts
are its designed retry unit.

## Rerun

```console
TMPDIR=/home/hatch/.st python3 tests/smoke-native-observe.py
```

(as `svrunner`; see the lifecycle evidence for why TMPDIR
is set)
