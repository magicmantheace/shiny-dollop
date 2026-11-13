# Observer interval power — native QEMU validation

Date: 2026-11-07. Gate: `tests/smoke-native-observe.py`
(marker `SYNVEIL_OBSERVE_QEMU_PASS`), extended with
energy/power coherence assertions for this slice. Same
method and fixture pattern as the earlier observe evidence.

## What ran

The joined image rebuilt with the interval-power
implementation (sha256
`4d51e418ad85b69ec89de80f6659c2f4f051f7e6411f1eafb25cdee68727d48a`;
guest binaries stamp source revision `95ede21`, which
includes the implementation at `8abe685`) was booted in
QEMU (TCG, no KVM); the joined baseline smoke
(`SYNVEIL_NATIVE_JOINED_QEMU_ENROLL_LOGIN_WESTON_PASS`)
passed on this exact image, and the observe gate captured
one real `synctl observe` response from the guest (second
boot-pair attempt; the gate's assertion set passed with no
failures).

## Result — and its honest limit

The QEMU guest exposes **no powercap sysfs**: the captured
`energy` object is the bare unavailable form
(`{"status": "unavailable", "zones": []}`), and
`energy.power` is therefore coherently **absent** — exactly
the contract the implementation defines (no power object
when either interval scan cannot run) and the gate asserts.
Disk throughput, network bandwidth, and PSI were
re-verified `ready` in the same capture, and `observe.err`
is empty.

So this native run validates the *absence path* and the
response coherence only. The rating path — per-zone average
microwatts over the window, single-wrap accounting at
`max_energy_range_uj`, withholding for vanished zones or
changed wrap ranges — is proven at host level (veil-core
unit tests over constructed scans and real fixture trees),
not in a guest, because no QEMU configuration here exposes
RAPL zones. That is the same evidentiary shape the original
cumulative energy implementation had at `bca81e5`.

## What this does not establish

- No in-guest power reading of any kind.
- No accuracy claim for the microwatt figures beyond the
  host-proven arithmetic.
- QEMU/TCG only; no physical hardware was tested (owner
  hardware with real powercap zones is where a positive
  native reading can first exist).

Files: `result.json` (the gate's receipt), `observe.json`
(the full captured response envelope), `observe.err`
(empty).
