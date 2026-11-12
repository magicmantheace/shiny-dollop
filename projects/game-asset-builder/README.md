# Game Asset Builder

**Status: P0 pipeline built and proven end-to-end (2026-11-06). The
Hunyuan3D-2 shape+paint pair won the Pip bake-off (RIGGABLE, front
silhouette IoU 0.84 vs the Meshy reference; `benchmarks/pip/scores.md`),
and the full pipeline — cutout → mesh → texture → rig → animate →
catalog — ran a brand-new creature (the Ember Dragon) from concept
image to a rigged, animated, catalogued .glb. Run it with
`python3 asset_builder.py run --concept <image> --name "<Name>"`.
Catalogue record: `catalog/ember-dragon/metadata.json` (the .glb
itself lives in the local `outputs/` area, pinned by sha256).**

**Skinning update (2026-11-06): the rig stage now produces real
bone-heat (automatic) weights. The P0 build's heat failure was
diagnosed to two causes — residual non-manifold geometry in Hunyuan
output (Blender's heat solver needs a closed 2-manifold and otherwise
fails silently with zero weights) and template bone endpoints landing
outside the mesh volume (23 of 28 on the dragon; bbox fractions can't
know where a generated model folded its wings). The rigger now repairs
the geometry to (near-)manifold and snaps outside endpoints onto the
surface before weighting; an acceptance policy in
`stages/rig/skin_policy.py` decides whether a heat result ships, and
the distance-to-bone fallback remains as the labelled last resort.
Ember Dragon re-rigged: heat weights, wingtip dominance 0.0 → 1.0;
details in `docs/MUSE_HANDOFF.md`.**

**P1 update (2026-11-06): quadruped + biped rig templates and the
unrigged prop path are built and proven end-to-end on three new
assets, all through the same pipeline: a baby **Triceratops**
(quadruped template, 15 bones, `idle` + `bounce`), a **Snow Goblin**
(biped template with ears, 13 bones, `idle` + `wave`), and a
**Treasure Chest** (prop path — static GLB, no armature, catalogued
as unrigged). All three shipped real bone-heat weights where rigged
(coverage 1.0; feet/hands tip dominance 1.0). Two honest wrinkles,
detailed in `docs/MUSE_HANDOFF.md`: the triceratops mesh came out
of Hunyuan sideways and needed the pipeline's per-run `--rotate-z`
facing correction, and the goblin's fused-fur ruff is partly
arm-weighted, so poses well beyond the shipped wave drag fur.
Catalogue records: `catalog/triceratops/`, `catalog/snow-goblin/`,
`catalog/treasure-chest/` (GLBs in local `outputs/`, sha-pinned).**

**Environment pack (2026-11-10): seven unrigged props for scene work —
pine-tree, boulder, bush, fern, mushroom-cluster, fallen-log, stump.**
Builder-shaped on the owner's PC; painted procedurally (vertex
colours) because the Hunyuan paint stage stalls on this machine —
see `docs/PAINT_STALL.md`. Catalogue records under `catalog/<slug>/`.


**P1.1 update (2026-11-06): the weight-distance veto is now part of
the rig stage** (owner-flagged on the goblin's wave render: the body
texture stretched with the raised arm). After bone heat, any
non-trunk bone's weight on a vertex beyond its reach radius
(0.85 × bone length, floored at 0.19 × mesh height; the root→head
trunk chain is exempt) is zeroed and renormalized onto the surviving
bones; `skin_policy.py` additionally gates the torso zone's arm
weight share (≤ 0.25). The Snow Goblin was re-rigged from its saved
textured mesh — no GPU stages re-ran: torso arm share 0.51 → 0.14,
head-zone dominance 0.67 → 0.79, hands dominance 0.997, coverage
still 1.0, and in the re-rendered wave the chest and ruff stay put.
Residual honesty: a taut fur sheet still stretches in the armpit web
at the wave's peak (the arm and torso are one fused fur mass — some
web must stretch), and the 2.2 rad stress raise still sails the
flank. The other P1 assets were not regenerated; their catalogue
entries are byte-identical. Details in `docs/MUSE_HANDOFF.md`.**

**P2 cleanup update (2026-11-06): three layers on the
`game-asset-builder/p2-cleanup` branch (draft PR stacked on #38).**
(1) A concept pose & separation spec (per body plan, in
`docs/DESIGN.md`) plus a pre-flight fused-limb check that records
a pass/warn in every rigged run's manifest — the to-spec giraffe
concept passes; the original goblin concept warns. (2) The veto's
reach is now geodesic-aware: max(Euclidean, surface) distance, so
weights cannot leak across a fused web on a straight line.
(3) A new **segment stage** (P3-SAM, chosen by bake-off over
PartField on licence — `benchmarks/segmentation/scores.md`) labels
the textured mesh's parts; the rig separates geometry at part
boundaries and adds a label-aware veto on top of the geodesic
one. Goblin re-proof: torso arm share 0.139 → **0.079**, head
dominance 0.881, the 2.2 rad stress sail materially reduced
(residual: the arm part's own web fin). Triceratops re-proof:
feet/head dominance 1.0, belly share 0.200, two of four legs as
their own parts (P3-SAM's known weakness). Ember Dragon and
Treasure Chest untouched, byte-identical. Suite 79/79. Details in
`docs/MUSE_HANDOFF.md`.**

**P2 UI update (2026-11-07): a simple local UI over the catalog and
pipeline** (branch `game-asset-builder/p2-ui`, stacked on the P2
cleanup branch). `python3 asset_builder.py ui` serves a stdlib-only
single-page UI on localhost (default port 8770): catalog cards for
every asset (rig/prop, bones, clips, counts, preview renders, GLB
presence) with an on-demand sha256 verify against the catalog entry;
the stage registry and doctor report; and a run form that launches
the existing CLI as a subprocess — GPU stages still dispatch to the
owner's PC through the bridge, using the server process's
environment for the token. No dependencies, no build step, binds
127.0.0.1 by default. Suite 92/92; details in
`docs/MUSE_HANDOFF.md`.**

**P3 update (2026-11-07): engine hand-offs built and playback
PROVEN in both engines** (branch `game-asset-builder/p3-handoff`,
stacked on the P2 UI branch). `asset_builder.py export-godot /
export-threejs / export-studio` turn any catalogued asset into a
ready package — every export sha-verifies the GLB against the
catalog record before and after copying, and refuses a mismatch.
Playback, the project's standing unverified gap, is now closed:
**Godot 4.7.2** (owner's PC, headless) instanced all four exported
assets through their wrapper scenes — bone sets equal the catalog,
every baked clip moves the skeleton (hop Δ0.085, goblin wave
Δ1.69, bounce Δ0.096; the chest verified static) — and **three.js
0.180** (Chrome headless, SwiftShader) loaded and played the same
GLBs through GLTFLoader + AnimationMixer with matching bone counts
and identical clip durations. The studio export emits the
animation studio's intake format (validated against its real
schema; records stay `candidate` — promotion is the studio's
process). Harnesses + procedure: `handoff/README.md`. Suite
101/101; full numbers in `docs/TEST_PLAN.md`.**

**P4 update (2026-11-08): game-ready locomotion — every rigged
creature now walks and runs** (branch
`game-asset-builder/p4-game-animations`, stacked on the P3 branch).
At the owner's direction ("produce walking animations and any kind
of animation needed for a game"), the animate stage gained a
parametric gait model (`stages/animate/poses.py`, P4 section): one
swing/fold curve pair per leg, phase-offset per rig class —
anti-phase pairs for the biped-plan templates, a lateral-sequence
walk (FL → HR → FR → HL) and a bounding-gallop run for the
quadruped. Loops close exactly by construction; the new leg/arm
drivers were axis-probed on the shipped rigs like the P0/P1 ones.
The three catalogued creatures were re-animated from their existing
rigged GLBs (no mesh, texture, or rig change) and now carry four
clips each — Ember Dragon: hop/idle/**walk 1.5 s**/**run 1.0 s**;
Snow Goblin: idle/wave/**walk**/**run**; Triceratops:
bounce/idle/**walk 2.0 s**/**run** — with catalog records updated
(actions, per-clip durations, new sha256). Suite **113/113**;
three.js playback of the new clips verified on the build VM
(Electron Chromium + SwiftShader, the project's harness page);
full numbers and the honest limits (procedural gaits, no IK) in
`docs/TEST_PLAN.md`.**

**P5 update (2026-11-09): the campfire creatures pack — DONE,
6 of 8** (branch `game-asset-builder/p5-campfire-creatures`,
stacked on the P4 branch). Eight whimsical smashup creatures
commissioned for the campfire wallpaper. New rig templates landed
first: `winged-quadruped` (quadruped + wing pair + optional
ear/antenna bones) and `snail` (legless body chain + eye stalks +
shell bone; locomotion is an undulation `glide`, showcase is
`retract`), plus a per-creature SIGNATURES registry in the animate
stage (`fan`, `headturn`, `bounce`, `scream`, `bow`, `shiver`,
`wiggle`). **Built, catalogued, and verified end to end**
(catalog-verify MATCH + three.js playback with bone deltas for
every one): **Moth-Hart** (winged-quadruped + ears, `fan`, 21
bones), **Toasty** (biped, `bounce`, 11 bones), **Lantern Snail**
(snail, `retract`, 9 bones), **Axolotl-Capybara** (quadruped,
`wiggle`, 15 bones), **Geode Tortoise** (quadruped, `shiver`, 15
bones), **Crow Postman** (biped, `bow`, 11 bones). **Two honest
failures, not catalogued:** the **Ember Owl-Cat** (paint stage
non-terminating across two attempts — unbounded memory growth,
killed at 2h33m and ~60 min) and the **Mandrake Toddler** (retry
paint died mid-bake without a traceback after its first attempt
was killed on a memory criterion the pack's own evidence later
disproved — both failures are written up in their
`outputs/<slug>/attempt1-texture-note.txt`).
**Update (2026-11-10): the Mandrake verdict was wrong — its retry
paint had succeeded and the finished texture was recovered from
the lab; the remaining stages then ran and the Mandrake Toddler
is catalogued (7 of 8), leaving only the Ember Owl-Cat
unfinished.** **Update (2026-11-10, later): the paint stall is
FIXED (see `docs/PAINT_STALL.md` — a CUDA caching-allocator
pathology, cured by `expandable_segments` in the paint stage) and
the Ember Owl-Cat finished end to end: texture stage exit 0
(6,202 s on the 1.41M-face mesh), then segment → rig → animate →
catalog, catalog-verify MATCH. The P5 pack is complete: 8 of 8.**
The pack's main
operational finding: the paint bake's ~17.7 GB private-memory
plateau is its fixed footprint on large meshes, not a runaway;
the completed paints ran 763–2,524 runner-seconds, the tortoise
at 1,643,448 faces the longest legitimate paint in project
history. Suite **134/134**. Full record in
`docs/MUSE_HANDOFF.md` and `docs/TEST_PLAN.md`.**

**Environment proof (2026-11-09): the first environment asset — a
stylized pine for the campfire wallpaper** (branch
`game-asset-builder/env-pine-proof`, stacked on the P5 branch).
The Hunyuan shape stage produced the tree in one pass (243,514
verts, 13 components, clay-verified), the prop path finished it
to 4,961 verts, and it is catalogued (`catalog/pine-tree/`,
catalog-verify MATCH) and proven to load and render in the
wallpaper's own three.js stack. **The paint is procedural vertex
colour, not Hunyuan paint**: the paint stage produced no result
on this foliage subject across repeated attempts (root cause
unproven — see the HANDOFF), so the asset ships honestly labelled
"builder-shaped, hand-painted" and the environment-paint question
stays open. Full record in `docs/MUSE_HANDOFF.md` and
`docs/TEST_PLAN.md`.**

A fully local, no-API pipeline that builds game assets — creatures included —
on the owner's own hardware:

```
concept image → cutout → [mesh model] → [texture model] → [segment model] → rig → animate → catalogued .glb
```

Mesh generation and texturing are **different local models**, each run as its
own stage in its own process, unloaded before the next stage loads. Rigging
and animation are procedural (Blender, headless), reusing the armature
templates and pose recipes proven on Pip, the Drabbit Pet character.

## Why

The Drabbit Pet's hero asset (Pip) was built by hand across a chain of
one-off tools, and its best mesh came from a cloud service. This project
turns that chain into one repeatable local tool, scored honestly: Pip is the
standing benchmark, and every local candidate is compared against the
cloud-generated reference Pip the owner already has.

## Hardware target

- Owner's PC: Windows 11, RTX 3060 **12 GB VRAM** (~9.2 GB free at rest),
  32 GB RAM. All heavy stages run here.
- The build VM has **no GPU** (7 GB RAM): orchestration, Blender work,
  cataloguing, and scoring only.

## Layout

- `docs/DESIGN.md` — founding decisions, stage architecture, candidate
  models, and the Pip benchmark protocol.
- `docs/TEST_PLAN.md` — what is verified, where, and what is not.
- `docs/MUSE_HANDOFF.md` — current state for the next working session.
- `stages/` — one folder per pipeline stage as they land.
- `catalog/` — the finished-asset catalog (lands with P0).
- `benchmarks/` — benchmark inputs, scores, and comparison sheets.

## Slices

- **P0** — model bake-off on Pip + the winning creature pipeline end-to-end
  (image → rigged, animated .glb + catalog entry).
- **P1** — more rig templates (quadruped, biped) + the unrigged prop path.
  **Done 2026-11-06** (see the P1 status note above).
- **P2 cleanup** — concept pose spec + preflight, geodesic weights,
  part segmentation + separation + label-aware skinning.
  **Done 2026-11-06** (see the P2 cleanup status note above;
  branch `game-asset-builder/p2-cleanup`).
- **P2** — a simple local UI over the catalog and pipeline.
  **Done 2026-11-07** (see the P2 UI status note above;
  branch `game-asset-builder/p2-ui`).
- **P3** — hand-off integrations (animation studio library, Godot projects).
  **Done 2026-11-07** (see the P3 status note above;
  branch `game-asset-builder/p3-handoff`).
- **P4** — game-ready animation sets: procedural walk/run gaits for
  every rig template, catalogued creatures re-animated in place.
  **Done 2026-11-08** (see the P4 status note above;
  branch `game-asset-builder/p4-game-animations`).
- **P5** — campfire creatures pack: eight smashup creatures on two
  new rig templates (winged-quadruped, snail) with per-creature
  signature clips. **Done 2026-11-09, 6 of 8** — six built,
  catalogued and verified; the Ember Owl-Cat and Mandrake Toddler
  failed at the texture stage and are catalogued as failures, not
  assets (see the P5 status note above; branch
  `game-asset-builder/p5-campfire-creatures`).

## Arm-separation rebuilds (2026-11-11)

Adam's requirement (2026-11-10): arms/limbs must not be fused to the body
along their length — a hard gate, not an advisory warning. The wallpaper
audit found six deployed creatures in violation. All six were attempted
on branch `game-asset-builder/arm-separation-fixes`; **none passed both
finish gates (catalog-verify + posed-render check), so no deployed
creature was replaced and no catalog entry changed.** Verified state:

- **Mandrake Toddler** — new two-bulb A-pose concept passed preflight
  (arm daylight 0.4437; the single-bulb bodyplan caps at ~0.31). Mesh is
  genuinely separated (rest renders show arms in daylight; bleed ~1%).
  **FAILED the posed gate:** bone heat rejected (torso arm share 0.60) →
  distance-fallback weights drag the belly at any scream amplitude
  (stock 1.50 rad catastrophic; ×0.35 belly-disc; ×0.18 feet smear).
- **Snow Goblin** — concept passed (0.4125), mesh passed; **texture
  stage failed twice** (freeze at "[paint] input mesh", then a
  ~100 min full-power bake with no output). Not catalogued.
- **Ember Owl-Cat** — **concept gate not passed** (best 0.3799 of nine
  attempts; down-wings cap ~0.38 on this bodyplan). No build started.
- **Crow Postman** — concept passed (0.4957), mesh passed and
  render-verified A-pose; **texture stage froze** (~65 min, no output).
- **Toasty** — concept passed (0.7697, best of the queue), mesh passed;
  **texture stage froze** at the same point.
- **Axolotl-Capybara** — concept passed (5 leg components, gap 0.0213),
  mesh passed; **texture stage froze** at the same point.

The Hunyuan paint stage degraded across the night: the delver and
mandrake textured fine early; goblin/crow/toasty/axolotl all froze at
"[paint] input mesh" (log frozen at 1,419 bytes, GPU 100% at ~60 W).
Root cause unproven (VRAM headroom suspected — successful paints peaked
~11.9/12.3 GiB). All failed assets keep genuine prep/mesh artifacts in
`outputs/<slug>/` with `ARMFIX-FAILURE-2026-11-11.md` notes for a future
retry. NOT verified: Godot playback (unchanged from before).

### Retry after the PC reboot (2026-11-12)

The reboot was the untested remedy; the gloam-lurker canary (Underreach
queue) textured clean on the first post-reboot dispatch, and Adam
authorized retrying the four texture-blocked rebuilds in order
(crow → toasty → axolotl → goblin). Deployment to the live wallpaper
is NOT part of the retry — rebuilt assets are catalogued on this
branch only; the deployed copies stay untouched until a separate
re-sync/re-apply step.

- **Crow Postman — SHIPPED to the branch catalog.** Texture exit 0 in
  1,206.26 s (genuine lab textured.glb sha-verified 92f448a5…).
  Segment P3-SAM 14 parts; biped rig, distance-fallback weights
  (disclosed); clips idle/walk/run/bow; catalog-verify MATCH
  (c2e23612…). Posed gate PASS with a disclosed weakness: rest and
  all shipped apexes are clean (sleeves separate, daylight in
  motion), but a forward arm raise drags the coat side panel into a
  sail — onset between 1.2 and 1.7 rad, full sail at the 2.2 rad
  stress pose. No shipped crow clip raises the arm past ~0.6 rad.
  One recovered incident: the dispatch client hit the bridge
  tracking limit mid-bake and fetched the stale previous-build
  texture (the goblin pattern); the client was killed before the
  segment stage consumed it and the genuine result was recovered
  from the lab — see `outputs/crow-postman/texture-retry-success.txt`.
- **Toasty — SHIPPED to the branch catalog.** Texture exit 0 in
  906.87 s (genuine lab textured.glb sha-verified b5ed9eda…); the
  VM runtime restarted mid-run but the genuine result was recovered
  from the lab by hash — no re-dispatch. Segment P3-SAM 7 parts;
  biped rig with **bone-heat weights accepted** (torso arm share
  0.0238); clips idle/walk/run/bounce; catalog-verify MATCH
  (3818679c…). Posed gate PASS with a disclosed weakness: the
  audited leg fusion is gone in every pose (bounce apex shows both
  legs hanging free, rim intact; stress step clean), but at the
  2.2 rad stress arm raise the body surface beside the arm peels
  into a standing flap — outside every shipped clip's arm range.
- **Axolotl Capybara — SHIPPED to the branch catalog.** Texture
  exit 0 in 1,362.99 s (genuine lab textured.glb sha-verified
  3b01e97c…); quadruped rig 15 bones, clips idle/walk/run/wiggle;
  catalog-verify MATCH (a925ab92…). Posed gate PASS, clean: the
  audited paddle-belly is gone — walk-apex belly close-up shows
  four distinct legs with daylight between them; the stress tuck
  drags no membrane. One recovered incident: the dispatch client
  hit the bridge tracking limit mid-bake, fetched the stale
  texture, and dispatched segment against it (PC free RAM fell to
  0.48 GB); the client and the wrong segment tree were killed,
  the genuine bake finished once RAM recovered, and the result
  was recovered from the lab by hash — see
  `outputs/axolotl-capybara/texture-retry-success.txt`.
- **Snow Goblin — texture OK, posed gate FAILED, NOT catalogued.**
  Texture exit 0 in 893.03 s (genuine lab textured.glb sha-verified
  61878b0e…; the queue's only clean end-to-end run); biped+ears rig,
  clips idle/wave/walk/run. But at the wave apex the raised arm
  drags a continuous fur blade from armpit to hip — the audited
  defect, in a shipped clip (torso arm-weight share 0.5389). Rest
  and walk are clean; per the mandrake precedent a shipped-clip
  defect means no catalogue: the catalog write was reverted. See
  `outputs/snow-goblin/texture-retry-GATE-FAILURE-2026-11-12.txt`.

### Snow Goblin — Option 1 code fix: cross-zone bone ban (2026-11-12)

Adam picked the code route. The rig's weight machinery gained a
**cross-zone bone ban** (`skin_policy.chain_groups` +
`zone_ban_map`; rig flag `--zone-ban GROUP:GROUP`, off by
default): bones are grouped into chains (trunk + one chain per
appendage root), and a named pair of zones may not own each
other's part-labelled flesh — `trunk:arm.L` bans the whole arm.L
chain on trunk-dominated labels and the trunk bones on arm-chain
labels. It closes the hole the parameter variants could not:
Layer 3 only forbids bones that DOMINATE another label, and the
arm labels are dominated by arm2, so arm.L/arm.R were never
banned on torso flesh. Enforcement reuses the Layer-3 machinery
(label-boundary vertices within the banned bone's reach keep
their blend — the shoulder's blend band), and `apply_veto` now
enforces label bans on trunk columns too (a ban on the spine
previously bound nothing).

The goblin's existing textured mesh (61878b0e…) was re-rigged
with `--zone-ban trunk:arm.L --zone-ban trunk:arm.R` — no mesh,
paint or segment stage re-ran. **Bone heat ACCEPTED for the
first time on this mesh: torso arm share 0.0385** (gate 0.25;
the rejected heats were 0.3768/0.3211, the fallback 0.5389),
coverage 1.0, head dominance 0.97. Posed gate PASS: the wave
from behind shows no continuous sheet armpit→hip — the raised
arm reads as an arm and the back stays home; rest/walk/run
clean, shoulders blended. Disclosed weakness (the crow/toasty
class): the arm's own underside fur fringe — flat fur-card
geometry in the mesh — hangs as a soft flap under the raised
arm in the wave and spikes into slivers at the beyond-spec
2.2 rad stress raise; shipped clips (≤ ~0.95 rad) show the
flap only. **Catalogued: sha 6cfaaa6e…, catalog-verify MATCH;
deployed to the campfire wallpaper the same day** (both PC
copies hash-verified, Lively re-applied). Suite 144/144
(9 new zone-ban tests). The failed rig's artifacts are kept in
`outputs/snow-goblin/before-zoneban/`.
