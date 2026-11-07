# Observer PSI (memory/pressure) — native QEMU validation

Date: 2026-11-07. Gate: `tests/smoke-native-observe.py`,
marker `SYNVEIL_OBSERVE_QEMU_PASS`, first attempt. QEMU
evidence only — no physical hardware is claimed
(`physical_hardware_tested: false` in `result.json`).

## Why this gate exists

ROADMAP Phase 3's memory/pressure item shipped bounded Linux
PSI snapshots with producer-side parsing and host unit tests,
and recorded "Host/guest validation of PSI is required". This
gate is the guest half.

## Method — the fixture pattern, in-guest

The gate boots a private copy of the joined image (sha256
`a80e3266948066fb4c2b98c9c8e8843d5f34dd7f2b8cbb9bb6c5696c70fba737`,
built at `d526e55`; the guest binaries stamp git revision
`d526e555eacc36c4dbbb9d472126751f8476891`, visible in the
fixture core's own audit records during the run), enrolls and
logs in through the graphical login, and in the session
terminal runs one fixed harness command
(`tools/qmp_input.py`, id `observe`).

The system core's socket is root-only by design (0600 in a
0700 directory) and the image offers no root shell, so the
command follows the project's fixture pattern: a user-level
`/usr/sbin/veil-core --socket /var/tmp/observe.sock --once`
serves one connection in the background, and the guest's real
`/usr/bin/synctl --socket … --json observe` queries it. The
compiled producer and client code paths run unmodified
against the real guest kernel state; only the serving
instance is a fixture. Captures land in /var/tmp (the state
partition — the joined image's persistent world-writable
directory) and are read back from the partition after the
session relocks.

## What was required of the real response (`observe.json`)

- synctl's stderr empty (`observe.err`, 0 bytes): the client
  validates the response itself and reports refusal there, so
  an empty file proves the client accepted it.
- Response envelope `ok: true`; result schema
  `synveil.observe/v1`.
- `cpu.utilization` ready: busy 3500 basis points over a
  101 ms window, per-CPU records ready.
- `memory` counters sane (available ≤ total).
- `processes` ready with 98 records.
- **`pressure.cpu`, `pressure.memory`, `pressure.io` all
  `ready`** — the guest kernel is built with `CONFIG_PSI=y`,
  so the ready path is exercised natively, not only the
  unavailable path: cpu some total_stall_us 3,388,981 with a
  present `full` group; memory some total 0 with `full`
  present; io some total 461,286 with `full` present; all
  avg10/60/300 percentages in [0, 100].

Assertions never retry; boot/enroll flakes under TCG retry
the whole boot on a fresh image copy (the audit-v2 gate's
pattern) — this pass needed one attempt.

Harness lessons recorded in the smoke's comments: the serial
AUTH_ACTIVE marker can precede the first presented frame by
minutes under load (patient frame retries, as in the A/B
harness); a just-focused terminal can eat leading characters
(the fixed line carries a sacrificial `echo` segment); and
synctl prints the full protocol envelope — the observe
document is its `result`, which the assertions unwrap.

## What this does not establish

Physical-hardware PSI behaviour; the system (root) core
instance's socket path in production use — unreachable from
the desktop session by design; pressure history, attribution,
or long-term measurement, which remain open roadmap items.
