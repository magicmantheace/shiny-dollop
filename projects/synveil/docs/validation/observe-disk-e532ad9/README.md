# Observer disk interval throughput — native QEMU validation

Date: 2026-11-07. Gate: `tests/smoke-native-observe.py`
(marker `SYNVEIL_OBSERVE_QEMU_PASS`) — the same gate as the
PSI validation, extended with disk assertions. This folder is
its evidence for the disk interval-throughput slice.

## What ran

Same joined image lineage and same method as the PSI
evidence (observe-psi-d526e55): the current joined image
(sha256
`1a6abd0a60460ca1c0d61ab49dfda5fd43ce48f48f8fe1312e742f2f3502151e`;
guest binaries stamp source revision `e532ad9`, which
includes the throughput implementation at `97debb8`) was
booted in QEMU (TCG, no KVM), enrolled and logged in through
the normal graphical flow, and the observe fixture captured
one real `synctl observe` response from the guest's own
/proc. The joined baseline smoke
(`SYNVEIL_NATIVE_JOINED_QEMU_ENROLL_LOGIN_WESTON_PASS`) also
passed on this exact image before the observe run. Passed
on the first attempt.

## Result (guest-written, host-read back)

- `disk.status`: **ready**, 11 devices in the cumulative
  snapshot.
- `disk.throughput.status`: **ready** — every device present
  in both samples was rated; `sample_window_ms` 101;
  `unavailable_devices` 0; `omitted_devices` 0.
- Rated devices: loop0–loop7, vda, vda1, vda2 — each with
  integer `read_bytes_per_sec` / `write_bytes_per_sec`. All
  rates were 0 in this capture: the guest was idle during
  the 100 ms sample window, and zero is the truthful rate.
  The gate asserts shape and coherence, not activity; the
  rate arithmetic itself (sector delta × 512 × 1000 /
  window, floored; churn/decrease withholding; zero-window
  and truncation handling) is proven by host unit tests.
- PSI re-verified in the same capture: cpu/memory/io all
  **ready**; `observe.err` is empty — the packaged synctl's
  own validation, including the new throughput consistency
  checks, accepted the response.

## What this does not establish

- No throughput *accuracy* claim under load: no controlled
  I/O workload was driven in the guest, so the rates are
  proven well-formed and honestly zero at idle, with the
  arithmetic proven at host level — not calibrated against
  a known in-guest workload.
- No persistent history or aggregation: throughput is a
  per-request interval measurement only.
- QEMU/TCG only; no physical hardware was tested.

Files: `result.json` (the gate's receipt), `observe.json`
(the full captured response envelope), `observe.err` (empty).
