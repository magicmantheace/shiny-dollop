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
