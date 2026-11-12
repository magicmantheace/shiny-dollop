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

## S5 — the Fungal Reaches (verified 2026-11-10, VM headless)

- `cargo test`: 24/24 green (adds 6 S5 scenario tests).
- The gate set, proven piece by piece: an unmasked miner working the
  fungal face gets the spore-cough (`DelverSick`) and still hauls oil
  home; a crafted mask (2 goods) protects its wearer entirely;
  tier-2 lantern placement is refused with no oil in stores and
  succeeds for exactly 1 oil once it flows; a herbalist clears a
  spore load of 90 to well in ~60 ticks vs ~400 for clean air alone
  (control run in the same test).
- Recombination groundwork: `hazards_at(y)` — Shallows clean, Fungal
  spore, then cycling unions (spore+flood, spore+heat, flood+heat)
  every 8 depths, asserted as data. Only `spores` has mechanics in
  this slice; `flooded`/`hot` are modelled, not yet simulated.
- S5 scenario run (6,000 ticks, two masks crafted): 6 delvers alive,
  19 fungal oil stockpiled, tier-2 placement succeeds, **0 sick
  events** — with the miner masked, the hauler's short trips clear
  between runs; sustained unmasked mining is what sickens (test 1).
- Two design rules fell out of implementation failures, both kept:
  tier-2 oil cost is a flat 1 per lantern (a per-fuel charge made
  scenario lanterns silently unaffordable and broke the S3 rescue
  test — caught by that test), and a herbalist's patient stays a
  patient until well (<30 spore), not until merely not-critical.

## S4 — Godot frontend (verified 2026-11-10, VM headless)

- Bridge: `cargo test` 25/25 (adds a bridge acceptance test that
  drives an S3 colony to production through the file protocol
  alone: init → light_the_way → 4,000 ticks → goods ≥ 1).
- Frontend: `godot --headless -- --underreach-verify` prints
  `UNDERREACH_VERIFY_PASS goods=20 delvers=5 floor_instances=15
  tick=4000` — the scene initialises the colony through the bridge,
  issues the network command, drives 4,000 ticks, and the rendered
  entity set matches the sim view exactly.
- The view is a depth slice (one sim layer at a time); entities use
  Game Asset Builder catalog GLBs (snow-goblin delver stand-in,
  ember-dragon critter stand-in, treasure-chest stockpile,
  mushroom-cluster plots — provenance + shas in `frontend/README.md`).
- **Not verified:** anything visual. Godot's headless driver on this
  VM produces no viewport image (a capture attempt failed cleanly
  and the code path was removed rather than shipped unproven). A
  first on-PC pass ran 2026-11-12 after the owner lifted the PC
  testing stop — engine-verified live (see the on-PC section
  below) — but the workstation was locked, so screenshots captured
  only the Windows lock screen. Rendered appearance remains
  unverified, as do all frame claims.

## Asset swap — dedicated delver, lantern, cot (verified 2026-11-11, VM headless)

- The builder's dedicated delver GLB (catalog sha256
  `7ab7262b7eeb…`, arm-separation-gated A-pose build) replaced the
  snow-goblin stand-in as `DELVER_SCENE`; the Tier-1 lantern prop
  (`5dffb6360730…`) replaced the emissive-sphere lantern visual
  (OmniLight + emissive flame marker kept); the cot prop
  (`67e070f2012…`) replaced the plain bed box. Frontend copies are
  byte-for-byte — sha256 of the copies matches the catalog values.
- `godot --headless -- --underreach-verify` after the swap prints
  the identical pass line as S4: `UNDERREACH_VERIFY_PASS goods=20
  delvers=5 floor_instances=15 tick=4000`, with no errors or
  warnings in the full output.
- A one-off load check (temporary script, run then deleted)
  instantiated all three GLBs in Godot: delver 1 mesh / 4 animation
  clips (idle, walk, run, bounce), lantern 1 mesh, cot 1 mesh.
- Sim untouched: `cargo test` 25/25 and the `scenario` binary run
  repeated after the swap, same results.
- **Not verified:** the visual appearance of the delver, lantern,
  and cot in the rendered scene — headless verify proves load and
  logic, not looks. The on-PC visual pass remains the outstanding
  check, as do all frame claims.

## On-PC pass — engine-verified live (2026-11-12)

- The owner lifted the full PC testing stop on 2026-11-12. The sim
  bridge was cross-compiled on the VM for Windows
  (`x86_64-pc-windows-gnu`; `bridge.exe` sha256 `5f374368…`) — the
  PC has no Rust toolchain — so the pass ran against a genuinely
  live sim stepping on the PC, not a state snapshot.
- Frontend + bridge staged at `D:\bridge-work\underreach-visual\`
  and hash-verified on the PC: `delver.glb`, `lantern.glb`, and
  `cot.glb` copies match the builder catalog shas.
- A first windowed launch threw repeated script errors (prop
  scenes loading as null) — traced to the missing Godot import
  cache in the staging, not project code. After a headless editor
  import pass on the PC, the project's own check printed
  `UNDERREACH_VERIFY_PASS goods=20 delvers=5 floor_instances=15
  tick=4000` on Windows — identical numbers to the VM.
- Windowed relaunch on the RTX 3060 (OpenGL/NVIDIA per the engine
  log): zero script errors (stderr 0 bytes); the state file
  changed on every sample — the sim was live and stepping. Godot
  was closed afterwards and verified gone.
- **Not verified:** rendered appearance. The workstation was
  locked (LogonUI) throughout, so all screenshots captured only
  the Windows lock screen; the captures were deleted rather than
  kept as misleading "game" images. The staging and import cache
  persist on the PC, so the capture redo is minutes of work once
  the PC is unlocked. Animation motion was not observed; clip
  playback rests on the headless verifies.

## Asset swap — gloam-lurker critter (verified 2026-11-12, VM headless)

- The builder's gloam-lurker GLB (catalog sha256 `f0c881cb9bd3…`,
  builder branch `game-asset-builder/underreach-assets` @
  `328bca3`) replaced the ember-dragon stand-in as `CRITTER_SCENE`;
  the dragon file is kept, now unused. The frontend copy is
  byte-for-byte — sha256 of the copy matches the catalog value.
  The asset passed the builder's leg-separation gates before
  cataloguing (concept preflight; posed renders of rest and the
  idle/walk/run/shiver apexes plus a beyond-spec stress pose —
  legs separate with belly daylight in every shipped pose; the
  stress pose only shows a neck/head weight artifact, recorded in
  the builder docs).
- `godot --headless -- --underreach-verify` after the swap prints
  the identical pass line: `UNDERREACH_VERIFY_PASS goods=20
  delvers=5 floor_instances=15 tick=4000`.
- Sim untouched: `cargo test` 25/25 and the `scenario` binary run
  repeated after the swap, clean to tick 6000.
- **Not verified:** the lurker's in-engine appearance and clip
  playback — load is proven by the verify run; looks await the
  unlocked-PC capture redo above.

## Planned (later slices)

- Owner-PC visual pass of the frontend; performance measurement
  before any frame budget claim.
- The dedicated gloam-lurker asset once it is built (not yet in the
  builder catalog); the ember-dragon stands in until then.
