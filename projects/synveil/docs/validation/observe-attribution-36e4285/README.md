# Observer per-process CPU attribution — native QEMU validation

Date: 2026-11-07. Gate: `tests/smoke-native-observe.py`
(marker `SYNVEIL_OBSERVE_QEMU_PASS`), extended with
`processes.utilization` assertions for this slice. Same
method and fixture pattern as the earlier observe evidence.

## What ran

The joined image rebuilt with the attribution
implementation (sha256
`c136d431e5349249b502fa4d1492e94665d069553fe633942aab3325d3ad3566`;
guest binaries stamp source revision `36e4285`, which
includes the implementation at `b946269`) was booted in
QEMU (TCG, no KVM); the joined baseline smoke
(`SYNVEIL_NATIVE_JOINED_QEMU_ENROLL_LOGIN_WESTON_PASS`)
passed on this exact image, and the observe gate captured
one real `synctl observe` response from the guest. Passed
on the first attempt.

## Result (guest-written, host-read back)

- `processes.utilization.status`: **ready** — all 97
  processes in the snapshot were rated over the 101 ms
  window; `unavailable_processes` 0.
- The rated processes' `busy_basis_points` sum to 2223,
  below the same response's aggregate `cpu.utilization`
  busy figure of 3704 — the expected relationship, since
  the aggregate also counts kernel time not attributed to
  any process. (The gate asserts the hard bound: sum ≤
  10000 plus per-record rounding slack.)
- The busiest processes read 741 bp each (~7.4% of total
  machine capacity) — the desktop session's own processes
  during login settle.
- Also re-verified in the same capture: PSI cpu/memory/io
  `ready`; disk throughput `ready`; network bandwidth
  `ready`; `observe.err` empty — the packaged synctl's
  validation, including the new utilization consistency
  checks (omission-count agreement with the snapshot, PID
  ordering, the 10000 bp bound), accepted the response.

## What this does not establish

- No lifecycle or delta event stream: attribution is a
  per-request interval measurement, like the other
  windowed metrics; processes born inside a window are
  withheld, not tracked.
- No history or aggregation.
- QEMU/TCG only; no physical hardware was tested.

Files: `result.json` (the gate's receipt), `observe.json`
(the full captured response envelope), `observe.err`
(empty).
