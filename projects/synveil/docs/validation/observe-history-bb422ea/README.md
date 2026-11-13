# Observer History — Process Lifecycle (Phase 3 slice, ADR 0026)

Evidence for the lifecycle-events slice of the accepted observer
history design: a sampler inside veil-core emits `process_started`
/ `process_exited` events (schema `synveil.observe-event/v1`,
audit-envelope family, telemetry-only — never in the hash-chained
audit journal) into a bounded in-memory ring, served read-only by
the `observe-history` request. The sampler is OFF BY DEFAULT
(owner amendment, 2026-11-07); the gate enables it by policy
(`SYNVEIL_OBSERVE_HISTORY=1`).

## Source

Implementation commit `bb422ea` (history.rs, observer.rs,
lib.rs, synctl). Host tests at that commit: veil-core 186 lib
tests + synctl 10 tests; full veil-core + synctl suites 213
passed, 0 failed.

## Image

Joined native image `f3a4f36f…8547af3` (validation.json in
`out/native-joined/`), built at the implementation source
(gate harness fixes `afd4204` + `1ff65bc` are host-side test
changes only and needed no image rebuild).

## Native gate: SYNVEIL_OBSERVE_QEMU_PASS

`tests/smoke-native-observe.py` (extended), run as `svrunner`
with TMPDIR on the workspace filesystem (the 512 MiB `/tmp`
tmpfs cannot hold the ~680 MiB image copy, and a long TMPDIR
prefix pushes the QMP socket path past the 108-char AF_UNIX
limit — both were hit and worked around during this pass).
**Passed on attempt 1** after the fixture fix (below). The
joined baseline regression on the same image also passed
(`SYNVEIL_NATIVE_JOINED_QEMU_ENROLL_LOGIN_WESTON_PASS`).

The gate's history phase (fixed command
`observe-history` in `tools/qmp_input.py`): the fixture core
runs with the sampler enabled (no `--once`), the ring is
snapshot once (h0), a known `sleep 12` probe is started and
its pid recorded, the ring is snapshot again while the probe
is alive (h1), then once more after it exits (h2). The host
requires the probe's started event in h1 and its exited event
(same pid, same `start_time_ticks`, later sequence, valid final
cumulative counters) in h2.

### Result (`result.json`)

- `passed: true`, `attempts: 1`
- pressure: cpu / memory / io all `ready`
- history: `probe_pid: 219`, `started_sequence: 1`,
  `probe_start_time_ticks: 25201`, `exited_sequence: 3`

### Snapshots

- h0: sampler `enabled: true`, `cadence_ms: 5000`,
  `ring_capacity: 1024`, 0 events (baseline snapshot quiet).
- h1: 3 events retained — the probe's `process_started`
  (sequence 1, start_time_ticks 25201) among them.
- h2: 6 events retained — the probe's `process_exited`
  (sequence 3, same start_time_ticks 25201, user_ticks 0,
  system_ticks 0) follows its started event in the ring.

## What is proven

- The sampler runs inside veil-core at the 5 s cadence with
  the 1024-event ring, enabled by policy only.
- A real process lifecycle in the guest — start, then exit —
  produces exactly the two expected events, in order, with
  matching identity and the exit carrying the final observed
  cumulative counters.
- The ring retains events across queries (the started event is
  still present in h2).
- The existing observe response is unchanged by the slice
  (pressure all `ready` in the same boot).

## What is not proven

- Aggregation/storage slices of the history design (not in
  this pass).
- Between-sample processes (missed by construction, per ADR
  0026) and the wire-limit trim path (not exercised natively;
  unit-tested at host level only).
- No hardware claim: QEMU only.

## Gate history (harness, not product)

The first gate runs typed both fixture lines but died at
`awaiting-relock` on all three attempts: the fixture core
runs forever (unlike the `--once` observe fixture) and holds
the terminal's pty open through its inherited stdio, so the
terminal window never closes and the session never ends. A
preserved screendump showed the shell had exited and later
keystrokes were echoing into a readerless pty. Fixed in
`1ff65bc`: the fixture line ends with `kill %1`. The gate
then passed on attempt 1.

## Rerun

```console
TMPDIR=/home/hatch/.st python3 tests/smoke-native-observe.py
```

(as `svrunner`; see the header for why TMPDIR is set)
