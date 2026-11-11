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

## S2 — colony breadth (verified 2026-11-10, VM headless)

- `cargo test`: 13/13 green (5 unit, 3 S1 scenario, 5 S2 scenario).
- S2 scenario run (6,000 ticks, network lit from the start): 5 delvers
  (3 founders + 2 recruits), 6 goods, 80 food in stores, 42 harvests,
  3 deliveries, 2 recruits, 0 spirits-fallen. Final hash
  `15219b37986f16972ffb0c07168321aa9f466c5b9cb52e194d4cb7a569eb32dd`
  (hashes change as the sim model evolves; determinism is proven by
  the save/load + twin-run tests, not by hash stability across slices).
- Proven by tests: job division (miner fills the face cache, hauler
  runs it home, farmer's harvests reach stores), recruitment arrival
  on schedule while fed, morale collapse + `SpiritsFallen` in a
  starved colony, save/load continuation bit-identical.
- Balance notes (observed, tuned once): hunger decay and plot growth
  were re-tuned after the first run produced a 1,129-food surplus;
  a starving delver now cannot rest past half energy, which is what
  makes morale actually fall when the food runs out.

## S3 — the dark bites (verified 2026-11-10, VM headless)

- `cargo test`: 18/18 green (adds 5 S3 scenario tests).
- Choreographed proofs: a delver kills a gloam rat in total darkness
  (kill credited in the Ledger, combat XP gained, delver bitten but
  standing); a downed delver is carried home by a rescuer before the
  900-tick clock expires (`DelverRescued`, hp restored to 30); a
  downed delver alone is lost at clock-out (`DelverLost`, name kept);
  killing the tunnel lanterns strands the miner at the face on the
  600-tick dark clock, ending in a loss.
- S3 scenario run (6,000 ticks): colony produced 20 goods under
  threat; 5 critters spotted and 5 slain, 0 downed, 0 lost. Honest
  read: in this run the lantern network itself did the repelling —
  every incursion burned in the light before reaching a delver
  (all combat XP stayed 0). Delver combat is proven by the corridor
  tests above, not by this run.
- Design rule that fell out of implementation: nobody works in the
  dark — a delver cut off by a light failure stops work and waits
  (for rescue, a relight, or the clock).

## Planned (later slices)

- Godot frontend: headless `--verify` load of core state; owner-PC
  visual pass before any frame claims.
- Owner-hardware performance measurement before any frame budget claim.
