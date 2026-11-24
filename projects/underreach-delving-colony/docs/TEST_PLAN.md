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

## Planned (later slices)

- Owner-PC visual pass of the frontend; performance measurement
  before any frame budget claim.
- The dedicated gloam-lurker asset once it is built (not yet in the
  builder catalog); the ember-dragon stands in until then.
- S6 follow-ons: face registration when a pocket is carved
  open, floors 2–5 scenarios. (Cave-in/bad-air mechanics from
  this list were built in S7, above; floor-to-floor
  traversal was built in S8, above.)
