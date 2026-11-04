# MUSE_HANDOFF — Milky Way Colonization Simulator

State as of **2026-11-04**, end of slice S1. Branch
`milky-way-colonization-sim/foundation` (extends the S0 commits;
not pushed by the S1 builder — Nyx verifies and pushes to draft
PR #29).

## What S1 delivered

The headless Rust sim core in **`sim/`** (crate `mwcs-sim`, zero
third-party dependencies of its own; it path-depends on the S0
pipeline crate for the star-table reader and SHA-256):

- `src/catalog.rs` — in-memory view of the S0 table (`Galaxy`,
  `StaticStar`, `StaticPlanet`) plus a canonical catalog fingerprint
  used to bind saves to their galaxy.
- `src/state.rs` — the simulation itself: `Campaign` with sparse
  per-system state (`BTreeMap<StarId, SystemState>`) over the inert
  catalog; survey state unknown → surveyed, claims, colonies
  (population, development, specialization slot, five strategic
  stockpiles, energy flow, defence placeholder, construction queue);
  ships as state machines (at system / surveying / en route /
  stranded en route / stranded at system); the daily tick with a
  monthly settlement every 30 days.
- `src/profile.rs` — the profile revealed by a survey. Real catalog
  planets stay real (habitability from measured eq. temperature and
  radius); systems without catalog planets get a generated profile
  from the star's real properties + campaign seed, with every
  generated planet explicitly labelled `Generated`.
- `src/rng.rs` — SplitMix64 seeded RNG owned by the core. Profile
  generation uses per-star child streams derived from
  `(campaign seed, star id)`, so decision order cannot leak into a
  system's fixed contents.
- `src/save.rs` — canonical binary serialization (sorted maps, raw
  float bits, length-prefixed strings) → SHA-256 state hash; the
  save format is that payload behind a `MWSS` header, verified
  against the galaxy fingerprint + star count on load.
- `src/policy.rs` — the deterministic scripted policy (the S1 test
  harness driver, **not** the §6 AI — that is S3).
- `src/main.rs` — `sim-cli`: starts a campaign at Sol (ruling
  §11.7), runs the scripted policy, prints one summary line per
  game year.

Rules implemented from the design: 1 tick = 1 game day (§2);
colonization pipeline survey → claim → found, colony ship consumed
(§3); credits global + energy as a per-system flow, five strategic
resources stockpiled per system with fuel first-class (§4); ship
range = tank ÷ burn, movement burns fuel by distance, orders beyond
range or beyond the fuel aboard are refused, refuelling at colonies,
stranded ships per §5.2 (only via a deliberate unchecked one-way
order in S1 — no combat/lost-depot causes exist yet).

## Model choices where the design left room

- **Economy constants** (design §4 gives structure, not numbers):
  population income `pop × 0.045 × (0.7 + dev × 0.08)`/month,
  upkeep `2 + dev + pop × 0.004`/month; production formulas keyed
  to development, habitability, and profile traits, with
  specialization multipliers (Refinery ×3 fuel, Industrial ×2.5
  alloys, Agricultural ×2.2 supplies, Trade Hub ×1.4 income).
  Supplies are the binding upkeep: production + stored buffer first,
  growth stops when unsupplied, decline after 3 unsupplied months,
  abandonment after 12 (design §3's slow, telegraphed loss).
- **Growth:** logistic toward capacity
  `100 + habitability% × 25 + development × 400` (millions).
- **Development** rises one level per supplied year (to a S1 cap of
  5) when population exceeds `development × 150`M; specialization
  unlocks at development 3, one slot in S1 (the second slot at 7 is
  a later-slice concern).
- **Starting position:** homeworld population 1,200M, development 3,
  15,000 credits, one surveyor (75 ly range) and one colony ship
  (75 ly range) in orbit. Ship construction is a per-colony queue
  (surveyor 90 days / 400 credits / 12 alloys; colony ship 240 days
  / 1,500 credits / 45 alloys).
- **Survey duration:** deterministic 24–37 days + 2 per known
  catalog planet, derived from the seed and star.
- **Stranding in S1:** normal dispatch can never strand a ship.
  `dispatch_ship_unchecked` is the explicit one-way order of §5.2;
  a ship arriving on exactly empty tanks can still survey/found
  (local work) but cannot depart until refuelled; a ship stranded
  en route awaits tanker mechanics from a later slice.
- **No routes/trade/gates/AI/diplomacy/war** — S3–S5 by design.
  Colonies are self-supplied from local production + buffers in S1;
  the route layer (§4.3) arrives with trade in S4.

## Test state (all run 2026-11-04 on this VM)

- `sim`: `cargo test` **19/19** (6 unit + 13 integration,
  `sim/tests/s1.rs`) — determinism across advance chunking,
  save/load-at-year-5 continuity, range/fuel refusals, exact fuel
  burn, stranding, claim-before-founding, bounded growth,
  construction, scripted expansion, 100-year endurance. Detail in
  `docs/TEST_PLAN.md`.
- `pipeline`: `cargo test` **22/22** (unchanged by S1).
- Viewer: Godot `--verify` still all-pass (unchanged by S1).
- No wall clock / external RNG in `sim/src` (grep-verified, see
  TEST_PLAN).

## Demo — scripted 25-year campaign (verbatim)

`cargo run --release --bin sim-cli -- --years 25`, seed 42, real
113,393-star table:

```text
campaign_start seed=42 stars=113393 home=0 
year=1 day=365 surveyed=8 colonized=3 population_millions=1214.64 fuel_stock=1039.27 credits=12286.58 ships=1
year=2 day=730 surveyed=16 colonized=4 population_millions=1230.56 fuel_stock=1207.87 credits=11041.47
year=3 day=1095 surveyed=24 colonized=5 population_millions=1248.02 fuel_stock=1258.53 credits=9797.66
year=4 day=1460 surveyed=29 colonized=7 population_millions=1266.14 fuel_stock=1439.54 credits=7100.39
year=5 day=1825 surveyed=29 colonized=8 population_millions=1284.17 fuel_stock=1642.80 credits=5986.90
year=6 day=2190 surveyed=34 colonized=9 population_millions=1303.84 fuel_stock=1876.14 credits=4744.48
year=7 day=2555 surveyed=42 colonized=10 population_millions=1322.18 fuel_stock=2129.47 credits=4864.60
year=8 day=2920 surveyed=46 colonized=10 population_millions=1340.41 fuel_stock=2165.29 credits=5082.65
year=9 day=3285 surveyed=55 colonized=10 population_millions=1358.79 fuel_stock=2331.53 credits=5185.70
year=10 day=3650 surveyed=59 colonized=10 population_millions=1377.31 fuel_stock=2356.33 credits=5423.81
year=11 day=4015 surveyed=63 colonized=11 population_millions=1396.22 fuel_stock=2615.88 credits=4172.06
year=12 day=4380 surveyed=72 colonized=11 population_millions=1416.59 fuel_stock=2810.06 credits=4296.96
year=13 day=4745 surveyed=78 colonized=11 population_millions=1435.54 fuel_stock=2848.25 credits=4480.68
year=14 day=5110 surveyed=84 colonized=11 population_millions=1454.62 fuel_stock=2883.49 credits=4674.77
year=15 day=5475 surveyed=91 colonized=11 population_millions=1473.83 fuel_stock=3062.73 credits=4854.30
year=16 day=5840 surveyed=91 colonized=11 population_millions=1493.17 fuel_stock=3179.73 credits=5219.35
year=17 day=6205 surveyed=91 colonized=11 population_millions=1512.64 fuel_stock=3334.22 credits=4094.99
year=18 day=6570 surveyed=91 colonized=12 population_millions=1534.12 fuel_stock=3603.71 credits=4496.00
year=19 day=6935 surveyed=91 colonized=12 population_millions=1553.84 fuel_stock=3768.14 credits=4858.00
year=20 day=7300 surveyed=97 colonized=12 population_millions=1573.69 fuel_stock=3957.33 credits=5080.79
year=21 day=7665 surveyed=97 colonized=12 population_millions=1593.65 fuel_stock=4101.13 credits=5464.45
year=22 day=8030 surveyed=97 colonized=13 population_millions=1613.97 fuel_stock=4361.55 credits=4359.02
year=23 day=8395 surveyed=97 colonized=13 population_millions=1634.16 fuel_stock=4551.30 credits=4728.67
year=24 day=8760 surveyed=97 colonized=13 population_millions=1656.15 fuel_stock=4758.92 credits=5141.59
year=25 day=9125 surveyed=99 colonized=13 population_millions=1676.56 fuel_stock=4956.91 credits=5484.31
final_state_hash=7e64c3223b1604eb9a1ee5f97401edfb3ee10a6741f14d7e554be638c8ea6bad
```

(The year lines above omit the trailing `ships=1` field for width;
the binary prints it. The hash is over the exact run.)

Performance: the same harness at `--years 100` completes in
**~0.78 s wall** on this VM (release), ending at 256 surveyed /
34 colonized. VM CPU number for the core only — no frame claims.

## Gotchas found in S1 (don't rediscover these)

- A surveyor that chains single affordable legs away from colonies
  *will* maroon itself (found at Teegarden's Star, 0.04 fuel). The
  scripted policy's return-reserve rule is load-bearing; a future
  AI/frontend needs the same prudence or tanker support (§5.2).
- Arrival on exactly empty tanks must not block the arrival order
  itself (survey/found), or the ship deadlocks permanently.
- `cargo` needs the full synveil-tools env
  (`RUSTUP_HOME`/`CARGO_HOME`/`RUSTUP_TOOLCHAIN=1.99.0-...`); a bare
  `cargo` invocation fails with a rustup toolchain error.
- The sim depends on the pipeline crate by path; the binary star
  format contract (`pipeline/src/table.rs`) is unchanged in S1.

## Offline progression — RULED BY ADAM 2026-11-04: FULL CATCH-UP

Adam's ruling, in his words: **"Full catch-up — the galaxy lives
while I'm away."** On load, a save advances by the full real
elapsed time since it was saved (one game day per real day at the
1× baseline), with **no cap**. Capped catch-up (the builder's
recorded recommendation, ~30 days) and frozen-while-closed were
considered and not chosen.

**No code in S1 embodies this yet** — the core is step-driven and
only advances when a driver calls `advance()`; its determinism
makes the policy implementable without a redesign. Implementation
belongs to S2, when save/load is wired into the frontend:

- Saves need a trustworthy saved-at timestamp; on load, the S2
  driver advances the core by the elapsed whole days before handing
  control to the player.
- The player must be able to review what happened during the
  catch-up (event history/summary) — unwatched months or years of
  arrivals, settlements, and (S3+) AI expansion and wars cannot
  land silently.
- Long absences mean long catch-up runs; the measured tick rate
  (100 game-years ≈ 0.78 s on this VM, release build) makes even
  multi-year absences cheap to simulate.

## Unverified / owner-PC gates

- FPS and rendering feel on Adam's RTX 3060 (no FPS claims made).
- Interactive picking/orbit with a real mouse; Windows export.
- Offline progression is settled (full catch-up, above); S2 implements it when wiring save/load into the frontend. S2 itself still needs Adam's go-ahead.

## Next slice

**S2 — Playable colonizer**, only on Adam's go-ahead: Godot
frontend over this core (map UI, system panel, colonization loop
from Sol, save/load in the frontend). Save/load implements the
full-catch-up offline-progression ruling (above).
