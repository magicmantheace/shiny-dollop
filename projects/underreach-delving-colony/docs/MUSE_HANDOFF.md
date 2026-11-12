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
- Later: Drowned/Crystal/Magma gates, co-op, colony failure &
  succession, children/generations.

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
- **CONFLICT RECORDED 2026-11-12 (rule 3 — implementation reality
  vs the spec's working-prototype expectation):** the capture redo
  ran on the owner's PC with the workstation unlocked. The sim is
  genuinely live (live `state.json`: 15 carved/lit cells at the
  viewed layer, 4 delvers and a lantern beside the camera target;
  HUD tick/Food/Delvers advancing; zero script errors) — **but the
  3D viewport renders pitch black in every frame**: no terrain, no
  delver, no lantern prop or light pool, no labels. The headless
  verify counts instances and nodes and never checks pixels, which
  is how this survived every earlier pass. Root cause is NOT
  proven; candidates from the code read are MultiMesh
  instance-colour handling with `vertex_color_use_as_albedo` under
  the Compatibility renderer, or world-node setup. Recorded here
  rather than silently worked around; diagnosis/fix is the next
  step, on the owner's go. Until then the frontend's rendered
  appearance (delver, lantern, cot, gloam-lurker in scene) is
  unverified and the 3D view must be treated as not working.
- **On-PC run note:** the PC verify/launch needs the
  `UNDERREACH_BRIDGE` environment variable set to the release
  `bridge.exe` path; without it the frontend falls back to a
  non-existent debug path and fails.
- **Planned:** the "Later" list above (Drowned/Crystal/Magma
  mechanics, co-op, succession, generations) — future programs, not
  part of the 2026-11-10 all-slices build.
- **Outstanding on owner hardware:** the on-PC visual pass of the
  frontend (the 2026-11-10 stop was lifted 2026-11-10 ~22:13, so
  this is unscheduled rather than blocked).
- No performance claims: nothing has run on owner hardware.
