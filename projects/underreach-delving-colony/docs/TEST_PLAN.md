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
  kept as misleading "game" images. Animation motion was not
  observed; clip playback rests on the headless verifies.
- **Capture redo (2026-11-12, workstation unlocked):** staging
  restaged from branch tip `3cca4f2` (lurker swap included; all
  GLB shas re-verified on the PC), import pass redone, project
  check again `UNDERREACH_VERIFY_PASS` with identical numbers.
  (Wrinkle: the verify needs `UNDERREACH_BRIDGE` set to the
  release `bridge.exe`; without it the frontend falls back to a
  non-existent debug path.) The live run climbed past tick 3,783
  with the HUD advancing and zero script errors — **but the 3D
  viewport is pitch black in every capture** while the live
  `state.json` held 15 carved/lit cells, 4 delvers, and a lantern
  at the viewed layer beside the camera target. Nothing 3D is
  drawn: no terrain, models, light pools, or name labels.
  Appearance is therefore still unverified — now blocked on this
  rendering defect, not on access. Root cause unproven; the
  conflict is recorded in `docs/MUSE_HANDOFF.md` (rule 3).

## Black-viewport diagnosis — no defect reproduces (2026-11-12)

- Owner gave the go the same day. Method: read `frontend/main.gd`
  end to end first (camera, environment, MultiMesh setup, entity
  sync), then controlled launches of the UNMODIFIED staged build
  on the PC (`UNDERREACH_BRIDGE` set to the release `bridge.exe`,
  window placed fully on-screen with `--position 100,60`).
- **The world renders.** Screenshots (viewed, incl. a centre crop)
  show: lit tan floor tiles with grid seams (MultiMesh floors in
  the lit colour), dark rock-rim walls, the treasure chest, three
  cots, the lantern prop with a warm OmniLight pool on the floor,
  and standing delver figures. Two scenarios (s3: 3 delvers, tick
  804+; s5: 4 delvers incl. the Herbalist, Goods 4), two separate
  process instances, and a minimize/restore cycle in between —
  rendering intact in every capture.
- **Pixel evidence on the original captures:** all three redo
  captures sample 100% uniformly (5,5,11) across the viewport —
  exactly the Environment background colour. The camera WAS
  active and the environment WAS rendering in that session; what
  never appeared is geometry. That session's window spent its
  life mostly off-screen / behind other windows (it had to be
  chased by minimizing the owner's apps), and the carved room is
  small and centred — the captures' visible areas never contained
  it. The exact historical mechanism is not provable from here;
  what is proven is that no code path in the frontend reproduces
  it under controlled conditions.
- **Ruled out, each with evidence:** camera never made current
  (background + full scene render; Godot activates the first
  camera), environment/ambient setup (background is the env
  colour; scene is lit by sun + ambient + lantern omni),
  MultiMesh instance colours under gl_compatibility (floor/rock
  instance colours render distinctly), world-node transforms
  (room sits at the camera target in frame), GLB load failure
  (chest/cots/lantern/delvers all draw), minimize/restore
  swapchain loss (post-cycle capture renders).
- **Disposition:** no frontend code change — there is no
  reproduced defect to fix, and changing code against an
  unreproduced report is how this record got muddy in the first
  place. The rule-3 conflict in `docs/MUSE_HANDOFF.md` is closed
  as capture-conditions, with the protocol lesson recorded there.
  VM checks after the pass: `cargo test` all suites ok (25/25),
  `scenario` clean to tick 6000, headless verify again
  `UNDERREACH_VERIFY_PASS goods=20 delvers=5 floor_instances=15
  tick=4000`.
- **Still unverified:** a critter (gloam-lurker) in frame on PC —
  both live scenarios sat at Critters 0 for the whole session;
  name-label legibility at capture zoom (labels exist in code;
  figures visibly re-pose between captures, but clip playback as
  such rests on the headless verifies); layer switching on PC
  (Godot's UI exposes no UIA controls to the bridge and there is
  no key-injection route; the layer path is the same
  `rebuild_layer` the verify exercises). Cots read plain white at
  capture zoom — cosmetic, matches the prop's pale paint; noted,
  not treated as a defect.

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

## S6 — procedural floor generation (verified 2026-11-12, VM headless)

Branch `underreach-delving-colony/floor-generation`. Design
record: `docs/FLOOR_GENERATION.md`. Save hashes for S1–S5 shift
in this slice (the save gains `world_seed` and `floor` fields);
behaviour numbers are unchanged, and determinism is proven by
the twin-run tests as before.

### Generator tests (`sim/tests/gen_floor.rs`, 10 tests)

- **Purity:** same seed + floor → identical world hash and
  layout across runs; floors 1–4 generated standalone equal
  floors generated sequentially and interleaved; seeds 1/2/3 →
  pairwise different floor 1s; floor 1 ≠ floor 2 for one seed.
- **Network guarantees across seeds 1–16 + demo seed
  `0x5EED0007`:** entry → descent reachable via passages alone
  every time; measured descent network distance **25–45**
  (guarantee ≥ 24, and the layout's recorded distance equals
  the measured one); every connected cavity reached, every
  sealed cavity unreached; on-network dens exactly **2** at
  distances **18–36** (guarantee ≥ 2 at ≥ 10); sealed dens 0–1
  (minority); node graph 8 nodes / 8 links (one loop); camp room
  intact; 3 faces with carved stands and ore rock; 6 veins with
  at least one embedded pocket.
- **Hazards:** the world's Loose/BadAir cells are exactly the
  layout's pockets; every bad-air cell at y ≥ 6; loose 7–12
  cells, bad air 5–8 cells per floor across the spread.
- **RNG separation:** the gen scenario starts with
  `rng_state == world_seed`, and `open_floor1` draws nothing.
- **Save/load:** generated-floor sim saved at tick 500 reloads
  to the identical hash, floor record included; twin
  continuation for 300 ticks stays identical.
- **Colony loop on the generated floor:** 200 dark ticks →
  goods 0, deliveries 0, RouteBlocked ≥ 1; after `open_floor1`,
  6 000 ticks → deliveries ≥ 3, goods ≥ 2 (actual 24), nobody
  lost.
- **Rescue on generated geometry:** a deep lurker staged beside
  the first face downs Bram; a rescuer carries him home within
  the 1 500-tick window; nobody lost.
- **Stub bands:** floor 2 generates as Fungal Reaches with
  fungal-node cells present and `built == false`; floor 5 is
  Magma Roots; floor 6 recombines to Fungal Reaches.

### Defects found by these tests during development (both fixed)

- **HashSet-order impurity:** one sampling step iterated a
  `HashSet` unsorted, so floor 2 could differ between
  generation orders. Fixed by sorting every sampled set; the
  independence test now covers stub bands for this reason.
- **Bad-air depth leak:** hazard pockets were *seeded* at
  y ≥ 6 but *grew* upward. The growth predicate now enforces
  the floor's minimum y for the whole pocket.

### Full-suite + harness results

- `cargo test`: **37/37** (25 pre-existing + 10 gen_floor + 2
  generator unit tests), 0 failed.
- `scenario` binary (release): S1/S2/S3/S5 sections unchanged
  in behaviour (S1 goods 6, S3 goods 20, S5 oil 19). New GEN
  section: phase 1 goods=0, RouteBlocked=1; after opening,
  **goods=24, deliveries=13, conversions=13, delvers alive=5,
  lost=0** at tick 6 200; descent (20, 9, 3) at network
  distance 28; 52 network cells; 2 dens; 3 faces. GEN state
  hash `ba202ca7f045f5443d08…`.
- Godot headless verify prints **both** lines:
  `UNDERREACH_VERIFY_PASS goods=20 delvers=5 floor_instances=15
  tick=4000` (s3, unchanged) and `UNDERREACH_VERIFY_PASS
  scenario=gen goods=24 delvers=5 floor_instances=61 tick=4000`
  — for gen, the view layer is set to the descent's depth (9),
  so 61 is the generated floor's carved-cell count on that
  layer.
- **Not verified:** generated-floor appearance on the owner's
  PC (placeholder markers have never been rendered outside the
  headless load check); floors 2–5 balance (stub themes);
  cave-in/bad-air mechanics (cells exist, no mechanics);
  floor-to-floor traversal (descent is a marker, not a
  transition).

## S7 — the Shallows bite back (verified 2026-11-23, VM headless)

Branch `underreach-delving-colony/hazard-mechanics`. The
Shallows gate set from owner decision 9, over the pockets S6
generates: cave-ins at loose faces and bad air beside sealed
pockets, answered by timber supports and vents. Save hashes
shift again in this slice (delvers gain an air load; the save
gains `supports`/`vents` lists); behaviour numbers for the
S1–S6 scenarios are unchanged — a colony that never meets
loose rock or bad air draws no new RNG and breathes no bad
air, which the unchanged scenario sections below demonstrate.

### The mechanics

- **Bad air.** A carved cell touching a `Cell::BadAir` pocket
  is gassy unless a vent reaches it. Load +1.0/tick in a gassy
  cell; at 60 the delver is **gasping** (work halved, morale
  −20, bed-seeking — the spore-cough's shape); at 100 it
  drains hp 0.2/tick and can down, starting the rescue clock.
  Clears 0.25/tick in clean air, 1.25/tick within a vent's
  reach. A pocket carved open is spent — its gas is gone with
  the rock (a modelling decision, recorded in `sim.rs`).
- **Cave-ins.** Per unit mined at a face: 2% per loose cell
  neighbouring the face's rock or its stand, rolled on the
  sim RNG (draws happen only when loose rock neighbours an
  unsupported face). A collapse spends the first loose cell
  in scan order, fills the stand cell with stone, and deals
  55 damage to the delver working there. A survivor climbs
  out through the existing pathing; a downed delver is dug
  out — rescuers aim at the rubble's nearest carved
  neighbour and carry from there. The player re-carves the
  stand to reopen the face.
- **The answers.** `place_support` / `place_vent`: crafted
  kit at **1 goods each**, carved cells only, no stacking. A
  support protects any face whose stand it stands on or
  touches; a vent ventilates carved cells within Chebyshev
  radius 2. Both are exposed over the bridge (`support` /
  `vent` commands; the view gains `air`, `supports`,
  `vents`; `init s7` founds the demo colony).

### Tests (`sim/tests/scenario_s7.rs`, 6 tests)

- **The unprotected face bites both ways:** 6,000 ticks with
  the player script clearing each fall — `CaveIn` ≥ 1
  (actual 3), `DelverGasping` ≥ 1 (actual 2), 1 downed,
  0 lost, goods 16: the colony weathers it, at a price.
- **Timber support stops cave-ins:** `CaveIn` == 0, the
  stand never buried, the face produced (goods 14 in the
  binary's protected run, support + vent together).
- **A vent keeps the air clean:** `DelverGasping` == 0 and
  every delver's air load exactly 0 — while `CaveIn` ≥ 1:
  the vent answers air, not rock.
- **Placement rules:** solid rock refused, 1 goods apiece,
  no stacking on a cell, a broke colony refused.
- **Burial and dig-out:** vented but unsupported face, the
  miner staged at 50 hp — the fall comes early in the run,
  the stand is `Stone`, `DelverDowned` fires, and within
  the rescue window `DelverRescued` fires with 0 lost.
- **Determinism:** twin-run and save/load continuation
  hashes identical, as every slice before.

### Full-suite + harness results

- `cargo test`: **43/43** (37 pre-existing + 6 S7), 0 failed.
- `scenario` binary (release): S1/S2/S3/S5/GEN sections
  unchanged in behaviour (S1 goods 6, S3 goods 20, S5 oil
  19, GEN goods 24, nobody lost). New S7 sections:
  unprotected — goods=16, cave-ins=3, gasping=2, downed=1,
  lost=0, hash `a0fa094e684ff118d3…`; protected — goods=14,
  cave-ins=0, gasping=0, downed=0, hash
  `d709d50d524c0ab248…`.
- **Balance note (tuned once, on evidence):** `AIR_RATE`
  went 0.6 → 1.0 after the first runs. At 0.6 a miner's
  haul trips cleared more load than a mining stint gained,
  so bad air could never gasp anyone at a single face; a
  pocket's seep is concentrated, unlike ambient spores.
- **Not verified / not built:** Godot frontend surfacing
  for supports, vents, and air loads (the bridge view
  carries the data; the frontend renders none of it yet —
  the same stance as S5's sim-side build); cave-in
  triggers from carving or from passing loose walls
  (mining only in this slice); floors 2–5 scenarios;
  floor-to-floor traversal.

## S8 — floor-to-floor traversal (verified 2026-11-24, VM headless)

Branch `underreach-delving-colony/traversal`. The S6 descent
becomes a transition: per-floor stored state, `descend()` /
`ascend()` on the sim (and `descend` / `ascend` bridge
commands; the bridge view already carried `floor_index`).
Save hashes shift again in this slice (the save gains the
`floors` stored-state map and two Ledger kinds);
behaviour numbers for the S1–S7 scenarios are unchanged.

### Modelling decisions (the record was silent on these)

- **Whole-colony immediate transition.** Every delver
  travels together; there is no per-delver cross-floor
  pathing. On descent delvers gather at the target floor's
  entry camp; on ascent they arrive at the floor above's
  descent cell (they climb back up the stairs they came
  down), with their current work step reset.
- **A floor left behind is frozen.** Its packed state is
  not ticked: its lanterns do not burn fuel while the
  colony is away, and it restores exactly on return.
- **Forward camp on first arrival.** A never-visited floor
  is generated purely from `(world_seed, floor_index)` and
  founded at its entry camp mirroring `build_scenario_gen`
  (delvers at the entry camp, beds + stockpile there, the
  generated floor's registered faces, gate at the entry
  camp, a pipe-fed camp lantern, one resident critter per
  den) — except that **farming plots do not carry down**:
  a fresh floor starts with no plots. Stores, delvers, the
  Ledger, tick, RNG, and the arrival schedule are global
  and travel with the colony.

### Tests (`sim/tests/scenario_s8.rs`, 8 tests)

- **Descend lands on floor 2:** `floor.index == 2`, the
  active world equals `generate_floor(seed, 2).world`,
  `FloorInfo` equals that floor's `info()`; a forward camp
  (stockpile at the entry, beds, the generated faces, no
  plots), floor 1 stored behind, one `Descended` entry.
- **Generation purity:** `rng_state` identical before and
  after a generating descend; descending 1→2→3 yields
  worlds equal to standalone `generate_floor` for floors
  2 and 3.
- **Round-trip restoration:** after producing on floor 1
  and setting a support + vent, descend, run 1,000 ticks
  on floor 2, ascend — floor 1's world, lanterns, faces,
  supports, vents, and lit_depths are exactly as they were
  at departure (lantern fuel unburned: the floor froze).
- **Save/load across floors:** mid-run on floor 2,
  `save_json` → `load_json` reproduces `state_hash()`
  exactly, stored floor included; twin continuation for
  300 ticks stays hash-identical; the loaded copy ascends.
- **First light per floor:** after descending and opening
  floor 2, `FirstLight` entries exist beyond those
  recorded on floor 1 (lit depths are packed per floor).
- **The loop continues:** on floor 2 after opening,
  deliveries ≥ 1 (actual 5 in the binary run) and goods
  strictly increase (24 → 33 in the binary run); 0 lost.
- **Refusals:** `descend` on the hand-built S1 scenario
  (floor `None`) returns false with the state hash
  unchanged; `ascend` on floor 1 returns false.
- **Ledger append-only:** the entries present before a
  descent are a strict prefix of the ledger after it.

### Full-suite + harness results

- `cargo test`: **51/51** (43 pre-existing + 8 S8),
  0 failed.
- `scenario` binary (release): S1/S2/S3/S5/GEN/S7 sections
  unchanged in behaviour (S1 goods 6, S3 goods 20, S5 oil
  19, GEN goods 24 with nobody lost, S7 unprotected goods
  16 / cave-ins 3 / gasping 2 / downed 1, S7 protected
  goods 14 / cave-ins 0 / gasping 0 / downed 0). New S8
  section: floor 1 goods=24, deliveries=13, alive=5,
  lost=0 at 6,000 ticks; descend ok, floor=2; floor 2
  goods=33 (was 24 on arrival), 5 deliveries on that
  floor, alive=6 (a recruit arrived), lost=0, 12
  first-light entries in total across both floors at
  12,000 ticks; ascend ok, back on floor=1, floor 1 world
  intact=true, floor 1 lanterns intact=true. S8 state
  hash `7fff65ca28fd8bcec5ce1815e52a65dd9be807f23b81692a6f1942e97bea9def`.
- Bridge check (release binary, file protocol): `init
  gen` → step with `[{"cmd":"descend"}]` reports
  `floor_index` 2; a following `[{"cmd":"ascend"}]` step
  reports `floor_index` 1.
- **Not verified / not built:** Godot frontend surfacing
  for traversal (the bridge view carries `floor_index`;
  the frontend has no floor-switch UI yet); floors 2–5
  scenarios, balance, and per-floor band mechanics —
  floor 2 generates as the Fungal Reaches stub and runs
  the generic delve → haul → convert loop, but spores are
  still keyed to depth (`hazards_at`), not to the floor's
  band, and no Fungal gate set is founded with the forward
  camp.

## S9 — floors 2–5 scenarios and balance (verified 2026-11-24, VM headless)

Branch `underreach-delving-colony/band-scenarios`. The gen
founding is generalized: `build_scenario_gen_floor(world_seed,
floor_index)` founds a colony directly on any generated floor
with the exact `build_scenario_gen` pattern (entry-camp
delvers, beds + stockpile, generated faces, gate, pipe-fed
camp lantern, one resident critter per den, and the two camp
farming plots — a founded colony is a home, where S8's forward
camps omit the plots). `build_scenario_gen` is now that
function at floor 1; a test pins the two foundings
hash-identical, and the GEN section below is unchanged.

### Tests (`sim/tests/scenario_s9.rs`, 9 tests)

- **Founding identity:** `build_scenario_gen(seed)` and
  `build_scenario_gen_floor(seed, 1)` produce identical state
  hashes.
- **One loop test per band (floors 2–5):** founded on the
  demo seed `0x5EED0007`, the active world equals
  `generate_floor(seed, floor)`, founding drew no runtime RNG,
  opened with `open_current_floor`, 6,000 ticks → goods
  strictly increase, deliveries ≥ 1, 0 lost.
- **Determinism (floors 2 and 5):** save/load mid-run
  reproduces the state hash; twin continuation for 300 ticks
  stays hash-identical.
- **The Fungal spore proof** (below).
- **Floor 1 guard:** every value of the Shallows theme row is
  pinned exactly as it stood before this slice.

### Per-band scenario numbers (scenario binary, 6,000 ticks each)

| Floor / band | Goods | Deliveries | Alive | Lost | Sick | Gasping | Cave-ins | Downed | Fungal oil | Food at end* |
|---|---|---|---|---|---|---|---|---|---|---|
| 2 Fungal Reaches | 9 | 6 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 94 |
| 3 Drowned Galleries | 15 | 8 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 96 |
| 4 Crystal Dark | 9 | 6 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 92 |
| 5 Magma Roots | 6 | 4 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 94 |

\* Food read from the identical test-configuration runs (the
binary does not print it). State hashes: F2
`7693079b122fbe76c7…`, F3 `59bb11997b063ddb92…`, F4
`0e6be80d248a9d50b3…`, F5 `7096ce90a703e9abc1…`. Critters
spotted/slain in the same runs: F2 9/9, F3 10/10, F4 9/9,
F5 8/8 — the lit network did the repelling, the same honest
read as S3; no cave-in or gasping event fired on any band's
opened faces in these runs.

### The Fungal finding — spores do NOT engage on generated floors

Proven by test, not assumed. Spore exposure in `sim.rs` is
keyed to **depth**: a delver gains load only where
`hazards_at(pos.y).spores`, which is true only at
y ≥ `FUNGAL_FROM` (10). A generated floor's content lives at
y ≤ `GEN_MAX_Y` (9) — the demo floor 2's carved cells top out
at y = 9 and every face stand sits in clean air
(`hazards_at(stand.y).spores == false` for all three faces).
An unmasked delver staged at floor 2's first face stand for
2,000 ticks gains exactly 0.0 spore load; across the full
6,000-tick colony run every delver's load stays 0.0 and
`DelverSick` never fires. Fungal oil does not flow either:
the generator registers faces from the theme's primary
resource cell (ore) only, so all of floor 2's faces yield
ore, and the fungal-node clusters are embedded pockets, not
faces — oil in stores stays 0. Mask protection itself remains
proven by the S5 tests on the hand-built floor (chamber at
y = 14, above the Fungal line). **No rewire was made:**
keying exposure to the floor's band instead of depth would
change S8's floor-2 behaviour, so it is not provably inert
for the existing baselines; the finding feeds S10, where the
Drowned/Magma mechanics land and band-keying can be designed
once for all bands.

### Balance pass — no tuning

The tuning triggers (a band's colony cannot produce, starves,
or is wiped by its dens before it can work) fired for **no**
band: every band produced from its stub theme numbers, ended
the run fed (food 92–96), and lost nobody. Per the slice
rule — tune only on evidence, by the smallest change — **no
theme row was changed**: floors 2–5 keep their S6 stub
numbers, and the Shallows row is pinned by the guard test.

### The `built` decisions — no flag flips

A band flips only when (a) its scenario runs the colony loop
on its generated floor, (b) its balance numbers are recorded,
and (c) the mechanics that exist for that band today
demonstrably engage on the generated floor.

- **Fungal Reaches: stays `false`.** (a) and (b) hold; (c)
  fails on the finding above — spores never engage and oil
  never flows on the generated floor.
- **Drowned Galleries: stays `false`.** (a) and (b) hold;
  (c) fails — `flooded` is flag-only until S10, no flooding
  mechanics exist to engage.
- **Crystal Dark: stays `false`.** (a) and (b) hold; (c)
  fails — its gate items (lenses, quiet gear, harnesses,
  brittle floors, sound hunters) have never been modelled.
- **Magma Roots: stays `false`.** (a) and (b) hold; (c)
  fails — `hot` is flag-only until S10.

Consequently **no pre-existing assertion changed**: the
`built` expectations in the `gen.rs` unit test and in
`sim/tests/gen_floor.rs` already assert `false` for the stub
bands and remain correct as written.

### Full-suite + harness results

- `cargo test`: **60/60** (51 pre-existing + 9 S9), 0 failed.
- `scenario` binary (release): S1/S2/S3/S5/GEN/S7/S8 sections
  unchanged in behaviour **and** in state hash (S1 goods 6,
  S3 goods 20, S5 oil 19, GEN goods 24 / lost 0, S7
  unprotected 16/3/2/1, S7 protected 14/0/0/0, S8 floor-2
  goods 33). New S9 F2/F3/F4/F5 sections as tabulated above.
- **Not verified / not built:** flooding and heat mechanics
  (S10); band-keyed hazard exposure (the Fungal finding,
  feeds S10); Crystal Dark gate items; Godot frontend
  surfacing for floors 2–5 (the bridge view carries
  `floor_index`; no per-band rendering exists yet).
  *(S10 amendment, 2026-11-24: flooding, heat, and
  band-keyed exposure are built — see the S10 section below.
  The Fungal finding is resolved for spores; its second
  half — fungal oil never flows from generated faces —
  stands, and face registration for embedded pockets
  remains open.)*

## S10 — deeper band hazards (verified 2026-11-24, VM headless)

Branch `underreach-delving-colony/band-hazards`. The S9
finding is acted on: hazard exposure is keyed to the active
floor's band on generated floors, and the two flag-only
hazards — Drowned flooding and Magma heat — become live
mechanics with their decision-9 answers. Save hashes shift
again in this slice (delvers gain water/heat loads, a
cooling-gear flag, and threshold latches; the stores gain a
cooling-gear count; the sim and per-floor state gain pump
lists); behaviour numbers for the S1–S9 scenarios are
unchanged, as the full-suite results below show.

### The band-keying design (`hazards_here`)

One query, `Sim::hazards_here(pos)`, is the only exposure
source every hazard consults (spores, water, heat, and the
lantern-dousing check):

- **Generated floor** (`floor` is Some): the active floor's
  band flags — `theme_for_floor(index).hazards` — decide
  which hazards a cell can carry, applied in the floor's
  **deep zone**: carved cells at y ≥ `BAND_ZONE_FROM_Y` (6).
  That is the same depth line generation already uses
  (bad air pools only at y ≥ 6; the entry camp sits at
  y = 3), and it mirrors the hand-built world, where the
  camp is clean air above the Fungal line and the hazard
  lives in the deep workings. The camp stays a refuge on
  every band floor, so loads clear at camp exactly as they
  do in the hand-built S5 world; the faces, which generation
  places deep, are where the band bites. The depth table is
  not consulted on a generated floor — nothing double-applies.
- **Hand-built world** (`floor` is None): the depth-keyed
  `hazards_at(y)` table rules, exactly as before S10, at
  every depth — including its recombined flooded/hot bands
  deep down, where the new mechanics now also engage (no
  hand-built scenario reaches those depths; S5's chamber at
  y = 14 is in the spore-only band, so no baseline moves).

### The mechanics

- **Flooding (Drowned).** A delver standing in flood water
  — a flooded-band deep-zone cell no pump keeps dry — gains
  **water load** +1.0/tick (`WATER_RATE`, the air rate's
  value). At 60 (`DROWNING_AT`) they are **drowning**: work
  halved, morale −20, bed-seeking — the shared threshold
  shape (`DelverDrowning` ledgered). At 100 the load drains
  hp 0.2/tick and can down onto the rescue clock. Load
  clears 0.25/tick in dry cells, 1.25/tick within a pump's
  reach. **Lantern failure**: an unsealed lantern (tier <
  3) standing in flood water loses `DOUSE_RATE` 2.0 extra
  fuel/tick on top of its burn — a 5,000-fuel route lantern
  is doused in ~2,475 ticks — and its death is ledgered as
  `LanternDoused`, not a burnout.
- **The Drowned answers.** A **pump**: placed kit at
  **1 goods**, carved cells only, no stacking; carved cells
  within Chebyshev radius 2 (`PUMP_RADIUS`, the vent's
  radius) are dry — no load, fast clearing, lanterns there
  burn normally. The **sealed pressure lantern** is lantern
  **tier 3** (decision 8's waterproof tier): placement
  follows `place_lantern`'s existing rules, so it draws the
  tier-2+ charge of 1 fungal oil, and it burns in flood
  water at its plain tier rate. Air bells and drains were
  **not** modelled: the pump's dry reach already provides
  refuge cells and a workable face, so a second water
  answer would duplicate it, not complete it (modelling
  decision, recorded here and in the handoff).
- **Heat (Magma).** A delver in a hot band's deep zone gains
  **heat load** +1.0/tick (`HEAT_RATE`); at 60
  (`OVERHEATING_AT`) the shared threshold shape applies
  (`DelverOverheating` ledgered); at 100, hp drains
  0.2/tick. Clears 0.25/tick in cool areas. The answer is
  **cooling gear**: worn crafted kit at **2 goods** (the
  mask's price and pattern — crafted into stores,
  auto-equipped at camp, permanent), which prevents the
  gain entirely. No placed heat answer was modelled:
  decision 9's list leads with cooling gear, and worn kit
  travels with the delver through the whole hot zone
  (modelling decision).
- **One correction, on the record:** `SPORE_RATE_MASKED`
  went 0.05 → 0.0. S5's record says a mask "protects its
  wearer entirely", and S10's mask proof asserts a load of
  exactly 0 at a deep face; the 0.05 leak contradicted both.
  No S5 assertion depended on the leak (its mask test
  asserts no sickness, which holds either way), and the S5
  scenario numbers below are unchanged.

No rate was re-tuned on evidence in this slice: the rates
are the established pattern values (load 1.0 as `AIR_RATE`,
threshold 60 as `SICK_AT`/`GASPING_AT`, drain 0.2, clear
0.25 / assisted 1.25 as air's), and the first full runs
showed the intended contrasts (below).

### Tests (`sim/tests/scenario_s10.rs`, 10 tests)

- **Band-keying:** a delver staged at floor 2's deep face
  (stand y = 7) maxes spore load and the spore-cough fires
  for them; the camp shallows are clean; a masked delver at
  the same stand keeps a load of exactly 0.0 and never
  sickens. On generated floor 1 nothing engages: all three
  loads stay 0 at the deepest face stand.
- **Flooding loads and downs:** staged at floor 3's deep
  face, water maxes, `DelverDrowning` fires; a hurt delver
  kept working the face (staged Mining, the S7 hurt-miner
  pattern) is downed onto the rescue clock. (A delver who
  rests between trips heals faster than the 0.2 drain —
  the flood's honest pace; the downing proof therefore
  stages continuous work.)
- **A pump keeps its reach dry:** the pumped face stand is
  not `flooded_at`; a delver pinned there for 2,000 ticks
  keeps water exactly 0.0, never drowns, and the tier-1
  lantern on the stand burns at its plain rate throughout
  (fuel > 4,900 of 5,000 after 2,000 ticks).
- **Pressure lantern vs tier-1:** both placed in flood
  water with 100 fuel — tier-3 placement first refuses with
  no oil, then places for exactly 1 oil; after 200 ticks
  the tier-1 is at 0 with `LanternDoused` ledgered, the
  pressure lantern holds > 90 fuel and its cell is lit.
- **Heat:** staged at floor 5's first face (stand y = 6),
  heat maxes and `DelverOverheating` fires; with cooling
  gear crafted and auto-equipped at camp, the same staging
  keeps heat exactly 0.0.
- **Placement/cost rules:** solid rock refuses a pump;
  a pump costs 1 goods with no stacking; a broke colony
  places and crafts nothing; cooling gear costs 2 goods.
- **Determinism:** twin-run + save/load continuation
  hash-identical on a flooded floor (3) and a hot floor (5).
- Staged proofs pin the delver at the stand with a lantern
  placed there first (lit staging) — an unlit staging
  conflates the flood with the dark's own clock, which an
  early version of these tests demonstrated the hard way.

### Full-suite + harness results

- `cargo test`: **70/70** (60 pre-existing + 10 S10),
  0 failed.
- `scenario` binary (release): S1/S2/S3/S5/GEN/S7/S8
  sections unchanged in behaviour (S1 goods 6, S3 goods
  20, S5 oil 19 / sick 0, GEN goods 24, S7 unprotected
  16/3/2/1, S7 protected 14/0/0/0, S8 floor-2 goods 33,
  nobody lost anywhere). S9 sections: every band's goods
  and deliveries reproduce S9 exactly (F2 9, F3 15, F4 9,
  F5 6) — with the now-live events visible in the same
  runs: **F3 drowning=3, doused=3** and **F5
  overheating=2**, downed=0 and lost=0 on both. **F2's
  sick stays 0, for a new reason**: the demo-seed colony
  spends the whole 6,000-tick budget working its first
  face (ore_left 0 at run end), whose stand at y = 5 sits
  above the deep zone; floor 2's engagement is proven by
  the staged tests at its deeper faces, not by this run.
  All state hashes differ from S9's (new save fields);
  determinism is proven by the twin-run tests as before.
- New S10 sections (6,000 ticks each, demo seed):

  | Run | Goods | Deliveries | Alive | Lost | Band events |
  |---|---|---|---|---|---|
  | Drowned unprotected (tier-1 opening) | 15 | 8 | 5 | 0 | drowning 3, doused 3, downed 0 |
  | Drowned protected (3 pumps + pressure opening) | 15 | 8 | 5 | 0 | drowning 0, doused 0, downed 0 |
  | Magma unprotected | 6 | 4 | 5 | 0 | overheating 2, downed 0 |
  | Magma protected (6 cooling gear crafted) | 6 | 4 | 5 | 0 | overheating 0, downed 0 |

  The protected runs' scripts grant the supplies a prepared
  colony would carry in (3 goods for the pumps, 8 oil for
  the pressure lanterns — placement spent 3 goods and one
  oil charge per lantern actually placed; 12 goods for the
  gear) and the net goods land exactly on the unprotected
  runs' numbers: the answers cost their kit price and
  nothing in production. Drowned protected hash
  `e0b6a85e87110238…`; magma protected hash
  `9066728cc322593e…`. The unprotected runs are the S9
  F3/F5 runs themselves (identical hashes to the S9
  sections above).
- Bridge check (release binary, file protocol): `init gen`
  → a step carrying `pump` and `craft_cooling` commands
  applies cleanly (both refused at 0 goods, as designed);
  the view carries `pumps`, `flooded` (0 cells on floor 1),
  per-delver `water`/`heat`/`cooled`, and the stores'
  `cooling_gear`.

### Baseline movements — each one explained

No pre-existing scenario number or test assertion about
behaviour moved. The movements are exactly these:

- **`gen.rs` unit test + `gen_floor.rs` stub-band test**:
  the `built` expectations for floors 2, 3, and 5 flip to
  `true` (floor 4 stays `false`) — this slice's intended
  flag flips; see the `built` decisions below.
- **`scenario_s9.rs`'s Fungal proof** is rewritten to pin
  the new truth (its S9 form proved spores do *not*
  engage): it still asserts the depth table keys no
  generated stand as spore-bearing, that the shallow first
  face stays clean under staging, and that no fungal oil
  flows from generated faces — and now also that a deep
  face's stand is band-keyed spore air where the cough
  fires. The property it exists to prove — floor 2's
  hazard-engagement status is pinned by test, whichever
  way the mechanics stand — is kept; the direction is
  S10's intended change.
- **`scenario_s3.rs`**: one mechanical line — its `Stores`
  literal gains the new `cooling_gear: 0` field (as do all
  of `scenario.rs`'s). No assertion touched.
- **State hashes** in every scenario section differ from
  their S9 values (new save fields, listed above). S9's
  own precedent applies: determinism is proven by the
  twin-run tests, not by hash stability across slices.

### The `built` decisions — three flags flip

Under S9's rule — (a) the band's scenario runs the colony
loop on its generated floor, (b) its balance numbers are
recorded, (c) the mechanics that exist for that band
demonstrably engage on the generated floor:

- **Fungal Reaches: flips to `true`.** (a) and (b) held
  since S9; (c) now holds — band-keyed spores engage in
  floor 2's deep zone (staged proofs: load maxes, the
  cough fires, a mask holds the load at exactly 0). The
  oil half of the S9 finding is unchanged and does not
  block the flip: it was never a hazard mechanic, and face
  registration for embedded pockets remains a recorded
  follow-on.
- **Drowned Galleries: flips to `true`.** (c) holds in the
  ordinary colony run itself — drowning and dousing events
  fire unprotected and are wholly absent under pumps +
  pressure lanterns, at equal production.
- **Crystal Dark: stays `false`.** Its gate items (lenses,
  quiet gear, harnesses, brittle floors, sound hunters)
  have still never been modelled; nothing about this
  slice changes that.
- **Magma Roots: flips to `true`.** (c) holds in the
  ordinary run — overheating fires unprotected and is
  wholly absent under cooling gear, at equal production.

### Not verified / not built

- Godot frontend surfacing for pumps, flooded cells, water
  / heat loads, and cooling gear (the bridge view carries
  all of it; the frontend renders none of it yet — the
  same stance as S5/S7's sim-side builds).
- Face registration for embedded pockets (fungal-oil faces
  on generated floors) — the S6/S9 follow-on, still open.
- Crystal Dark gate items; flooding/heat *combinations*
  on recombined floors ≥ 6 beyond what the band cycle and
  the depth table already compose (each generated floor
  ≥ 6 takes its cycled band's flags under `hazards_here`;
  no scenario run was made there in this slice).

## S11 — Godot frontend surfacing (verified 2026-11-24, VM headless)

Branch `underreach-delving-colony/frontend-surfacing`. The
pieces S7/S8/S10 built sim-side only — supports, vents, pumps,
flooded cells, per-delver air/water/heat loads, cooling gear,
and floor traversal — are now surfaced in the Godot frontend.
The frontend still holds **no sim rules**: it renders the
bridge view and sends the existing bridge commands. The sim
library is untouched; the only `sim/` change is in the bridge
binary's view JSON, purely additive (below).

### What the frontend now does

- **Placed kit renders** (`supports` / `vents` / `pumps` from
  the view) as placeholder markers in the dressing idiom, one
  per placed piece on the viewed layer, with a distinct colour
  per kind (timber-brown support, pale-cyan vent, blue-steel
  pump — recorded in `frontend/README.md`). No catalog GLBs
  exist for these; placeholders are the owner-approved stance.
  The placed pump is distinct from the "Pump" *dressing*
  anchor, which remains unbuilt scenery data.
- **Flooded cells render** (`flooded` from the view) as a
  thin blue-tinted overlay instance per flooded cell on the
  viewed layer (a second MultiMesh, the floors' idiom).
- **Delver loads surface**: the right-panel status line shows
  air / water / heat verbatim from the view (spore when > 0),
  plus `MASKED` / `COOLED` worn-kit state; suffering is
  flagged in text — `[SICK]`, `[GASPING]`, `[DROWNING]`,
  `[OVERHEATING]` — in the panel line and appended to the
  3D name label (which also tints orange while suffering).
- **Floor indicator + traversal**: the HUD shows
  `Floor <index> · <band name>` from the view (`Floor — ·
  hand-built` for the hand-built scenarios), and the player
  can `descend` / `ascend` via Colony buttons or PgDn / PgUp.
  New tools **Support** / **Vent** / **Pump** place kit by
  clicking a cell (the carve/lantern/plant pattern), and a
  **Craft cooling gear (2 goods)** button sends
  `craft_cooling`. The scenario row gains **S7**.

### The one bridge change — additive only, justified

The view already carried every S11 field except two things
the HUD/flags need: the active floor's **band name** and each
delver's **suffering state**. Deriving either in the frontend
would duplicate sim logic (the band table; the load
thresholds) in the presentation layer, against rule 5's
spirit. The bridge view therefore gains, purely additively:
`band` (the sim's own `band_for_floor` for the active floor,
null on hand-built worlds) and per-delver `sick` / `gasping`
/ `drowning` / `overheating` booleans (the sim's own
`Delver` predicates). No sim state, no save field, no hash
input, no behaviour change — proven by the baselines below:
`cargo test` 70/70 and every scenario section's numbers
(including the S10 protected-run hashes `e0b6a85e87110238…`
and `9066728cc322593e…`) reproduce exactly.

### Headless verification — the extended `--underreach-verify`

The verify keeps its two existing parts byte-identical and
adds a third (S11) part. Exact output (VM, headless, exit 0,
zero script errors):

```
UNDERREACH_VERIFY_PASS goods=20 delvers=5 floor_instances=15 tick=4000
UNDERREACH_VERIFY_PASS scenario=gen goods=24 delvers=5 floor_instances=61 tick=4000
UNDERREACH_VERIFY_PASS scenario=s11 supports=1 vents=1 pumps=1 cooling_gear=1 floor_index=3 flooded=96 flooded_layer=35 tick=0
```

What the S11 part proves, each check failing loudly
(`UNDERREACH_VERIFY_FAIL scenario=s11 …`, exit 1) on any
mismatch — no silent skips:

- **Kit placement + sync (Phase A).** On a fresh `init s7`
  colony (4 goods — its script founds no kit), the verify
  drives the bridge commands `support` at (14, 8, 4), `vent`
  at (14, 8, 4), and `pump` at (13, 8, 4) — the face stand
  and its tunnel neighbour. The frontend's synced counts
  (`kit_synced`, taken from the view on every `apply_view`)
  must equal the view's array sizes exactly (1 each), and
  the rendered marker count on layer 8 (`count_rendered_kit`,
  counting `kit_kind`-tagged props) must be 1 per kind.
- **Load display (Phase A).** For every delver in the view,
  the panel line the frontend actually built
  (`delver_load_texts`) must contain `air <v>`, `water <v>`,
  and `heat <v>` formatted from that delver's view values.
  The suffering/worn-kit flags are additionally proven on a
  synthetic delver entry (sick + gasping + drowning + masked
  + cooled, not overheating), so the flag logic is exercised
  regardless of this run's loads.
- **Cooling gear (Phase B).** A fresh `init s7` (the kit in
  Phase A leaves only 1 good, short of the 2-good craft)
  takes `craft_cooling` through the bridge; the view's
  `cooling_gear` must be 1 and the HUD stores line must read
  `Cooling 1`.
- **Traversal + flooded (Phase C).** On `init gen`, the HUD
  floor indicator must read Floor 1 · Shallows; after a
  `descend` command it must read Floor 2 · Fungal Reaches
  (the spec's 1 → 2 follow, asserted on both the view's
  `floor_index` and the label text); after a second
  `descend`, Floor 3 · Drowned Galleries with
  `flooded=96` in the view, the frontend's `flooded_synced`
  equal to it, and the overlay's instance count on layer 9
  equal to the view's layer-9 flooded count (35) — computed
  independently in the verify from the view, not from the
  renderer's own bookkeeping. Kit sync is re-asserted on
  floor 3 (0 each, matching the view).

### Full-suite + harness results

- `cargo test`: **70/70**, 0 failed — unchanged.
- `scenario` binary (release): every S1–S10 section
  reproduces its S10 numbers exactly (S1 goods 6, S3 goods
  20, S5 oil 19 / sick 0, GEN goods 24, S7 unprotected
  16/3/2/1, S7 protected 14/0/0/0, S8 floor-2 goods 33, S9
  F2 9 / F3 15 with drowning 3 + doused 3 / F4 9 / F5 6
  with overheating 2, S10 protected hashes as above;
  nobody lost anywhere).
- Godot headless verify: the three PASS lines above.
  (Environment note: a fresh worktree needs one
  `godot --headless --editor --import` pass before the
  verify, or the GLB import cache is missing and loads
  fail — the same wrinkle the 2026-11-12 on-PC pass hit.
  The `.godot` cache is gitignored; no project file
  changed by it.)

### Not verified

- **Rendered appearance of all S11 surfacing: unverified,
  awaits the owner's PC.** Headless verify proves load and
  logic only — this VM produces no viewport image. The kit
  markers' colours/sizes, the flooded overlay's look, the
  name-label flag text, and the HUD layout have never been
  seen rendered. No performance claims, as ever.

## S12 — children & generations (verified 2026-11-24, VM headless)

Branch `underreach-delving-colony/generations`. Owner
decision 5's second growth source — children growing up —
behind the opt-in `generations_enabled` flag, in the
`critters_enabled` precedent (S3). **Unlike every prior
slice, no pre-existing state hash moves in this one** (see
the inertness proof below): no existing save field changes
meaning, and the new fields default inertly.

### Modelling decisions (the record was silent on all of these)

- **`TICKS_PER_YEAR` = 2400** — one year is one
  surface-recruitment cycle (`RECRUIT_INTERVAL`), the
  colony's existing calendar beat. Founders and recruits are
  founded at **25 years**; adulthood is **18**.
- **Age is inert recorded data while the system is off.**
  `Delver::age_ticks` advances only in generations colonies,
  and both new save fields omit themselves at their inert
  defaults (`age_ticks` at the founding age,
  `generations_enabled` at false — an omitted field loads
  back as exactly its serde default, so the omission is
  roundtrip-safe). That is what makes the disabled sim
  bit-identical, hash included.
- **Births** are checked on the recruitment cadence
  (`BIRTH_INTERVAL` = `RECRUIT_INTERVAL`, on tick multiples)
  and are **deterministic with no probability roll**: a birth
  fires at a check when at least two adults are alive, food
  in stores is at or above **`BIRTH_MIN_FOOD`, which reuses
  `RECRUIT_MIN_FOOD` (4)** — a colony viable to a recruit can
  feed a child — and total population is below
  `MAX_DELVER_POPULATION` (6).
- **Parents are the two longest-present adults** — the two
  lowest delver ids among living adults (ids are issued in
  arrival order, never reused). The `ChildBorn` Ledger entry
  names the child and both parents.
- **The child's name** is drawn from `RECRUIT_NAMES` not
  currently in use, on the sim RNG, exactly as recruitment
  draws — the only RNG draw the system makes, and only when
  a birth fires in an enabled sim. **Fallback if the pool is
  exhausted: no birth at that check** (the recruitment
  pattern); unreachable in practice while the cap (6) sits
  below the pool size (12), but the rule is total.
- **Childhood scoping:** a child lives the camp life of an
  Unassigned delver (eat, rest, morale) but the job decision
  never dispatches them to work, `set_job` refuses them (it
  now returns `bool`; the refusal's bridge signal is the
  delver simply staying `Unassigned`), they gain no job XP,
  and they are never picked as a rescuer. No school,
  childcare, or carrying system is modelled — children at
  camp are in the lit safe zone by construction.
- **Coming of age** is the age-crossing itself: age is
  monotonic, so the 18-year crossing fires exactly one
  `CameOfAge` entry per delver, with no latch field.

### Choreography disclosure (the S7 staged-proof tradition)

The scenario binary's S12 colony is **hand-built** (the S2
Shallows layout — its production is the proven baseline, and
the slice's claim is the generational arc, not a new floor)
and founded with **Joss, a child of 17**, so the coming of
age lands one year into the run instead of eighteen. The
colony takes no surface recruits, so the growth on show is
births alone, and its face is very rich (2,000 ore: a veteran
miner's rate grows with level, and Bram alone strips a
200-ore face before Joss turns 18 — found in development).
The **from-birth** arc is proven in the tests instead of the
binary: a real newborn is born at a real check, and its last
childhood year is run tick by tick to the crossing (staging
its age to 17 first, the same founding choreography — a
literal from-birth-to-adult run is 43,200 ticks of a child
idling at camp and proves nothing the staged year does not).

### Tests (`sim/tests/scenario_s12.rs`, 10 tests)

- **Birth fires, named:** after the tick-2400 check,
  exactly 1 `ChildBorn`; its detail names the child and both
  parents (Bram and Sella, the two longest-present adults);
  the newborn is age < 1, `Unassigned`, XP-free, at the gate.
- **Three negative proofs**, each removing one condition:
  one adult only (food ample, two checks pass) → no birth;
  food below the minimum (plots cleared, stores empty;
  adults and headroom hold) → no birth; population at the
  cap of 6 (food ample) → no birth.
- **Childhood:** `set_job` on the 17-year-old returns false
  and leaves him `Unassigned` (an adult control's assignment
  returns true); after 2,000 ticks his mining/hauling/
  farming XP are all exactly 0 while the adult control's
  mining XP is > 0.
- **Coming of age:** over 6,000 ticks exactly 1 `CameOfAge`
  (naming Joss); assignment then accepts him. A separate
  test assigns the grown Joss Miner and runs 3,000 ticks:
  his mining XP is > 0 (388 in the binary run's longer arc).
- **From-birth childhood:** a newborn (age < 1 year at
  proof time) staged to 17, refused a Farmer assignment,
  then run one full year tick by tick to its own crossing —
  the colony's second `CameOfAge`.
- **Determinism:** twin runs of the S12 colony are
  hash-identical at 3,500 ticks (past a birth and the
  coming of age); save/load there reproduces the hash
  (ages and the enabled flag included) and a 1,000-tick
  continuation stays identical.
- **Disabled-system inertness (the hash tripwire):** the
  S3 builder, flag off, run 6,000 ticks with `light_the_way`
  — every delver's age stays at the founding 25, no
  `ChildBorn`/`CameOfAge` entries, and the state hash is
  exactly the pre-S12 value pinned in the test,
  `4dc99472c56104f7af…`, captured from the scenario binary
  at the S11 tip before any S12 change.

### Full-suite + harness results

- `cargo test`: **80/80** (70 pre-existing + 10 S12),
  0 failed.
- `scenario` binary (release): the full output was diffed
  against the pre-S12 run — **every S1–S11 section is
  byte-identical, numbers and state hashes alike**; the
  only addition is the new S12 section: 7,000 ticks,
  delvers alive=6, **goods=964, births=2, comings-of-age=1,
  grown child assigned miner=true, grown child mining
  xp=388**, children at camp=2, lost=0. Joss ends at age 19
  a working miner (mining 388 / hauling 436); the two
  colony-born children (Fenn, age 1; Tomas, age 0) sit at
  camp XP-free. S12 state hash
  `8d4d431f2e7d8cf5b359d7bbf0e8c21c3f6630d7ca09b893785c6897f3c54dfa`.
- Bridge check (release binary, file protocol): `init s12`
  view carries Joss at `age_years` 17 / `is_child` true and
  the founders at 25 / false; `init s3` carries the founders
  at 25 / false. The fields are purely additive (the S11
  pattern); no frontend work in this slice.

### Not verified / not built

- Godot frontend surfacing for age/child state (the bridge
  view carries both fields; the S11 frontend ignores them,
  as designed for this slice).
- Children in any system beyond camp life: no school,
  childcare, carrying, or child-specific needs are modelled
  (recorded scoping, above). Colony failure & succession —
  the Ledger-inheritance half of decision 5's world — is
  still not built.

## S13 — co-op foundations (verified 2026-11-24, VM headless)

Branch `underreach-delving-colony/coop-foundations`. The
lockstep foundation for the design's 1–4 co-op, built only
where headless verification can reach: a typed command layer,
an attributed session log with a canonical merge, and replay.
**No networking code exists** — no sockets, no transport, no
Godot multiplayer. The full assessment of what co-op still
needs, and the owner design questions it raises, is in
`docs/COOP_ASSESSMENT.md`. The session layer is additive
library code (`sim/src/session.rs`); the bridge is unmodified
and no sim behaviour changed — proven by the baselines below,
which for the first time since S12 include state hashes
reproducing exactly.

### The layer

- **`Command`** mirrors the bridge's player-action vocabulary
  one-for-one (carve, lantern with tier + fuel, job, plant,
  craft_mask, support, vent, pump, craft_cooling, descend,
  ascend), and `apply` dispatches to the same `Sim` methods
  the bridge handler calls with the same arguments (the
  bridge's lantern fuel is fixed at 5,000; its tier defaults
  to 1). The bridge's choreography scripts (`light_the_way`,
  `light_the_deep`, `open_floor1`) are **excluded**: they are
  multi-step founding scripts, not single sim operations, and
  stay bridge/scenario side. Two outcome conventions where the
  bridge discards the result: `carve` reports whether a cell
  was actually carved, and `plant` reports whether a new plot
  now stands (both are what a session log needs to record
  `applied` honestly).
- **`SessionLog`**: the founding save (the founding sim's
  canonical save JSON) + `end_tick` + entries
  `{tick, player, seq, command, applied}`. Players are 1–4;
  each player's `seq` starts at 0 and increments by 1.
- **`merge_streams`** sorts all entries by `(tick, player,
  seq)` — a total order independent of stream arrival order.
  A duplicate `(player, seq)` or a `seq` gap is a `MergeError`,
  surfaced, never repaired.
- **`Session` / `replay`**: a session advances to each entry's
  tick, applies, and records `applied` (a sim-refused command
  is recorded `applied: false`, not an error; a bad player,
  out-of-order `seq`, or past tick *is* an error and records
  nothing). `replay` rebuilds from the log alone, runs to
  `end_tick`, and rejects a log whose recorded `applied` flags
  disagree with the replayed outcomes (`AppliedMismatch` —
  a desync, named). `Session::resume` continues a session on
  a sim loaded from a mid-session save, keeping the original
  founding save in the log so replay is unaffected.

### Tests (`sim/tests/scenario_s13.rs`, 7 tests)

- **Two players, one colony:** on the gen Floor-1 founding,
  P1's lantern commands (the `open_floor1` route and spacing,
  issued as commands) and P2's plant (tick 0) + support + vent
  on the first face's stand (tick 1,000, once production holds
  goods — the gen colony reaches 2+ goods by ~tick 115) all
  apply with correct attribution and per-player `seq`; at
  6,200 ticks goods = 22 (> 0), nobody lost.
- **Replay:** `replay(log)` reproduces the live session's
  final state hash exactly, at the same tick count.
- **Arrival-order independence:** the same streams merged in
  reversed arrival order produce an identical merged sequence,
  byte-identical session logs (`to_json` equal), and identical
  final hashes.
- **Mid-session save/load:** at tick 3,000 the live sim is
  saved, loaded (hash reproduced), and the session resumed on
  the loaded copy; its final hash *and* its log JSON equal the
  uninterrupted session's.
- **Rejected commands:** a support on solid rock is recorded
  `applied: false` with the state hash unchanged across the
  entry; a command from player 5 is refused at the API
  (`InvalidPlayer`, nothing recorded); a past-tick entry is
  refused (`TickInPast`).
- **Merge validation:** duplicate `(player, seq)` →
  `DuplicateSeq`; a gap (0, 2) → `SeqGap`; player 5 →
  `InvalidPlayer`.
- **Log roundtrip:** `SessionLog` → JSON → parsed is equal and
  re-serializes byte-identically; replaying the parsed log
  reproduces the original session hash.

### Full-suite + harness results

- `cargo test`: **87/87** (80 pre-existing + 7 S13),
  0 failed.
- `scenario` binary (release): the output was diffed against
  the pre-S13 run — **every S1–S12 section is byte-identical,
  numbers and state hashes alike** (S1 `e3599701…`, S3
  `4dc99472…`, GEN goods 24, S12 goods 964 / hash
  `8d4d431f…`, all as recorded in their own sections). The
  only addition is the new S13 section: 6,200 ticks, **P1
  applied commands=10, P2 applied commands=3, goods=22,
  delvers alive=5, lost=0, replay_matches=true** (computed by
  actually replaying the session log inside the section),
  S13 state hash
  `11e30e9ddb3f6aa9b46e2fdd32df9a13ecf66f9d8c4dbfff4b4c6c332f2c787d`.
  Goods are GEN's 24 minus the 2 P2 spent on the support +
  vent — the answers cost their kit price, as in S10.

### Not verified / not built

- Everything in `docs/COOP_ASSESSMENT.md` section (b):
  network transport and host/join, session discovery,
  lockstep pacing under real latency, Godot multiplayer,
  desync *recovery* over a live connection (detection exists:
  hash comparison + replay's applied-flag check), and play
  with 2–4 real clients on real machines. None of it is
  headless-verifiable, so none of it was built.
- No permission/role enforcement: attribution is recorded,
  but whether every player may carve and plant first light
  is an open owner question (assessment section (c)), not
  something this layer decides.

## Planned (later slices)

- Owner-PC visual pass of the frontend; performance measurement
  before any frame budget claim.
- The dedicated gloam-lurker asset once it is built (not yet in the
  builder catalog); the ember-dragon stands in until then.
- S6 follow-ons: face registration when a pocket is carved
  open, floors 2–5 scenarios. (Cave-in/bad-air mechanics from
  this list were built in S7, above; floor-to-floor
  traversal was built in S8, above.)

## Gloam rat frontend swap (verified 2026-11-13, VM headless)

- The dedicated gloam-rat asset (builder catalog sha256
  `aec00e60646e…`, branch `game-asset-builder/underreach-assets`
  @ `a5a93d5`) is copied byte-for-byte to
  `frontend/assets/gloam-rat.glb` (hash matches the catalog).
  Critter rendering in `main.gd` is now kind-aware: GloamRat
  critters instantiate `RAT_SCENE` at target height 0.5;
  DeepLurker keeps `CRITTER_SCENE` at 1.05. No sim change (the
  bridge view already carried each critter's `kind`).
- Leg-separation gate passed in the builder before cataloguing
  (posed renders of rest and the idle/walk/run/bite apexes —
  legs separate with daylight in every shipped pose).
- Godot load test: the rat scene instantiates headless with all
  four clips (bite / idle / run / walk). Rig facing verified
  against the gloam-lurker's armature convention (head −Y) in
  Blender, so the frontend's movement-facing behaves the same.
- `godot --headless -- --underreach-verify` after the swap
  prints the identical pass line: `UNDERREACH_VERIFY_PASS
  goods=20 delvers=5 floor_instances=15 tick=4000`.
- Sim untouched: `cargo test` 25/25 and the `scenario` binary
  run repeated after the swap, clean to tick 6000.
- **On-PC pass (2026-11-13, staging
  `D:\bridge-work\underreach-visual\` updated with the new
  frontend; staged rat GLB hash = catalog sha):** Windows
  headless import + verify prints the identical
  `UNDERREACH_VERIFY_PASS goods=20 delvers=5 floor_instances=15
  tick=4000`. The game then ran windowed and live on the
  owner's PC (RTX 3060): the colony renders correctly (entry
  camp, cots, stockpile chest, lantern light, delvers, HUD,
  ledger), ticking in real time with the colony growing from
  3 to 5 delvers; critters PROVEN to spawn in this build — the
  ledger recorded "[2118] a deep lurker burned away in the
  light" during the session.
- **Not verified:** a critter sighted in frame, name-label
  legibility at gameplay zoom, and layer switching on PC.
  Critters render only on their current layer, labels are too
  small to judge at the default camera distance, and both
  checks need HUD interaction: bridge `/v1/input` clicks do
  not reach Godot's HUD buttons on this 4K / 250%-scaled
  desktop (logical, physical, and grid click attempts all
  failed to toggle Pause; root cause unresolved — likely a
  DPI-virtualization mismatch between the session helper's
  SendInput space and Godot's DWM-virtualized window), and
  camera zoom is mouse-wheel-only (the input API has no wheel
  action). The live view JSON (`user://out.json`) was read
  throughout the session and matched the HUD.
