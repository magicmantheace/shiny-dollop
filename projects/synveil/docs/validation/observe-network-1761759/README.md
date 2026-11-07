# Observer network interval bandwidth — native QEMU validation

Date: 2026-11-07. Gate: `tests/smoke-native-observe.py`
(marker `SYNVEIL_OBSERVE_QEMU_PASS`), extended with network
assertions for this slice. Same method and fixture pattern
as the PSI and disk-throughput evidence.

## What ran

The joined image rebuilt with the bandwidth implementation
(sha256
`a159468398cfdc3e60e3c8cee4c86bf096976497449377db2b81dbc6d0a04164`;
guest binaries stamp source revision `1761759`, which
includes the implementation at `8c5696a`) was booted in QEMU
(TCG, no KVM); the joined baseline smoke
(`SYNVEIL_NATIVE_JOINED_QEMU_ENROLL_LOGIN_WESTON_PASS`)
passed on this exact image, and the observe gate then
captured one real `synctl observe` response from the guest.
Passed on the first attempt.

## Result (guest-written, host-read back)

- `network.status`: **ready**, 2 interfaces in the
  cumulative snapshot.
- `network.bandwidth.status`: **ready** — every interface
  present in both samples was rated; `sample_window_ms`
  101; `unavailable_interfaces` 0; `omitted_interfaces` 0.
- Rated interfaces: `lo` and `sit0`, each with integer
  `rx_bytes_per_sec` / `tx_bytes_per_sec`, all 0 — the guest
  was idle during the sample window and no other interface
  exists in this guest's /proc/net/dev. As with the disk
  slice, the gate asserts shape and coherence, not
  activity; the rate arithmetic (byte delta × 1000 /
  window, floored; churn/decrease withholding; zero-window
  and truncation handling) is proven by host unit tests.
- Also re-verified in the same capture: disk throughput
  `ready`; PSI cpu/memory/io all `ready`; `observe.err`
  empty — the packaged synctl's validation, including the
  new bandwidth consistency checks, accepted the response.

## What this does not establish

- No bandwidth accuracy claim under load (no controlled
  traffic was driven in the guest).
- No connection inventory, traffic inspection, or history:
  bandwidth is a per-request interval measurement only.
- QEMU/TCG only; no physical hardware was tested.

Files: `result.json` (the gate's receipt), `observe.json`
(the full captured response envelope), `observe.err` (empty).
