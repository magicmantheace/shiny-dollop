# MUSE_HANDOFF — Underreach: Delving Colony

## What this is

A survival/colony game set in the Underreach. Commissioned as a filed
"someday" concept on 2026-11-09; design decisions completed 2026-11-10;
**development started 2026-11-10 at the owner's direction.** This
document is the design record and the spec. Decisions below are the
owner's unless marked as adopted proposals; do not silently redesign.

This project is **not** `projects/crawl/` (The Underreach, parked by the
owner 2026-11-06). No shared code, no shared design.

## The concept

ASKA's self-sustaining NPC village fused with RuneScape: Dragonwilds'
skills/XP spine — but where both games spread outward, this one goes
**down**. The player leads a colony of delvers perched at the top of a
bottomless underground world. Scope: **1–4 co-op**, not an MMO.

**The player is the frontier.** Delvers only work inside the lantern
network, because the dark is genuinely lethal. The player is the only
one who goes beyond it: every metre of usable tunnel exists because the
player walked into blackness, dealt with what was there, and planted
light. The loop is **delve → haul → convert**: extract at the face,
haul it up through the lit network, convert it into what the colony
needs to go deeper.

## Owner decisions (2026-11-09 / 2026-11-10)

1. **Rescue, not instant loss.** Delvers caught by the dark — lantern
   dead, expedition overdue — are **rescuable on a real-time lantern
   clock**: you get a depth and a direction (a line-bell), not a map
   marker; how long they have is the lantern your smith made and the
   fuel in it. **Permadeath only when a rescue fails.**
2. **Depth never ends.** No bottom, no ending. What replaces an ending
   is a **record**: the colony's **Deep Ledger** — every depth first
   lit, every rescue, every loss, by name. Forward camps abandoned on
   the way down persist; a hundred hours later you push past your own
   ruins.
3. **Building: hybrid voxel-carve** (owner-approved 2026-11-10).
   Terrain is voxel at a smaller, bevelled/smoothed scale — digging,
   walls, floors, stairs, plugs, dams, emergency rescue shafts are
   carved. Colonist-facing objects (beds, forges, lanterns, pumps,
   rails, workshops) are crafted kit pieces snapped to the grid; nobody
   builds a forge out of forty cubes. **The lantern network is the NPC
   navigation graph**: delvers path along lit routes rather than
   free-solving a player-sculpted cave.
4. **Threats: a mix, leaning combat-led** (2026-11-10) — creatures and
   hazards, with combat the senior partner.
5. **Delvers are full-ASKA people** (2026-11-10): names, needs, moods,
   skill growth. Colony growth comes from **surface recruitment and
   children growing up** (2026-11-10).
6. **Player death** (2026-11-10): default — you **wake rescued at the
   last camp with no gear**; a **hardcore mode** option exists.
7. **Colony failure** (2026-11-10): a colony **can be lost**. A
   successor colony **inherits the Deep Ledger** and can eventually dig
   down into its predecessor's ruins.
8. **Lantern fuel & tech tree** (Nyx proposal, adopted as proposed
   2026-11-10): one rule — *each depth band produces the fuel or
   housing that makes the next band survivable*; the tech tree is
   stations + villager skills + depth materials, not research points.
   Progression: torches/charcoal (cheap, short, smoky — ventilation
   matters) → tallow/oil lanterns (the standard; chandlery/rendering
   jobs) → fungal oil/resin (brighter, cleaner, spore-repellent when
   refined; unrefined fuel causes incidents; dangerous to harvest) →
   sealed pressure lanterns (waterproof; Drowned Galleries) →
   crystal-heart lanterns (focused light for the Crystal Dark; slow
   burn, crystals crack, maintenance matters) → thermal lamps (Magma
   Roots; near-permanent near vents/heat pipes). Lantern stats:
   **radius, burn time, steadiness, tags** (clean, waterproof,
   spore-repellent, gas-detecting flame, creature-dazzling).
   Steadiness affects delver morale and accident rates. Infrastructure
   grows: hand-placed lanterns → piped light-spine on main routes →
   crystal/thermal relays. NPCs maintain lit routes; only the player
   plants first light past the frontier.
9. **Depth-band gates** (Nyx proposal, adopted as proposed 2026-11-10):
   **soft gates with hard physical edges** — you may enter early, but
   missing the answer turns progress into emergencies; some edges are
   simply hard (no air solution → no flooded section; no heat
   protection → no Magma Roots).
   - **Shallows** — cave-ins, bad air, starter creatures. Gate: timber
     supports, ventilation, oil lanterns. Jobs: timbering, support
     carpentry, charcoal.
   - **Fungal Reaches** — spores, illness, ambush in the glow. Gate:
     masks/filters, refined fungal oil, sealed food stores,
     herbalist/antidotes. Jobs: controlled fungus farming, herbalism,
     tailoring.
   - **Drowned Galleries** — flooding, drowning, lantern failure.
     Gate: pumps, drains, air bells/pipes, pressure lanterns. Jobs:
     pump crews, pipefitting.
   - **Crystal Dark** — thicker darkness, sound/vibration hunters,
     brittle floors. Gate: crystal lenses, quiet gear, marked routes,
     harnesses. Jobs: crystal cutting, lens grinding, cartography.
   - **Magma Roots** — heat, toxic gas, lava, rock bursts. Gate:
     cooling gear, basalt/insulated tools, gas detection, heat-pipe
     lighting, emergency plugs. Jobs: heat engineering, steam/water.
   - **Below Magma**, bands **recombine** in mutated combinations
     (flooded Crystal Dark, fungal Magma, …) — endless depth is gate
     combinations, not a longer linear list.
10. **Known cost driver (flagged at filing): villager AI.** Mitigated
    by decision 3 (pathing on the lit network, not free-solving).

## Owner decisions (2026-11-12) — procedural floor generation

11. **Themed floors from a unified world seed.** Each floor is
    randomly generated from its band **theme** and the colony's
    **unified world seed**, starting with a designed Floor 1;
    placeholder assets are acceptable for now. (Implementation:
    a floor's layout is a pure function of `(world_seed,
    floor_index)` — hash-mixed per-floor seed, never sequential
    draws; generation does not consume the runtime RNG. Full
    record: `docs/FLOOR_GENERATION.md`.)
12. **Pre-connected passages (amendment, same day).** Each floor
    also starts with a natural passage network: pre-carved
    tunnels connecting the entry camp to several natural
    cavities and partway through the floor — with branches, dead
    ends, and at least one loop. The richest veins and some
    cavities stay off-network, reachable only by carving.
    Passages start dark and follow the ordinary lit-nav-graph
    rules; no sim rule treats them specially.
13. **Dens and stairs on the network (amendment #2, same day —
    this settles the descent question).** The passage network
    connects to some monster dens (Floor 1: at least 2 gloam-rat
    dens on-network, none within 10 network steps of the entry;
    off-network dens are a minority). **The stairs down live in
    a natural cavern on the network**, far from the entry in
    network distance (Floor 1 guarantee: ≥ 24 steps), so finding
    the way down is exploration, never a strip-mining search.

## Architecture

Core/frontend split, the Milky Way pattern: a deterministic Rust sim
core (`sim/`), engine-agnostic and headless-testable; a Godot 4
frontend later as a replaceable presentation layer. Saves are canonical
JSON + SHA-256 state hash; the Deep Ledger is append-only.

## Slice plan

- **S1 — sim core (BUILT, see status).** Voxel Shallows; lantern
  network as lit nav graph; one named delver (needs, skills) running
  delve → haul → convert; frontier extension with first-light Ledger
  entries; lantern fuel burn-down; canonical save/load + determinism.
- **S2 — colony breadth (BUILT 2026-11-10).** Multiple delvers, job
  assignment (miner/hauler/farmer), morale, food production at camp,
  surface recruitment arrivals. *(Owner lifted the per-slice gate
  2026-11-10 and authorized every slice to a working prototype.)*
- **S3 — the dark bites (BUILT 2026-11-10).** First creatures +
  combat-led threat model, lantern-clock strandings and rescue runs,
  failed-rescue permadeath and Ledger losses.
- **S4 — Godot frontend (BUILT 2026-11-10).** Presentation over the
  core via a file bridge (`sim/src/bin/bridge.rs`): depth-slice voxel
  view, lantern light, delver/critter models from the Game Asset
  Builder catalog, camp view, job assignment, carve/lantern/plant
  tools, live Deep Ledger feed. Verified headless (logic + state
  sync); a visual pass awaits owner hardware.
- **S5 — second band (BUILT 2026-11-10, sim side).** Fungal Reaches
  gate set (masks, fungal oil, herbalist), band recombination
  groundwork (`hazards_at` table; flooded/hot flags modelled, only
  spores simulated so far).
- **S6 — procedural floor generation (BUILT 2026-11-12, branch
  `underreach-delving-colony/floor-generation`).** Owner decisions
  11–13 above: a seeded generator (`sim/src/gen.rs`) producing a
  floor as a pure function of `(world_seed, floor_index)` — theme
  table for all five bands (Floor 1 designed, the rest explicit
  stubs), natural passage network with dens and the descent
  cavern on it, embedded veins/hazard pockets/dressing. The S3
  colony loop runs end-to-end on a generated Floor 1 (bridge
  scenario `gen`). Design record: `docs/FLOOR_GENERATION.md`.
- **S7 — the Shallows bite back (BUILT 2026-11-23, branch
  `underreach-delving-colony/hazard-mechanics`).** Cave-in and
  bad-air mechanics for the pockets S6 generates, with their
  decision-9 answers. Mining a face ringed with loose rock
  rolls per unit mined (2% per neighbouring loose cell); a
  collapse fills the stand with rubble and deals 55 damage —
  the downed are dug out on the rescue clock. Bad air seeps
  from sealed pockets into adjoining open cells: gasping at
  60 load (work halved), hp drain at 100. Timber supports
  and vents are placed kit at 1 goods each. Sim + bridge
  only; frontend surfacing follows later, as S5's did.
- **S8 — floor-to-floor traversal (BUILT 2026-11-24, branch
  `underreach-delving-colony/traversal`).** Per-floor stored
  state in the save (`Sim.floors`, keyed by floor index); the
  active floor swaps in/out on `descend()` / `ascend()` (also
  bridge commands). First arrival on a floor generates it
  purely from `(world_seed, floor_index)` and founds a
  forward camp at its entry camp; return visits restore the
  packed state exactly. Descents and ascents are ledgered
  (`Descended` / `Ascended`, naming the floor and its band).
- **S9 — floors 2–5 scenarios and balance (BUILT 2026-11-24,
  branch `underreach-delving-colony/band-scenarios`).**
  Per-band founding (`build_scenario_gen_floor`), one
  scenario per band floor on the demo seed, and a balance
  pass that tuned nothing (every band playable as generated).
  The Fungal proof came back negative — spores and fungal
  oil do not engage on generated floors (see status) — so
  no band's `built` flag flipped.
- **S10 — deeper band hazards (BUILT 2026-11-24, branch
  `underreach-delving-colony/band-hazards`).** Band-keyed
  hazard exposure designed once for all bands
  (`Sim::hazards_here`: a generated floor's band flags rule
  in its deep zone, y ≥ 6; hand-built worlds keep the
  depth table exactly), the Drowned flooding mechanic
  (water load, lantern dousing) with pumps and sealed
  pressure lanterns, and the Magma heat mechanic (heat
  load) with cooling gear. The Fungal, Drowned, and Magma
  `built` flags flip; Crystal stays unbuilt.
- **S11 — Godot frontend surfacing (BUILT 2026-11-24, branch
  `underreach-delving-colony/frontend-surfacing`).** The
  S7/S8/S10 pieces the frontend did not render — supports,
  vents, pumps, flooded cells, per-delver air/water/heat
  loads, cooling-gear stores, and floor traversal — are
  surfaced: placeholder kit markers, a flooded-cell overlay,
  load lines + suffering flags on delver panels and name
  labels, a HUD floor/band indicator, descend/ascend
  controls, support/vent/pump tools, and a cooling-gear
  button, all over the existing bridge commands. The bridge
  view gains two purely additive presentation fields (band
  name; the sim's own suffering booleans) so no sim rule is
  re-derived in the frontend.
- **S12 — children & generations (BUILT 2026-11-24, branch
  `underreach-delving-colony/generations`).** Decision 5's
  second growth source, opt-in in the `critters_enabled`
  pattern: `generations_enabled` defaults off and a disabled
  sim is bit-identical to the pre-S12 sim, state hash
  included. Delvers carry an age (`TICKS_PER_YEAR` 2400,
  founded at 25, adult at 18); births fire deterministically
  on the recruitment cadence when two adults live, food
  meets the recruitment minimum, and population is under
  the cap — the `ChildBorn` Ledger entry names the child
  and both parents (the two longest-present adults).
  Children live camp life but cannot be assigned, gain no
  job XP, and are never rescuers; the 18-year crossing
  ledgers one `CameOfAge` and they are ordinary delvers
  from then on. Modelling decisions in `docs/TEST_PLAN.md`.
- **S13 — co-op foundations (BUILT 2026-11-24, branch
  `underreach-delving-colony/coop-foundations`).** The
  lockstep foundation for the 1–4 co-op, headless only: a
  typed `Command` layer mirroring the bridge's vocabulary, an
  attributed `SessionLog` (founding save + `{tick, player,
  seq, command, applied}` entries) with a canonical merge
  (sort by `(tick, player, seq)`; duplicates and `seq` gaps
  are errors), and a `Session` driver whose sessions replay
  from the log to the identical state hash. **Co-op itself
  is NOT built**: no networking, transport, host/join, pacing,
  or Godot multiplayer — none of it is headless-verifiable.
  The full record, including the open owner design questions
  (frontier rights/permissions, multi-rescuer lantern clock,
  player downing/rescue) and the recommended first
  real-machine step, is `docs/COOP_ASSESSMENT.md`.
- Later: Crystal Dark gates, colony failure & succession.

## Status — 2026-11-10

- **Implemented and verified (VM, headless):** the S1 sim core, the
  S2 colony layer, the S3 threat/rescue layer, the S5 Fungal
  Reaches (sim side), and the S4 Godot frontend — `cargo test`
  25/25, the `scenario` binary's four-slice run, and the frontend's
  `UNDERREACH_VERIFY_PASS` headless run. Details and numbers in
  `docs/TEST_PLAN.md`.
- **Asset swap (2026-11-11, VM-verified load/logic):** the owner
  lifted the PC stop on 2026-11-10 (~22:13) and the builder lane
  finished the dedicated delver — an arm-separation-gated rebuild
  (new A-pose concept, preflight PASS; the owner's hard requirement
  is that arms/limbs are never fused to the body along their
  length). The frontend now renders the dedicated delver (catalog
  sha `7ab7262b7eeb…`) instead of the snow-goblin stand-in, plus
  the builder's Tier-1 lantern prop (OmniLight kept) and cot prop
  for beds. Headless verify passes identically; provenance in
  `frontend/README.md`, numbers in `docs/TEST_PLAN.md`.
- **Gloam-lurker + on-PC pass (2026-11-12):** the owner lifted the
  full PC testing stop; the builder lane finished the gloam-lurker
  (catalog sha `f0c881cb9bd3…`; texture succeeded on the first
  post-reboot paint dispatch; quadruped leg-separation gates
  passed — concept preflight and posed renders). The frontend now
  renders it as `CRITTER_SCENE`; the ember-dragon stand-in is
  retired (file kept, unused). The same day, the frontend ran
  windowed on the owner's PC against a live cross-compiled sim
  bridge: `UNDERREACH_VERIFY_PASS` on Windows with identical
  numbers and zero script errors. Details in `docs/TEST_PLAN.md`.
- **CONFLICT RECORDED 2026-11-12, RESOLVED 2026-11-12 (rule 3):**
  the capture redo reported the 3D viewport pitch black in every
  frame despite a live sim. A same-day diagnosis pass on the
  owner's PC (owner's go given) could NOT reproduce any rendering
  defect: with the game window fully on-screen, the unmodified
  frontend renders the world on the RTX 3060 — lit/unlit floor
  MultiMesh with instance colours, rock rim, chest, cots, lantern
  prop with its OmniLight pool, and delver figures — across two
  scenarios (s3, s5), two process instances, 800+ live ticks, and
  a minimize/restore cycle. Pixel analysis of the original
  "black" captures shows the viewport uniformly at the
  Environment background colour (5,5,11) — the camera and
  environment were rendering even then; the lit room is small and
  centred, and that session's window was mostly off-screen /
  behind other windows while being chased via minimize/restore,
  so the captures never contained the room. Ruled out with
  evidence: camera-never-current (background renders), broken
  environment, MultiMesh instance-colour failure under the
  Compatibility renderer (floors/rocks render coloured), GLB prop
  failure, minimize/restore window-state loss. The historical
  captures' exact mechanism is not proven beyond that, but no
  frontend code defect reproduces, so NO code change was made —
  full evidence in `docs/TEST_PLAN.md`. Capture protocol lesson:
  place the window fully on-screen (`--position`) and pixel-check
  a capture before declaring a render defect. Still not observed
  on PC: a critter in frame (both scenarios sat at Critters 0) and
  readable name-label detail at capture zoom; delver clip motion
  rests on the headless verifies plus figures re-posing between
  captures.
- **On-PC run note:** the PC verify/launch needs the
  `UNDERREACH_BRIDGE` environment variable set to the release
  `bridge.exe` path; without it the frontend falls back to a
  non-existent debug path and fails.
- **Planned:** the "Later" list above (Drowned/Crystal/Magma
  mechanics, co-op, succession, generations) — future programs, not
  part of the 2026-11-10 all-slices build.
- **On-PC visual pass: DONE 2026-11-12** (see the resolution
  above and TEST_PLAN's diagnosis section). The frontend renders
  and plays live on the owner's PC.
- No performance claims: the frontend has run on owner hardware,
  but no frame-time measurement has been taken there.
- **S6 — procedural floors (2026-11-12, VM-verified; branch
  `underreach-delving-colony/floor-generation`, not yet merged):**
  owner decisions 11–13 built and verified headless — `cargo
  test` 37/37 (25 pre-existing + 10 new generation tests + 2
  generator unit tests), the `scenario` binary's GEN section runs
  the colony loop clean on the demo-seed Floor 1 (goods 24 after
  opening, nobody lost), and the Godot headless verify prints
  both PASS lines (s3 unchanged; `scenario=gen` with 61 floor
  instances on the descent layer). The network guarantees hold
  across seeds 1–16 + the demo seed. NOT built: floors 2–5
  scenarios/balance (stub themes generate only), floor-to-floor
  traversal, cave-in/bad-air mechanics, face registration for
  embedded pockets. Full record: `docs/FLOOR_GENERATION.md`,
  numbers in `docs/TEST_PLAN.md`.
- **S7 — the Shallows bite back (2026-11-23, VM-verified;
  branch `underreach-delving-colony/hazard-mechanics`, not
  yet merged):** the S6 hazard pockets are live. `cargo test`
  43/43 (37 pre-existing + 6 new S7 tests); the `scenario`
  binary's S1–S6 sections are unchanged in behaviour, and
  its new S7 sections show the contrast the slice exists
  for: an unprotected face (falls cleared by the player
  script) takes 3 cave-ins and 2 gasping events in 6,000
  ticks with 1 downed and 0 lost, while the same face under
  a timber support and a vent (2 of its 4 starting goods)
  takes none. Two modelling decisions where the record was
  silent, both flagged in `docs/TEST_PLAN.md`: cave-ins
  trigger on mining only (not carving or passing), and a
  bad-air pocket carved open is spent. NOT built: frontend
  surfacing for supports/vents/air, floors 2–5 scenarios,
  floor-to-floor traversal.
- **S8 — floor-to-floor traversal (2026-11-24, VM-verified;
  branch `underreach-delving-colony/traversal`, not yet
  merged):** the S6 descent is a transition. `cargo test`
  51/51 (43 pre-existing + 8 new S8 tests); the `scenario`
  binary's S1–S7 sections are unchanged in behaviour, and
  its new S8 section produces on floor 1 (goods 24), descends,
  produces on floor 2 (goods 24 → 33, 5 deliveries there,
  nobody lost), then ascends and finds floor 1's world and
  lanterns exactly as left. Three modelling decisions where
  the record was silent, all flagged in
  `docs/TEST_PLAN.md`: whole-colony immediate transition
  (no per-delver cross-floor pathing — every delver gathers
  at the new floor's entry camp on descent, and at the floor
  above's descent cell on ascent); a floor left behind is
  frozen (its lanterns do not burn fuel while the colony is
  away); on first arrival a forward camp is founded at the
  entry camp mirroring `build_scenario_gen`'s founding, and
  farming plots do not carry down. NOT built: floors 2–5
  scenarios/balance and band mechanics (floor 2 generates
  and runs the generic loop, but the Fungal gate set is not
  wired per-floor), frontend surfacing for traversal.
- **S9 — floors 2–5 scenarios and balance (2026-11-24,
  VM-verified; branch
  `underreach-delving-colony/band-scenarios`, not yet
  merged):** colonies found directly on floors 2–5 and run.
  `cargo test` 60/60 (51 pre-existing + 9 new S9 tests); the
  `scenario` binary's S1–S8 sections are unchanged in
  behaviour and state hash, and its new S9 sections produce
  on every band (goods F2 9, F3 15, F4 9, F5 6 in 6,000
  ticks; nobody lost; every colony ends fed). **Balance:
  no theme numbers were tuned** — no band met the tuning
  triggers (cannot produce / starves / wiped by its dens).
  **FINDING (feeds S10): the Fungal Reaches' mechanics do
  not engage on generated floor 2.** Spore exposure is
  keyed to depth via `hazards_at(y)` — spores only at
  y ≥ 10 — while generated floors hold all carved space at
  y ≤ 9 (GEN_MAX_Y); an unmasked delver staged at floor 2's
  face for 2,000 ticks gains exactly 0.0 spore load, proven
  by test. Fungal oil never flows either: generated faces
  are registered from the theme's primary resource cell
  (ore) only, and fungal-node clusters are embedded pockets,
  not faces. `hazards_at` was NOT rewired in this slice —
  band-keying exposure would change S8's floor-2 behaviour,
  so it is not provably inert for the existing baselines;
  band-keyed exposure should be designed once, with S10's
  flooding/heat mechanics. **`built` decisions: no band
  flips.** Fungal fails the engagement test above; Drowned
  (`flooded` flag-only) and Magma (`hot` flag-only) wait on
  S10; Crystal's gate items were never modelled. No
  pre-existing assertion changed. NOT built: flooding/heat
  mechanics, band-keyed hazards, Crystal gate items,
  frontend surfacing for floors 2–5.
- **S10 — deeper band hazards (2026-11-24, VM-verified;
  branch `underreach-delving-colony/band-hazards`, not yet
  merged):** the Drowned and Magma hazards are live, and
  exposure is band-keyed. `cargo test` 70/70 (60
  pre-existing + 10 new S10 tests); every S1–S9 scenario
  section reproduces its behaviour numbers exactly (state
  hashes shift with the new save fields), and the S9 band
  runs now show the live events in the same numbers —
  floor 3: drowning 3, doused lanterns 3; floor 5:
  overheating 2; nobody lost anywhere. The new S10
  scenario sections show the contrasts: Drowned protected
  (pumps on every face stand + a pressure-lantern opening)
  and Magma protected (cooling gear for the colony) run
  the same production with zero band events. **Design:
  `hazards_here(pos)`** — on a generated floor the active
  floor's band flags (`theme_for_floor(index).hazards`)
  rule in the floor's deep zone (carved cells at y ≥ 6,
  generation's own bad-air line; the camp at y = 3 stays
  refuge, mirroring the hand-built camp above the Fungal
  line); hand-built worlds keep `hazards_at(y)` exactly,
  and the two never combine. **Flooding:** a water load
  (+1.0/tick in flood water, drowning at 60 — work halved,
  morale hit, bed-seeking — hp drain at 100 onto the
  rescue clock) plus lantern failure (an unsealed lantern
  in flood water loses 2.0 extra fuel/tick and dies as
  `LanternDoused`). Answers: a **pump** (placed kit,
  1 goods, dry reach radius 2 — the vent's mirror) and the
  **sealed pressure lantern** (tier 3, the existing tier
  rules and oil charge). **Heat:** a heat load in the
  same pattern (overheating at 60, drain at 100),
  answered by **cooling gear** (worn kit, 2 goods, the
  mask's mirror, prevents the gain entirely). Modelling
  decisions where the record was silent, all flagged in
  `docs/TEST_PLAN.md`: the deep-zone footprint for band
  exposure; air bells/drains not modelled (the pump's dry
  reach already provides refuge and a workable face); no
  placed heat answer (decision 9 leads with cooling gear,
  and worn kit travels the whole hot zone); and
  `SPORE_RATE_MASKED` corrected 0.05 → 0.0 so a mask
  protects entirely, as S5's record always said. **`built`
  flips: Fungal, Drowned, and Magma to `true`** (each
  band's mechanics demonstrably engage on its generated
  floor with scenario + balance recorded); **Crystal
  stays `false`** — its gate items were never modelled.
  NOT built: frontend surfacing for pumps/flooded cells/
  water/heat loads/cooling gear (the bridge view carries
  them all), face registration for embedded pockets (the
  S9 finding's oil half stands — generated faces still
  yield ore only), Crystal gate items.
- **S11 — Godot frontend surfacing (2026-11-24, VM-verified;
  branch `underreach-delving-colony/frontend-surfacing`, not
  yet merged):** the frontend-not-rendered caveats of S7, S8,
  and S10 are closed. Supports, vents, and pumps render as
  placeholder markers (distinct colour per kind, dressing
  idiom; no catalog GLBs exist), flooded cells as a
  blue-tinted overlay instance per cell on the viewed layer,
  and delver panels + name labels carry air/water/heat loads
  verbatim with `[SICK]` / `[GASPING]` / `[DROWNING]` /
  `[OVERHEATING]` text flags and MASKED / COOLED state. The
  HUD shows floor index + band, with descend/ascend buttons
  and PgDn/PgUp keys, support/vent/pump click tools, and a
  craft-cooling button — commands only; no sim rules in the
  frontend. One bridge change, purely additive and justified
  in `docs/TEST_PLAN.md`: the view gains `band` (the sim's
  own `band_for_floor`) and per-delver suffering booleans
  (the sim's own predicates), so the frontend never
  re-derives the band table or the load thresholds. The sim
  library is untouched: `cargo test` 70/70 and every
  scenario section's numbers reproduce exactly. The headless
  verify prints its two prior PASS lines unchanged plus
  `UNDERREACH_VERIFY_PASS scenario=s11 supports=1 vents=1
  pumps=1 cooling_gear=1 floor_index=3 flooded=96
  flooded_layer=35 tick=0` — kit placed through the bridge
  on the S7 colony, cooling gear crafted on a fresh founding
  (the kit leaves 1 good, short of the 2-good craft), the
  floor indicator followed through descend 1 → 2 → 3, and
  the Drowned floor's flooded overlay matched to the view
  on layer 9. **Rendered appearance of all S11 surfacing is
  UNVERIFIED** — headless proves load and logic only; a
  visual pass awaits the owner's PC. NOT built: Crystal
  gate items, face registration for embedded pockets.
- **S12 — children & generations (2026-11-24, VM-verified;
  branch `underreach-delving-colony/generations`, not yet
  merged):** decision 5's second growth source is live.
  `cargo test` 80/80 (70 pre-existing + 10 new S12 tests);
  the `scenario` binary's S1–S11 sections are byte-identical
  to the pre-S12 run — **numbers and state hashes alike** —
  and the new S12 section shows the full arc in 7,000 ticks:
  2 births, 1 coming of age, the grown child (Joss) assigned
  Miner with mining XP 388, goods 964, 2 children at camp,
  nobody lost. The inertness proof is a pinned test: the S3
  scenario, flag off, reproduces its pre-S12 hash exactly.
  Modelling decisions where the record was silent, all
  flagged in `docs/TEST_PLAN.md`: `TICKS_PER_YEAR` 2400 (one
  recruitment cycle); founders/recruits founded at 25, adult
  at 18; age inert while the system is off (the new save
  fields omit themselves at their inert defaults); births
  deterministic on the recruitment cadence, no probability
  roll, parents the two longest-present adults, name from
  the recruitment pool with a no-birth fallback if it is
  exhausted; `BIRTH_MIN_FOOD` reuses `RECRUIT_MIN_FOOD`;
  childhood is camp life only — no school, childcare, or
  carrying. The S12 colony is founded with a 17-year-old
  child and takes no recruits (choreography, recorded in
  TEST_PLAN); the from-birth arc is proven in tests. The
  bridge view gains additive `age_years` / `is_child` per
  delver; the frontend renders neither yet. NOT built:
  Crystal gate items, face registration for embedded
  pockets, any frontend surfacing for age/children, colony
  failure & succession.
- **S13 — co-op foundations (2026-11-24, VM-verified;
  branch `underreach-delving-colony/coop-foundations`, not
  yet merged):** the lockstep foundation is built and
  verified; co-op itself is not. `cargo test` 87/87 (80
  pre-existing + 7 new S13 tests); the `scenario` binary's
  S1–S12 sections are byte-identical to the pre-S13 run —
  **numbers and state hashes alike** (the session layer is
  additive library code; the bridge is unmodified) — and
  the new S13 section runs a two-player session on
  generated floor 1 (P1's 10 lantern commands light the
  way, P2 plants a plot and sets a support + vent): goods
  22, nobody lost, `replay_matches=true` computed by
  replaying the log inside the section, hash
  `11e30e9ddb3f6aa9b46e2fdd32df9a13ecf66f9d8c4dbfff4b4c6c332f2c787d`.
  What exists: the typed `Command` layer (the bridge's
  vocabulary; its choreography scripts excluded as founding
  scripts, not commands), the attributed `SessionLog` with
  canonical merge (arrival-order independent; duplicate
  `(player, seq)` and `seq` gaps are errors), live `Session`
  + `replay` to the identical hash, mid-session save/load
  resume, and JSON log roundtrips — plus the desync *check*
  that has existed since S1 (canonical save + SHA-256).
  **NOT built (not headless-verifiable): network transport
  and host/join, session discovery, lockstep pacing under
  real latency, Godot multiplayer, desync recovery over a
  live connection, and play with real clients on real
  machines.** Owner design questions the slice surfaced but
  did not decide — per-player frontier rights/permissions,
  whether the lantern-clock rescue changes with multiple
  rescuers, and player downing/rescue (decision 6 was
  written for one player) — are recorded in
  `docs/COOP_ASSESSMENT.md` with the recommended first
  real-machine step (a two-process loopback session on the
  owner's PC, hashes compared every 100 ticks).
