# Test plan — Underreach: Delving Colony

## S1 — sim core

All tests run headless on the VM: `cargo test` in `sim/`, plus the
`scenario` binary (`cargo run --release --bin scenario`).

### Unit tests

- **World**: carving a solid cell makes it carved and returns the
  material; carving an already-carved cell is a no-op; out-of-bounds
  access is rejected.
- **Light**: a lantern lights carved cells within its tier radius and
  nothing through/inside solid rock; a lantern with no fuel lights
  nothing.
- **Path**: BFS finds a route through lit carved cells; the same route
  with the lantern removed (dark) returns no path — delvers do not
  path through darkness.
- **Save/load**: canonical save → load reproduces the SHA-256 state
  hash exactly.

### Scenario test (the S1 acceptance run)

A scripted Shallows colony: camp chamber, shaft, tunnel, ore face.

- **Phase 1 — the dark refuses**: tunnel carved, no lanterns beyond
  camp. Run 200 ticks. Expect: zero ore delivered, zero goods, and a
  `RouteBlocked` entry in the Deep Ledger.
- **Phase 2 — first light**: place lanterns down the shaft and tunnel.
  Expect `FirstLight` ledger entries for the newly lit depths, then run
  up to 4,000 ticks. Expect: at least 3 haul deliveries and at least 2
  converted goods; the delver's mining XP has increased.
- **Determinism**: at a mid-run point, save; continue the original and
  the loaded copy for the same ticks; state hashes must match.

### Results — 2026-11-10 (VM, headless)

- `cargo test` (debug): **8 passed, 0 failed** — 5 unit (world carve /
  bounds, light radius & solid-rock exclusion, dead lantern, path
  requires light) and 3 scenario acceptance tests (phase 1 refusal,
  phase 2 first light + production, save/load roundtrip +
  deterministic continuation).
- `cargo run --release --bin scenario`:
  - Phase 1 (200 ticks): `goods=0, deliveries=0, route-blocked
    entries=1` — Bram cannot reach the face; the refusal is ledgered.
  - Phase 2 (4,200 ticks total): `goods=6, deliveries=3,
    conversions=3, first-light entries=6, mining xp=12`. First light
    recorded at depths 3–6 by the camp lantern at founding, then 7
    and 8 when the network was extended; all 12 ore hauled in 3 loads
    of 4 and converted 2-for-1 into 6 goods.
  - Final state hash:
    `2dfee45db387e84876549580119df42bd03e3d407a4197c91bb39e49d6e91111`.

## Planned (later slices)

- Godot frontend: headless `--verify` load of core state; owner-PC
  visual pass before any frame claims.
- Rescue slice: lantern-clock countdown, failed-rescue permadeath,
  Ledger loss entries.
- Multi-delver scheduling, morale, and accident checks.
- Owner-hardware performance measurement before any frame budget claim.
