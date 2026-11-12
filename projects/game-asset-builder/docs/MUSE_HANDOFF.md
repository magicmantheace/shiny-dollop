# Handoff — Game Asset Builder

## State at scaffold (2026-11-06)

Commissioned by the owner on 2026-11-06 with three binding constraints:
**fully local, no APIs**; **mesh and texture are different models that
unload between uses** (separate processes); **test multiple models**, with
**Pip as the benchmark** against the owner's Meshy-generated reference Pip.

Done:
- Project scaffold: README, AGENTS.md, DESIGN.md (founding decisions, stage
  architecture, candidate matrix, benchmark protocol), REQUIREMENTS.md,
  TEST_PLAN.md, .gitignore.
- Stage registry (`stages.py`) + stdlib CLI (`asset_builder.py`:
  doctor / stages / benchmark-plan) + 8 unit tests, all passing on the VM.
- Benchmark input committed: `benchmarks/pip/input-idle.png` (the exact
  cutout that produced the reference).
- Hardware verified firsthand: VM has no GPU (7 GB RAM); owner's PC has an
  RTX 3060 with 12,288 MiB VRAM / 9,210 MiB free at rest, 3.1 TB free on D:.

## Bake-off round 1 — COMPLETE (2026-11-06)

Ran on the owner's PC (lab persists at `D:\asset-forge-lab` for re-runs);
meshes fetched back and re-verified on the VM; scored with the Blender
scorer now committed at `benchmarks/pip/` (`score_render.py`,
`iou_sheet.py`, `scores.json`, `scores.md`).

- **Hunyuan3D-2 shape + paint — RIGGABLE (front IoU 0.84), the winner.**
  Split pair behaved exactly as designed (separate processes, VRAM
  released between). Paint peaked at 12,086 MiB (~200 MiB headroom) and
  its texturing phase is ~21 min CPU-bound — looks hung, isn't. Side
  profile is its weak view (IoU 0.27).
- **TRELLIS — MELTED as delivered:** inference fine, but the textured
  export's CUDA rasterizer won't build here; fallback vertex-color GLB
  is a blob (its 0.55 front IoU is a coverage artifact; the sheet
  overrules it, per protocol).
- **TripoSR — MELTED:** 39 s, but the same ruffle-blob failure as the
  CPU spike; no UVs.
- **Stable Fast 3D — BLOCKED:** gated HF repo; needs the owner to accept
  Stability's licence and supply a token. Not chased.

## P0 pipeline — BUILT AND PROVEN (2026-11-06)

The pipeline is implemented around the Hunyuan pair and ran end-to-end
on a second creature, the **Ember Dragon** (concept → cutout → shape →
paint → rig → animate → catalogued GLB):

- Code: `pipeline.py` (orchestrator), `gpu_bridge.py` (bridge dispatch,
  env-configured, GET-retry + job reattach), stage modules under
  `stages/` (prep cutout; mesh/texture PC scripts with the bake-off's
  exact parameters; rig template + Blender rigger; animate pose
  recipes ported from Drabbit Pet's pose driver; catalog metadata +
  cold re-import verifier with preview renders). CLI grew `run`,
  `cutout`, and `catalog-verify` commands. 23 unit tests at P0;
  28 after the skinning pass.
- Ember Dragon run (PC, RTX 3060): shape 334 s (peak 7,233 MiB;
  423,908 verts out), paint 909 s (peak 12,043 MiB — ~250 MiB headroom
  again; 657,672 verts textured), VRAM back at baseline after each
  stage. Rig: welded 395,731 → decimated 45,012 verts, 14 bones
  (arms in, ears out), idle (4.8 s) + hop (1.24 s) clips baked; final
  GLB 20.7 MB, sha256 pinned in `catalog/ember-dragon/metadata.json`
  and re-verified via `catalog-verify`.
- Skinning reality (at P0): Blender bone-heat yielded **zero** weights
  on these Hunyuan meshes (both Pip and the dragon), so the rig's
  deterministic distance-to-bone fallback did the skinning both times
  — coverage 1.0, hop renders clean. **Superseded the same day by the
  skinning-hardening pass below: heat weights now ship.**
- Incident, recovered honestly: the first pipeline process died on a
  transient bridge disconnect while polling the paint job. The job
  kept running server-side and finished; its outputs were adopted via
  the new reattach path, and the catalog provenance records the
  recovery. (The bridge job wrapper also reported that job "failed"
  while the stage's own result JSON records exit 0 — the stage
  artifacts and result JSON are the authority.)

## Skinning hardening — DONE (2026-11-06, branch game-asset-builder/skinning)

Diagnosed the P0 bone-heat failure with measurements, on both Hunyuan
meshes (dragon rig input / Pip stand-in):

- **Cause 1 — non-manifold geometry.** Raw Hunyuan paint output is a
  triangle soup (dragon: 438,098 boundary edges, 44,126 shells; Pip:
  558,648 / 50,258). The P0 weld repaired almost all of it, but the
  decimated rig inputs still carried 28 (dragon) / 135 (Pip)
  non-manifold edges, 20 / 106 non-manifold verts, and debris shells
  (7 / 153). Blender's heat solver needs a closed 2-manifold: it
  printed "Bone Heat Weighting: failed to find solution for one or
  more bones" and produced 0 weighted verts on both meshes.
- **Cause 2 — bones outside the mesh volume.** A controls-validated
  ray-parity test on the actual P0 rig found only **5 of 28** bone
  endpoints inside the dragon mesh: all wing endpoints float in air
  (Hunyuan folded the wings low; the template places spread-wing
  bones), the tail chain runs down the centreline while the model's
  tail curls sideways, the head endpoints sit outside the skull.
  Outside bones get no heat weights — and this, not the weighting
  math, is also why the P0 fallback's wingtip dominance measured 0.0.
- Ruled out: scale/units (height normalised to 2.0, signed volume
  consistent), flipped normals (0 inconsistent-orientation edges).

Fix shipped in `stages/rig/rig_blender.py` (+ pure policy module
`stages/rig/skin_policy.py`, +5 unit tests, suite 28/28):

1. `cleanup_geometry` after decimation: duplicate + degenerate faces
   out, debris shells (< 0.5% of the largest) out, over-connected
   edges resolved to their two largest faces, holes filled. Dragon:
   28 → 1 residual non-manifold edge (reported, heat tolerates it);
   Pip: 135 → 0.
2. `snap_bone_endpoints`: endpoints failing the inside test are moved
   to the nearest surface point pulled 1% of height inward (fallback:
   pulled toward the bone's other end). Dragon: 23 snapped, 0 failed.
   Pip: 22 snapped, `head.tail` unplaceable (heat still covered it).
3. Heat result is normalised, measured, and judged by
   `skin_policy.assess_heat` (coverage ≥ 0.98, every bone non-empty,
   wingtip dominance ≥ 0.5). Verts the heat field never reaches get
   distance weights for those verts only ("rescue", counted in the
   report). Full distance fallback remains for rejected heat results.

Ember Dragon re-rigged + re-animated + re-catalogued (GPU stages NOT
re-run; same textured.glb): **bone-heat weights**, coverage 1.0,
rescue on 6 verts, new GLB sha256 in the catalog metadata. Metrics
(old fallback → new heat): wingtip dominance **0.0 → 1.0**, tail zone
0.98 → 0.92, head zone 0.79 → 0.62 (heat shares the neck boundary
with the spine — anatomically reasonable), blended-vert share
99.6% → 87.5% and mean influences 3.84 → 3.00 (the fallback's higher
"blend" numbers are smear: it assigns every bone everywhere; zone
dominance is the correctness metric). Stress render
(`stages/catalog/stress_render.py`: one wing at 1.25 rad — twice the
hop's peak — head turned hard, tail curled hard) shows the raised
wing intact with no tearing or joint collapse. Known cosmetic limit,
pre-existing under the fallback too: a texture-seam streak down the
belly centreline that appears as deformation grows (faint at hop
apex, pronounced in the beyond-clip stress pose; absent at rest).

Pip through the shipped rigger (stand-in check): pure bone-heat,
coverage 1.0, wingtip 1.0, no rescue needed. Note the head-zone check
reads 0.0 for Pip by definition — with ears fitted, the ear bones
rightly dominate the top-central zone the check credits to "head".

## P1 templates + prop path — BUILT AND PROVEN (2026-11-06, branch game-asset-builder/p1-templates)

PR #37 (skinning) was merged by the owner; this branch starts from
main at `cc28756`. What landed:

- **Templates** (`stages/rig/template.py`): `quadruped()` — 15 bones
  (root; spine + hips splitting the body so front and rear pitch
  independently; neck, head; two-segment legs at four corners;
  tail.1–2) and `biped(ears=False)` — 11 bones, 13 with ears
  (vertical root/spine/head, two-segment arms and legs). Both are
  bbox-fraction layouts in the same parameterized system as
  `winged-creature`, and both run the unchanged skinning stack
  (cleanup → snap → bone heat → `skin_policy` acceptance). One
  measured design point: biped arm bones use a horizontal roll —
  probed in Blender, that makes local +X the symmetric raise axis;
  with the vertical roll no single axis raises a hanging arm.
- **Recipes** (`stages/animate/poses.py` + per-template driver
  tables in `animate_blender.py`): quadruped `idle` + `bounce`
  (two-hop bounce chosen over a walk cycle — a walk's footfall
  timing would be invented; the bounce's lift is measurable in a
  still: apex ground clearance vs rest); biped `idle` + `wave`
  (1.9 rad arm raise with a smoothstep hold envelope and a forearm
  wiggle). The winged recipes/drivers are byte-for-byte the P0
  behaviour (winged back-compat re-verified on the Ember Dragon).
- **Tip checks generalized**: the acceptance policy's extremities
  check is now labelled per template — wingtips (winged), feet
  (quadruped: lowest 10% of verts, leg-dominated), hands (biped:
  outer-low verts, same-side-arm dominated). Zone evidence is
  per-template too; the biped head zone now counts ear bones across
  the full head width (the inherited centre-strip definition
  under-reported by ~0.4 on the goblin — metric fix, not a rig
  change; the re-rigged GLB was byte-identical).
- **Prop path** (`stages/prop/prop_blender.py`, pipeline `--prop`
  mode): prep → mesh → texture → weld/decimate/cleanup → static
  GLB → catalog. No rig/animate stage runs; the catalog entry has
  empty bones/actions and provenance `rigged: false`,
  `weight_method: null`. `render_verify.py --static` proves the
  absence of an armature on cold re-import and refuses to pass a
  rigged file. The stage registry is unchanged — a prop run is a
  pipeline mode, not a fake stage.
- **Facing correction**: `rig_blender.py --rotate-z {0,90,180,270}`,
  plumbed through the pipeline/CLI and recorded in the rig report
  and catalog provenance. Implemented via `matrix_world` after the
  first implementation silently no-opped (glTF imports sit in
  quaternion rotation mode; `rotation_euler` writes are ignored —
  the bake-off scorer's lesson, second time it has bitten).

Proof assets (all numbers in `docs/TEST_PLAN.md`; catalog entries
sha-verified):

- **Triceratops** (quadruped): Hunyuan emitted the body SIDEWAYS
  (axis along X). First rig: heat shipped, coverage 1.0, head zone
  0.05 — the metric exposed the mismatch instead of hiding it.
  Re-rigged at rotate-z 90: coverage 1.0, feet 1.0, head zone
  0.9998, 45,001 verts, idle + bounce, stress pose clean.
- **Snow Goblin** (biped + ears): messiest rig input yet (137
  non-manifold edges, 58 shells); heat shipped, coverage 1.0,
  hands 1.0, 49,080 verts, idle + wave. Known cosmetic limit: the
  fused-fur ruff is partly arm-weighted — the shipped wave reads
  fine; a 2.2 rad stress raise drags a visible fur sail. No
  tearing. Mitigation (weight-distance veto) is future work.
  **Superseded the same day by the P1.1 fix below** — the owner
  flagged the shipped wave itself (body texture stretching with
  the arm), and the goblin was re-rigged with the veto.
- **Treasure Chest** (prop): 27,041 verts from a 1.08M-vert
  textured mesh, static verify clean (0 bones/groups/actions),
  renders match the concept.

Incidents: the bridge's exec-job tracking ends at ~15 min on long
jobs (observed on the goblin and chest paint stages; the P0 paint
disconnect fits the same pattern). The PC-side processes were
unharmed both times and finished; their outputs were adopted from
the lab (stage_runner result JSON is the authority) and the
manifests/catalogues carry the true adopted records — a resume
pass initially overwrote the mesh-stage records with
`{"resumed": true}` placeholders, which were restored from the
PC-side result files before cataloguing. Suite: 44/44.

## P1.1 weight-distance veto — BUILT AND PROVEN (2026-11-06, same branch)

Owner verdict on the shipped goblin wave: "the body texture
stretched with the arm." Correct — bone heat had diffused through
the fused fur mass until 0.51 of the torso zone's total weight sat
on the arm bones (the ruff band measured 0.61). The fix is a general
skinning-stack step, not a goblin special case:

- `skin_policy.apply_veto` (pure, unit-tested): after heat, a
  non-trunk bone keeps a vertex's weight only within its reach
  radius — max(factor × bone length, floor × mesh height), shipped
  defaults factor 0.85, floor 0.19. Vetoed weight renormalizes onto
  the survivors. The root→head trunk chain (`template.trunk_chain`)
  is exempt: its segments run through the mass they own, so distance
  measures body radius there, not bleed. A vertex left weightless is
  rescued onto its nearest eligible bone — a vetoing bone is
  eligible again only for flesh projecting past its segment
  endpoints (fingertips, ear tips, toes), so the armpit web rescues
  onto the trunk instead of back onto the arm.
- `skin_policy.assess_zone_share` gates the result: torso-zone arm
  share must be ≤ 0.25 (unvetoed goblin: 0.51 — the check would
  have caught the defect at P1 time).
- The radius was tuned by measurement, not taste: on this mesh the
  arm's own flesh sits 0.34 (median) from its segment while torso
  bleed sits at 0.51, and the distributions overlap — tighter
  (0.7/0.16: torso share 0.065) hollowed the arm into a stretched
  fin in the wave render; looser (1.0/0.16) kept the arm whole but
  left the ruff at 0.56. The shipped point (0.85/0.19) is the
  measured compromise; renders were the judge (iterations kept
  under `outputs/snow-goblin/before-veto/`).

Re-proof (goblin only, from the saved textured.glb; mesh/texture
stages NOT re-run; Ember Dragon, Triceratops and Treasure Chest
untouched, catalogue-verified byte-identical):

- torso arm share 0.506 → **0.139**; ruff-band share 0.614 → 0.448
- coverage 1.0; hands (tip) dominance 1.0 → 0.997; head zone
  0.667 → **0.787**; feet zone 0.904 (unchanged); every bone
  populated (arm.L 24,162 → 6,967 weighted verts)
- new GLB sha256 `86c91cd6…` (catalogue re-verified); suite 57/57
- Visual verdict on the new renders: at the wave's 1.9 rad peak the
  chest and ruff stay with the body and the raised paw reads as a
  paw — the flagged defect is gone. Residual, stated plainly: a
  taut fur sheet still stretches in the armpit web at full raise
  (arm and torso are one fused fur mass; some web must stretch),
  and the 2.2 rad stress pose — beyond the shipped clip — still
  sails the flank, as it did before the veto. Euclidean distance
  cannot fully separate flesh from bleed on a near-spherical fur
  character; a geodesic-weight cleanup would be the next step if
  the owner wants the stress pose clean too.

Next:
1. Owner decisions outstanding: merge of this P1/PR #38 (draft,
   against main — now includes the P1.1 veto commits); whether to
   unblock Stable Fast 3D (owner-side HF action, only if wanted).
2. P2 when directed: a simple local UI over the catalog and
   pipeline. Possible further hardening if wanted: a bridge-client
   adoption path for >15 min stages instead of the manual recovery
   used here.

## P2 cleanup slice — BUILT AND PROVEN (2026-11-06, branch game-asset-builder/p2-cleanup, stacked on PR #38)

Owner commissioned all three layers (time/GPU explicitly not a
constraint). Full numbers in TEST_PLAN's P2 section; design notes
in `skin_policy.py` / `rig_blender.py` docstrings.

- **Layer 1 — pose spec + preflight.** Spec in DESIGN.md
  (per body plan; quadrupeds get their own spec — standing
  square, legs separated, belly clear — since A/T poses don't
  fix them). `stages/prep/preflight.py` runs in the pipeline for
  rigged runs and records a pass/warn in the manifest. To-spec
  giraffe concept passes; the original goblin concept warns
  (arm-daylight 0.009).
- **Layer 2 — geodesic veto.** Veto reach = max(Euclidean,
  graph-geodesic) (`stages/rig/geodesic.py`, Dijkstra over the
  edge graph; ~2 s build at 50k verts). Geodesic alone REJECTED
  by measurement (goblin gate failure at 0.268). Beyond-tail
  exemption for distal flesh; both-ends exemption measured and
  rejected (ruff). Side finding: the P1.1 belly guard zone had
  never run on a quadruped and misfired on leg centrelines —
  redrawn between the leg columns, threshold unchanged.
- **Layer 3 — segmentation.** Bake-off
  (`benchmarks/segmentation/scores.md`): P3-SAM adopted
  (licence-clean in Canada; goblin CLEAN, triceratops ROUGH);
  PartField better but NVIDIA-non-commercial — rejected for
  adoption, research cross-check only; SAMesh not run per the
  bake-off's gating. New `segment` stage between texture and
  rig: VM proxy with the bake-off's exact recipe (recipe is
  load-bearing — a rig-frame variant collapsed the triceratops
  to one part), P3-SAM in its own PC venv/process (peak
  9.8 GB, VRAM verified back to baseline), labels via nearest
  face centroid under the recorded canonical transform,
  geometry separation at part boundaries (split verts are the
  seam caps), then label-aware skinning: plurality label→bone
  map; only foreign-part dominants can be forbidden, and only
  on non-boundary or beyond-reach pairs.
- **Re-proofs** (saved textured meshes; priors preserved under
  `outputs/<slug>/before-cleanup/`): goblin 9 parts, torso
  share 0.139 → **0.079**, head 0.787 → 0.881, feet 0.831,
  hands 0.778 (label-veto cost, disclosed), stress sail
  materially reduced (front) / reduced (three-quarter) —
  residual is the arm part's own web fin at 2.2 rad. Trike
  5 parts (2 of 4 legs separate — P3-SAM's known weakness),
  feet/head 1.0, belly 0.200. Dragon/Chest byte-identical.
  Suite 79/79.

Next:
1. Owner decisions: merge PR #38, then this slice's PR (stacked
   draft); the UI slice (old P2) and engine hand-offs (P3) are
   still pending direction.
2. Known follow-ups if wanted: P3-SAM leg re-prompting for
   quadrupeds (interactive point-prompt mode exists upstream);
   hands-dominance cost of fine arm labels (0.78) could be
   revisited if a future asset's hands matter more.

## P2 local UI — BUILT AND VM-VERIFIED (2026-11-07, branch game-asset-builder/p2-ui, stacked on p2-cleanup)

Owner approved starting P2 (and P3) on 2026-11-07. Scope per the
README slice list: "a simple local UI over the catalog and
pipeline." Built stdlib-only, matching the CLI's discipline:

- `ui/catalog_data.py` — the data layer: catalog summaries (the
  rigged flag reads `provenance.rigged`, falling back to the bone
  list for the P0 ember-dragon entry, which predates the flag),
  full entry detail with a live sha256 verification (the catalog
  module's own `verify_entry`), the stage registry as data, the
  doctor report as data, and a traversal-guarded preview path
  (bare `*.png` basenames inside `outputs/<slug>/renders/` only).
- `ui/runs.py` — run management: validates a run request into the
  exact CLI argv (invalid specs raise before anything spawns) and
  tracks the spawned `asset_builder.py run` subprocess in memory
  (state, exit code, output tail). The durable record stays the
  pipeline's own manifest + catalog entry, as with a CLI run. The
  subprocess inherits the server's environment, which is how the
  bridge token reaches the GPU stages.
- `ui/server.py` + `ui/index.html` — ThreadingHTTPServer on
  127.0.0.1:8770 (flags on the new `asset_builder.py ui` command):
  catalog cards with preview renders and per-asset sha256 verify,
  stages table, doctor line, run form, run status polling. No
  auth — localhost-only local tool; do not rebind it outward.
- Verified (VM): suite 92/92 (13 new tests); live smoke served
  the real catalog and returned sha256 MATCH for the ember
  dragon through the API. NOT done: an end-to-end pipeline run
  launched from the browser (the spawn path is the proven CLI
  verbatim; only its validation/tracking is new-tested).

## P3 engine hand-offs — BUILT AND PLAYBACK-PROVEN (2026-11-07, branch game-asset-builder/p3-handoff, stacked on p2-ui)

Owner approved P3 alongside P2 on 2026-11-07. Scope per the README
slice list ("hand-off integrations — animation studio library,
Godot projects") plus the TEST_PLAN's standing gap (Godot/three.js
playback of the baked clips).

- **Exporters** (`handoff/export.py`, CLI `export-godot /
  export-threejs / export-studio`): load the catalog entry and
  REFUSE the export unless the local GLB verifies against it
  (sha256 + size), then re-verify the copy. Godot package: GLB +
  wrapper .tscn (instances the GLB at `res://assets/<slug>/`) +
  catalog record + README + manifest. three.js package: GLB +
  asset.json + GLTFLoader/AnimationMixer snippet + README +
  manifest. Studio package: GLB under the asset root's
  `assets/characters|props/` + a record merged into
  `game-asset-builder-catalog.json` in the studio's schema-1.0.0
  intake format — always `status: "candidate"`, `rig_id` = the GAB
  template (never `studio_humanoid_v1`; these are not that rig),
  license `proprietary` (owner-generated).
- **Playback verification (owner's PC, via the bridge)** — the
  long-standing gap is CLOSED for all four catalogued assets:
  Godot 4.7.2 headless (scratch project from `handoff/godot/`,
  import exit 0; `GODOT_VERIFY_DONE ok=true`): bone sets equal
  the catalog's, every clip found with length > 0 and real
  skeleton motion (global-pose deltas: dragon hop 0.085 / idle
  0.0062, goblin wave 1.69 / idle 0.035, trike bounce 0.096 /
  idle 0.156; chest static-verified). three.js 0.180 in Chrome
  headless under SwiftShader (`THREE_VERIFY_DONE ok=true`):
  same bone counts, same clips, durations identical to Godot's,
  world-space bone deltas dragon hop 0.074, goblin wave 0.70,
  trike bounce 0.030, chest static. PC scratch persists at
  `D:\asset-forge-lab\handoff-verify\`; no stray processes left.
- Harness lessons (in `handoff/README.md`): Godot `find_child`
  matches names, not types — walk by `is_class`; three ≥ 0.170
  needs `three.core.js` beside `three.module.js`; Chrome
  `--dump-dom` snapshots mid-load — the three.js driver polls
  the result element over the DevTools protocol instead.
- Studio scope honesty: the export was produced and
  schema-validated (real `asset.schema.json`, jsonschema, all
  four VALID) against a SCRATCH asset root. Writing into the
  studio's live store (`~/workspace/ai-animation-studio-assets`)
  and running its register/promote flow were deliberately NOT
  done from this project — that's the studio side's gated step,
  and the export command makes it a one-liner when wanted.
- Not verified: rendered pixels in either engine (both checks
  sample poses, not frames), the Godot editor GUI path, any
  shipped-game integration.

## P4 game animations — BUILT AND VERIFIED (2026-11-08, branch game-asset-builder/p4-game-animations, stacked on p3-handoff)

Owner directed game-ready animation production (walking + any
animation a game needs) on 2026-11-08. Scope landed: the standard
locomotion set — `walk` + `run` for all three rig templates —
from a parametric gait model in `stages/animate/poses.py` (P4
section; model + phase patterns in `docs/DESIGN.md` "Locomotion
(P4)"). The animate stage bakes them like every other recipe; no
new stage, no new meshes, no GPU work, no re-rigging.

- Drivers added (axis-probed on the shipped rigs, numbers in
  `animate_blender.py`'s header): legs on all templates
  (winged/biped had none), biped knee fold, biped fore-aft arm
  swing on local Z with mirrored per-side signs, winged arm
  counter-swing. Quadruped needed no driver changes.
- The three catalogued creatures were re-animated in place from
  `outputs/<slug>/rigged.glb`; previous finals kept under
  `outputs/<slug>/before-p4/`. Each now carries 4 clips (new:
  dragon walk 1.5 s / run 1.0 s; goblin walk 1.5 / run 1.0;
  triceratops walk 2.0 / run 1.0). Catalog entries updated:
  `actions`, a new per-clip `clips` duration map, sha256/bytes,
  and `provenance.animation_revision`; catalog-verify MATCH ×3.
  `handoff/threejs/run_verify.mjs` clip lists updated to match.
- Suite **113/113** (pytest; +12 in
  `tests/test_game_animations.py` — gait invariants, loop
  closure, phase patterns, fold timing, GLB clip presence /
  durations via the new stdlib reader
  `stages/animate/glb_clips.py`, hermetic synthetic-GLB test for
  the reader itself).
- three.js playback of the new clips VERIFIED on the build VM
  (Electron Chromium + SwiftShader driving the project's
  verify.html; per-clip numbers in `docs/TEST_PLAN.md`). The
  mid-cycle sampling blind spot for anti-phase gaits was found
  and documented there; quarter-cycle deltas are the meaningful
  figures for walk/run.
- Ground/intersection checks: evaluated-mesh min-Z across each
  walk stays within 0.007 units of rest (no material
  penetration); swing-peak Cycles stills read as a mid-stride
  on goblin + triceratops, a shuffle-step on the dragon (seated
  body plan, single-segment legs — its honest limit).
- NOT done / not verified: Godot playback of the new clips
  (P3's Godot proof predates them), rendered engine pixels, a
  `turn`/`jump`/`attack` set beyond locomotion (the model
  extends by adding recipes — no blocker, just not this slice),
  PC-side re-export of the hand-off packages (the catalog GLBs
  changed, so P3's exported packages are stale until re-run).

Next:
1. Owner decisions: merges of PR #38, the p2-cleanup PR, the P2
   UI PR, the P3 PR, and this slice's PR are the owner's call.
2. Possible follow-ups if wanted: a rendered-frame engine check
   (Godot viewport capture / three.js screenshot) to cover the
   seam-under-rendering question; running the studio hand-off
   into the live store.

Boundaries: no cloud fallback exists or may be added; weights and outputs
never enter git; GPU claims only from PC runs; merges are the owner's call.

## P5 campfire creatures — COMPLETE, 6 of 8 (2026-11-09, branch game-asset-builder/p5-campfire-creatures, stacked on P4) — 7 of 8 after the 2026-11-10 Mandrake finish (see the last section)

Owner commissioned eight "weird smashup" creatures for the
campfire wallpaper (2026-11-08): batch 1 = Moth-Hart, Toasty,
Lantern Snail; batch 2 = Ember Owl-Cat, Geode Tortoise,
Axolotl-Capybara, Mandrake Toddler, Crow Postman. Reference art for
all eight exists in `~/workspace/creature-refs/` (batch 2's five
were generated 2026-11-09 in the same recipe).

- **Infrastructure (commit `d81bb38`)**: `winged-quadruped` and
  `snail` rig templates, the SIGNATURES registry (fan / headturn /
  bounce / scream / bow / shiver / wiggle; the snail's showcase is
  its built-in `retract`), the snail emissive-shell material note
  in the catalog step, and the session-0 bridge transport
  (PowerShell jobs as .ps1 files via cmd jobs). P5 test module:
  21 tests.
- **Moth-Hart — BUILT AND VERIFIED.** Winged-quadruped + `--ears`,
  signature `fan`. Mesh exit 0 (334.11 s; 318,606 verts raw),
  texture exit 0 (runner 1,330.41 s; textured 487,742 verts; peak
  VRAM 11,870 MiB), segment exit 0 (136.74 s; 12 P3-SAM parts),
  rig 21 bones with bone-heat + geodesic veto + label-aware veto
  (25,087 entries vetoed; distance rescue on 2,759 verts). Clips:
  idle 4.79 s, fan 2.79 s, walk 2.0 s, run 1.0 s. Catalogued
  45,637 verts / 89,496 faces, GLB 20,692,592 bytes, sha256
  `0616e52aaeed63ba…`, catalog-verify **MATCH**. three.js playback
  verified on the build VM (Chrome headless shell + SwiftShader,
  the project harness page): ok=true, 21 bones; quarter-cycle
  deltas fan 0.666 / run 0.308 / walk 0.170 / idle 0.030. Rest +
  fan renders read clean — four distinct legs despite the
  preflight "warn" (leg band fuses in the concept's erosion test;
  segmentation + separation handled it). Verdict: **RIGGABLE**.
- **The bridge route was rebuilt the same day** (wrapper +
  tailnet proxy on port 3130; the earlier "blocked" note in this
  section's first draft was superseded within hours) and the
  remaining seven were run single-flight under a strict sweep-
  before-every-run rule. Results:
- **Toasty — BUILT AND VERIFIED.** Biped, signature `bounce`.
  Mesh exit 0 (332.32 s; 498,688 raw verts), texture exit 0
  (runner 1,573.17 s; 762,980 verts / 997,542 faces; peak VRAM
  12,045 MiB), segment exit 0 (219.01 s; 7 parts). Rig 11 bones,
  coverage 1.0; torso arm share 0.104, head zone 0.998, hands tip
  0.803, feet zone 0.390 (weak — disclosed; the fused skirt base
  gives the feet little distinct mass). Clips: bounce 1.25 s,
  idle 4.79 s, walk 1.5 s, run 1.0 s. GLB 21,960,832 bytes,
  sha256 `62289b927b6c161b…`, catalog-verify **MATCH**. three.js
  ok=true; quarter-cycle deltas bounce 0.270 / run 0.183 / walk
  0.152 / idle 0.009. Renders read clean; the bounce-peak frame
  splays the fused bottom rim (fused-mass class) and a mid-body
  texture seam is visible. Verdict: **RIGGABLE**.
- **Lantern Snail — BUILT AND VERIFIED.** Snail template, no
  `--signature` (built-in `retract` showcase; the catalog
  `material_notes` carry the emissive-shell note). Mesh exit 0
  (353.37 s; 769,509 verts / 988,234 faces), texture exit 0
  (runner 948.83 s). Rig 9 bones (root, body.1–3, neck, head,
  eye.L, eye.R, shell), coverage 1.0; head tip 0.959, shell zone
  0.747, distance rescue 3,351. Clips: glide 3.0 s, idle 4.79 s,
  retract 3.21 s. GLB 21,410,520 bytes, sha256 `240dbfafbdfded…`,
  catalog-verify **MATCH**. three.js ok=true; mid-cycle deltas
  glide 0.456 / retract 0.264 / idle 0.009. Disclosed: the
  retract pose dips the evaluated mesh to −0.024 (0.035 below
  the ground plane) and the head/face reads blobby in renders.
  Verdict: **RIGGABLE**.
- **Axolotl-Capybara — BUILT AND VERIFIED.** Quadruped,
  signature `wiggle`. Mesh exit 0 (295.48 s; 548,677 verts /
  691,694 faces), texture exit 0 (763.33 s) — the only run of
  the pack whose pipeline client survived end to end, so its
  manifest is untouched. Rig 15 bones (incl. tail pair),
  coverage 1.0; feet tip 0.865, head zone 0.658, tail zone
  0.389 (the thin tail fin — disclosed), label veto 14,755.
  Clips: idle 4.79 s, walk 2.0 s, run 1.0 s, wiggle 2.42 s.
  GLB 19,525,868 bytes, sha256 `7658b7db08dec3…`, catalog-verify
  **MATCH**. three.js ok=true; quarter deltas run 0.321 / walk
  0.194 / wiggle 0.158 / idle 0.020. Renders excellent — the
  axolotl gills and capybara body both read. Verdict:
  **RIGGABLE**.
- **Geode Tortoise — BUILT AND VERIFIED.** Quadruped, signature
  `shiver`. The pack's hardest build (full saga in
  `outputs/geode-tortoise/attempt1-texture-note.txt`): mesh
  sample 1 was adopted across a VM reboot; its texture attempt
  was killed on a memory criterion later disproved; the retry's
  mesh came back at **1,643,448 faces** and, under corrected
  criteria, its texture **completed** — runner exit 0,
  2,523.98 s (texture_s 2,399.67 s; 1,279,034 textured verts),
  peak VRAM 12,032 MiB, the longest legitimate paint in project
  history. Rig 15 bones, coverage 1.0; feet tip 1.0, head zone
  0.775, tail zone 0.231 (stub tail / shell rear), label veto
  14,732. Clips: idle 4.79 s, walk 2.0 s, run 1.0 s, shiver
  1.58 s. GLB 21,575,096 bytes, sha256 `0475366d287cbaa7…`,
  catalog-verify **MATCH**. three.js ok=true; mid walk 0.374 /
  run 0.103 / shiver 0.039 / idle 0.034. Renders: stone shell
  with the amethyst geode cluster — reads exactly as the
  concept. Verdict: **RIGGABLE**.
- **Crow Postman — BUILT AND VERIFIED.** Biped, signature
  `bow`. Mesh exit 0 (314.45 s; 341,956 verts / 684,162 faces),
  texture exit 0 (runner 1,230.4 s; texture_s 1,092.48 s;
  534,328 verts), peak VRAM 11,996 MiB. Rig 11 bones, coverage
  1.0; hands tip 0.886, head zone 0.937, feet zone 0.807 —
  **but** the bone-heat weights were rejected by the skin
  policy and the rig ships the distance-to-bone fallback;
  torso arm share is 0.60, so coat mass follows the arm bones
  (acceptable here: the concept's arms are coat sleeves fused
  to the torso, and the bow render is clean — disclosed as a
  quality limit). Clips: bow 2.58 s, idle 4.79 s, walk 1.5 s,
  run 1.0 s. GLB 21,106,560 bytes, sha256 `310942604e8623…`,
  catalog-verify **MATCH**. three.js ok=true; quarter deltas
  bow 0.189 / run 0.175 / walk 0.142 / idle 0.009. Renders are
  dark (black plumage, navy coat) but unmistakable. Verdict:
  **RIGGABLE** (fallback weights disclosed).
- **Ember Owl-Cat — FAILED at the texture stage, NOT
  catalogued.** Winged-creature + `--ears`, signature
  `headturn`. Two attempts, both mesh exit 0 (328.12 s /
  646,434 verts; 338.44 s / 703,035 verts). Attempt 1's paint
  grew private memory 14.9 → 17.5 GB **without plateauing**
  and was killed at 2h33m wall / 8,797 CPU-s — 5× the longest
  completed paint. Attempt 2 showed the same growth signature
  and was killed at ~60 min (17,565 MB). A postscript in its
  note records that the memory LEVEL alone was later disproved
  as a kill criterion; the verdict rests on duration +
  unbounded growth. Full record:
  `outputs/ember-owl-cat/attempt1-texture-note.txt`.
- **Mandrake Toddler — FAILED at the texture stage, NOT
  catalogued.** Biped, signature `scream`. Attempt 1: mesh
  exit 0 (321.65 s; 338,370 verts / 676,636 faces); its
  texture was killed by the operator at 701.92 s at private
  17,228 MB — a level the tortoise later completed at, so the
  kill is recorded in its note as an operator error on a
  since-disproved criterion. Attempt 2 (the one retry): mesh
  exit 0 (319.34 s; 355,463 verts / 710,866 faces); under
  corrected criteria the paint **died on its own** mid-bake —
  the stage log ends immediately after the input-mesh line,
  no traceback, no result file, no textured GLB. Root cause
  unproven. Full record:
  `outputs/mandrake-toddler/attempt1-texture-note.txt`.
- **The paint-memory finding (the pack's main operational
  result):** completed paints (runner seconds) — Axolotl-
  Capybara 763.33, Lantern Snail 948.83, Crow Postman 1,230.4,
  Toasty 1,573.17, Geode Tortoise 2,523.98. The bake phase's
  private-memory footprint (~11.6 GB early) rises to a
  **byte-stable plateau of ~17.2–17.7 GB** on large meshes:
  that plateau is the bake's fixed pool, NOT a runaway. The
  true runaway discriminator is unbounded growth + duration
  many times the envelope (the Owl-Cat). Corrected kill
  criteria: free RAM < 5 GB, private > 26 GB, or extreme
  duration with continued growth. Face count alone does not
  predict failure: the Mandrake died at 676,636 faces while
  the Axolotl-Capybara completed at 691,698 the same night
  and the Tortoise at 1,643,448.
- **Bookkeeping repairs, recorded per-creature in each
  manifest's `stage_record_note`**: the pattern repeated all
  pack — a `--resume` relaunch overwrites the manifest's
  detailed records of stages it skips, and the pipeline client
  typically dies at the post-stage fetch (bridge job-tracking
  limit, ~15–23 min into a long stage) while the stage itself
  completes unharmed on the PC. The standing recovery is:
  wait for the stage's own result file, fetch result + GLB +
  log (sha256-verified by the bridge download), `--resume`,
  then restore the genuine mesh/texture records into the
  manifest from the stages' own outputs. Applied to Toasty,
  Lantern Snail, Geode Tortoise (×4 attempts) and Crow
  Postman; the Moth-Hart instance is the one originally
  documented here (including a stale exit-1 result read and a
  reconstructed segment record — runner exit 0 / 136.74 s,
  read live pre-reboot; its on-disk outputs are the
  originals). Axolotl-Capybara needed no repair.
- **Operational lessons (hard-won, 2026-11-08/09)**: (1) a
  pipeline client that dies after dispatching a GPU stage leaves
  the stage RUNNING server-side — check the agent's job/process
  list before re-dispatching, or two paint stages will share one
  GPU and exhaust the PC's RAM (observed: 0.5 GB free of 32 GB;
  both trees had to be taskkilled). Single-flight is mandatory:
  sweep the PC (compute-apps + process list) before EVERY run.
  (2) Bridge file reads can return a stale record for minutes after a stage writes its
  result — when a stage reports failure, re-fetch its result +
  log before re-running anything; the reads self-heal. (3) VM
  reboots wipe /tmp and kill in-flight clients (three this pack)
  — keep run scripts/logs and lane tooling in the workspace,
  and prefer `--resume` + manifest checks over blind relaunches.
  (4) Judge a paint by growth + duration, never by memory level
  alone (see the paint-memory finding above).
- Suite **134/134** (the UI catalog test now expects the ten
  proven assets — the original five plus toasty, lantern-snail,
  axolotl-capybara, geode-tortoise and crow-postman, with bone
  counts 11 / 9 / 15 / 15 / 11).

P5 is closed: six creatures catalogued + verified, two failures
catalogued honestly, draft PR opened against
`game-asset-builder/p4-game-animations` (not merged — the
owner's call). Still open beyond P5: Godot playback of the six
new GLBs (three.js only so far), campfire-wallpaper roster
integration of the pack (a separate step), and the
Owl-Cat/Mandrake paint root cause (unproven; face count
excluded as the sole cause).

## Environment proof: pine tree — SHAPE PROVEN, PAINT OPEN (2026-11-09, branch game-asset-builder/env-pine-proof, stacked on P5)

Commissioned as a one-asset proof for "can the builder furnish the
campfire wallpaper's environment, not just its creatures?" — one
stylized pine through the prop path (`--prop --prop-target-verts
5000`) from a generated concept.

What is proven:
- The Hunyuan SHAPE stage handles foliage subjects: 243,514 verts /
  487,126 faces in 476.53 s on the owner's PC (peak VRAM 9,209 MiB),
  a single welded mesh in 13 components (one 242k-vert shell plus
  small debris) whose clay renders read unmistakably as the concept
  pine — tall trunk, pointed leader, bottom-heavy clustered canopy.
- The prop finish (weld/decimate/cleanup) takes the painted mesh to
  4,961 verts / 9,940 faces, and `catalog-verify` MATCHES the
  catalogued `pine-tree` entry (catalogue carries the entry; the
  run manifest records each stage).
- The catalogued GLB loads and renders in the campfire wallpaper's
  own vendored three.js stack (GLTFLoader, ACES tone mapping,
  shadow-casting) at scene scale next to the treasure chest — see
  TEST_PLAN. Vertex colours carry the paint (no UV map).

What is NOT proven / failed honestly:
- The Hunyuan PAINT stage produced no result on this asset.
  Attempt 1 (full-res shape) ran 10,801 s at a flat ~12 GB VRAM /
  100% GPU plateau and was killed at an owner-approved cap; its
  wrapper then recorded exit 1. Attempt 2 was invalidated by an
  operator error (below) and killed at 3,243 s. Attempt 3 — on
  the corrected, verified-welded 80k-face mesh — ran 7,728.62 s
  at the same flat ~12 GB VRAM plateau, produced no textured
  output, and was killed at the 23:30 hard deadline the same
  night (result archived, exit 1). The failure is therefore NOT
  explained by mesh weight or by the export defect: the same
  stage stalled on a 487k-face input and on a clean 80k-face
  input alike. Root cause for the
  stalls is UNPROVEN — same open category as the Owl-Cat/Mandrake
  texture failures; the subject's thin, high-surface-area foliage
  geometry is the standing suspicion, not a finding.
- Operator error, recorded plainly: the attempt-2 input was
  decimated in Blender and exported WITHOUT clearing the mesh's
  custom split normals, so the GLB exporter split every vertex —
  the "80k-face" file was 79,999 disconnected triangles (239,371
  verts, ~79,686 components), a worse paint input than the
  original. The corrected decimation (split normals cleared, smooth
  shading) verifies in-file at 39,956 verts / 120,000 edges /
  79,999 faces / the same 13 components. Any future pre-paint
  decimation MUST clear split normals before export and re-verify
  component counts in the exported file.
- The catalogued pine's paint is therefore PROCEDURAL, not Hunyuan:
  per-vertex colours computed in Blender (height-graded greens,
  fbm cluster patchiness + needle noise, interior/underside
  shading, tapered trunk mask with streaked bark; palette v2
  deepened after v1 rendered pale under AgX). The catalogue
  provenance and the run manifest say so explicitly; the pipeline's
  default provenance text was corrected by hand where it would
  otherwise have credited the paint model. Treat this asset as
  "builder-shaped, hand-painted" — it proves the environment SHAPE
  pipeline end-to-end and keeps the paint question open.
- Full-scene wallpaper A/B (builder pines swapped into the live
  scene) is NOT yet demonstrated: the verification harness
  screenshots on creature-ready, and static GLB loads (the
  builder pines AND the pre-existing treasure chest, on the
  unmodified baseline build too) race that screenshot and usually
  lose. The three.js mini-scene proof above is the current
  evidence; a roster-style gated load or a harness settle-wait is
  the fix when the full environment pack is attempted.

## Environment pack — COMPLETE (2026-11-10, branch game-asset-builder/env-pack, stacked on env-pine-proof)

- Owner's directive (2026-11-10): after the paint investigation was
  stopped, build the full environment pack with procedural paint; fix
  Hunyuan paint later. The investigation's findings are summarised in
  `docs/PAINT_STALL.md`.
- **Catalogued (all sha256-verified, suite 134/134): pine-tree (from
  the proof) + boulder, bush, fern, mushroom-cluster, fallen-log,
  stump** — every one builder-shaped (Hunyuan3D-2 dit-v2-0 on the
  owner's PC) and procedurally vertex-colour painted in Blender.
  Per-asset Cycles renders were inspected: boulder (deepened grey +
  moss palette v2 after v1 washed out), bush (layered leaf clusters),
  fern (chunky arching fronds), mushroom-cluster (full teal caps via
  an edge-relaxed normal/height field — a plain normal mask only
  dusted the cap tops), fallen log + stump (deepened bark, moss,
  pale ringed tops).
- Production route per asset (the pack pattern): full pipeline run
  for prep+mesh; the texture stage is then killed on the PC (it
  stalls per PAINT_STALL.md) and the client stopped; paint runs via
  `tools/paint_env.py` (decimate to ~45k in Blender, weld, clear
  split normals, smooth shading, per-asset palette — flat shading was
  rejected because the glTF exporter splits verts for it); finish
  with `--resume`; restore truthful provenance with
  `tools/fix_provenance.py` (the resume overwrites run-1 manifest
  records with placeholders and the catalog would otherwise credit
  Hunyuan paint — mesh records are restored from the lab stage
  result + log). The painter's own export is re-imported and
  verified (verts/components/Color attribute) before the finish.
- Not verified: Godot playback of the pack GLBs (three.js/Cycles
  only); wallpaper integration is a separate step (the pack was
  built for the campfire scene; the pine section's harness
  gated-load caveat still applies there).

## Mandrake Toddler — FINISHED (2026-11-10, branch game-asset-builder/mandrake-finish, stacked on env-pack)

The P5 verdict for Mandrake was corrected on 2026-11-10 (see
`docs/PAINT_STALL.md` and `outputs/mandrake-toddler/CORRECTION-2026-11-10.md`):
its retry paint had actually succeeded (967.81 s, exit 0) and the
textured GLB was recovered from the lab. At the owner's direction
the remaining stages then ran from that file (`--resume`, biped,
signature `scream`): segment (P3-SAM) → rig → animate → catalog,
380 s total. Result: **catalogued, catalog-verify sha256 MATCH**;
11-bone biped rig with bone-heat weights (coverage 1.0; head
dominance 0.98, hands 0.92, feet 0.92 — no distance fallback);
clips idle / walk / run / `scream`. Rest and scream renders
inspected — a grumpy purple-white mandrake with green sprout
hair; the scream pose deforms its papery shell skirt, disclosed
as-is. The P5 pack now stands at **7 of 8 catalogued**; only the
Ember Owl-Cat remains unfinished (its paint failure is genuine —
same VAE stall as the pine, see PAINT_STALL.md). Mandrake also
joined the campfire wallpaper roster the same day (wallpaper
project records). Suite: 134 passed (catalog-set test updated).


## Paint stall — FIXED; Ember Owl-Cat — FINISHED (2026-11-10, branch game-asset-builder/mandrake-finish)

The Hunyuan paint stall (this doc's open item since the pine) is
resolved; full write-up in `docs/PAINT_STALL.md`. Controlled probes
on the owner's PC isolated it: the standalone VAE encodes batch-6
fine and batch-1 through the full pipeline is fine (3.67 s), but
batch-6 inside the full resident pipeline never returns from the
VAE encoder's first down-block convolution. Setting
`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` cures it
(batch-6 encode 2.63 s) — a CUDA caching-allocator pathology, not
the VAE math and not cuDNN benchmarking (benchmark mode was
slower). `stages/texture/hunyuan_paint.py` now sets that variable
via `setdefault` at import, before CUDA initializes; an
operator-provided value is respected.

Proof is the production stage itself: the **Ember Owl-Cat** — the
creature whose paint genuinely stalled on two attempts — ran its
texture stage to exit 0 (loaded 104.5 s; texturing 6,202.2 s on
the 1,405,816-face mesh; peak VRAM 11,910 MiB, released after
exit). Two VM-side client deaths during adoption (runtime
restarts; the PC-side stage was unharmed both times) were worked
through with the standing recovery: the textured GLB was fetched
from the lab and verified in Blender (1,092,321 verts, UVMap,
2048² texture), then a `--resume` run completed segment (P3-SAM)
→ rig → animate → catalog. Result: **catalogued, catalog-verify
sha256 MATCH** (`f5a642353fa8…`); winged-creature rig, 14 bones
(root/spine/head/wing.L/wing2.L/wing.R/wing2.R/arm.L/arm.R/leg.L/
leg.R/tail.1–3); weights are the distance-to-bone fallback
(bone-heat rejected by skin policy — same disclosed situation as
the Crow Postman), coverage 1.0; clips idle / walk / run /
`headturn`. Rest and headturn renders inspected: a plump ember
owl-cat with ear tufts, a glowing heart marking on its chest,
folded feathered wings and a long curled tail — reads exactly as
commissioned. **The P5 pack is complete: 8 of 8 catalogued.** The
Owl-Cat also joined the campfire wallpaper roster the same day
(wallpaper project records). Suite: 134 passed (catalog-set test
updated with the owl-cat at 14 bones). Still not verified: Godot
playback of the owl-cat GLB (three.js/Cycles only).


## Headturn rework (2026-11-10, branch game-asset-builder/mandrake-finish)

The owner looked at the Owl-Cat's signature render and called it
"a tilt more than a turn" — fair: 0.55 rad of sine yaw, smeared
by the distance-fallback weights, read as a polite cock of the
head. `winged_headturn` in `stages/animate/poses.py` is reworked
to a true owl turn: swing to −1.05 rad and hold, sweep to
+1.05 rad and hold, settle back to centre (smoothstep segments,
same 3.2 s period; wing/ear/tail accents unchanged). Rework was
animate-only — the proven rig was kept: `animate_blender.py`
re-baked the clips from the existing `rigged.glb`, then
`render_verify.py` re-verified and re-rendered; catalog metadata
and the run manifest's animate/catalog/verify records were
updated to the new GLB (the pre-rework GLB + metadata are backed
up under `outputs/ember-owl-cat/backup-pre-headturn-fix/`).
New catalog sha256 `2bd78ce04579dbc605c7bcaf198ffa57c399165cec166ba6702f22c9e5844b3a`
(same 20,053,292 bytes — only animation data changed);
catalog-verify MATCH; weight coverage still 1.0; the apex render
(frame 27, mid-hold) now shows an unmistakable side-look with no
neck tearing; action-frame ground dip −0.024, negligible. A new
test locks the plateaus (`test_headturn_is_a_real_turn_with_holds`);
suite 135 passed. The wallpaper copy was re-synced the same day
(wallpaper project records).


## Headturn correction (2026-11-10, later) — the turn is now a turn

Correction to the entry above: the owner rejected the ±1.05 rad
version too — measured against his definition (an owl turn is a
level horizontal swivel; what he saw was a tilt), he was right.
Landmark measurement on the baked clip (beak-tip vertex, world
space) showed the bone-local Z rotation produced yaw +92°/−66°
**with the beak dipping 0.25–0.30** — the head bone's local Z is
canted, so the "turn" was a dipping cone sweep. A pitch-compensation
sweep proved euler channels cannot cancel the dip. Fix: the
animate stage's driver table now maps the winged-creature
`head_yaw` channel to a new `world_z` axis kind — `set_pose`
conjugates the armature-vertical rotation by the bone's rest
orientation (folding in the pitch accent), so the head rotates
about the world vertical. Re-measured on the re-baked clip:
**yaw −55.0° / +57.7° at the two holds, beak height change
+0.001 / −0.005** — level. The apex render now shows a
near-profile side-look, head upright. Animate-only again (rig
untouched; pre-fix GLB backed up under
`outputs/ember-owl-cat/backup-pre-world-yaw/`). New catalog
sha256 `98bc4f3f5c25f9ecb941a0d63ab387e14139fa808f2d16f4fcf779d2dad7102f`;
catalog-verify MATCH; suite 135 passed. Note for future
templates: any bone-local yaw on a canted bone has the same
trap — prefer `world_z` for head turns. The wallpaper copy was
re-synced the same day (wallpaper project records).

## Arm-separation rebuilds (2026-11-11, branch game-asset-builder/arm-separation-fixes)

Outcome: 0 of 6 rebuilds shipped; deployed catalog untouched. Failure
modes, in the order a future retry will meet them:

1. **Concept gate is bodyplan-bound.** Biped preflight daylight caps at
   ~0.31 for single-bulb bodies (mandrake: 8 attempts). The passing
   mandrake concept is a TWO-bulb redesign (head bulb + belly bulb,
   arms attach at the waist pinch) at 0.4437. Owl-cat down-wings cap
   ~0.38 (best of 9: 0.3799) — unpassed; a future attempt needs the
   25–40% rows (wings raised beside the head) or a narrower belly.
   Humanoid/thin-limbed plans pass easily (crow 0.4957, toasty 0.7697,
   goblin 0.4125, axolotl quad 5 components / 0.0213 gap).
2. **Posed gate can fail on weights alone.** Mandrake's mesh was
   genuinely separated, but bone heat was rejected (torso arm share
   0.60) and the distance fallback couples belly + feet to the arms:
   the scream tears at 1.50 rad, deforms at ×0.35, smears feet at
   ×0.18. Bulb bodies + fallback weights + big arm clips do not mix.
3. **The paint stage is the systemic blocker.** After the delver and
   mandrake succeeded early in the combined queues, EVERY later
   texture (goblin ×2, crow, toasty, axolotl, plus the Underreach
   gloam/lantern) froze or spun at "[paint] input mesh" — log frozen
   at exactly 1,419 bytes, GPU 100% at ~60 W (one goblin bake ran
   ~100 min at full power, still no output). Successful paints peaked
   11.9 GiB of 12.3 GiB VRAM. Root cause NOT proven; a PC reboot /
   driver-state reset is the untested first suspect for a retry.
4. **Bridge tracking limits corrupt runs silently.** The client
   abandons stages at ~15–25 min while the stage lives on; a client
   that then fetches gets the PREVIOUS build's lab file and will
   catalogue a Frankenstein (happened to the goblin; reverted).
   Discipline for any retry: judge stages by the lab result JSON
   CONTENT and sha256 of lab outputs (staged hash script), never by
   file dates (the PC clock is unreliable) or fetch freshness;
   verify every fetched GLB's sha before letting a resume proceed;
   a local textured.glb whose provenance is not hash-verified must be
   deleted before --resume, or the resume skips texture silently.

## Arm-separation retry (2026-11-12, same branch)

The PC reboot (owner-ordered 2026-11-11) was the untested remedy for
the paint freeze; the gloam-lurker canary textured clean on the first
post-reboot dispatch (615 s), and the owner authorized retrying the
four texture-blocked rebuilds (crow → toasty → axolotl → goblin).
Catalogue on this branch only — no wallpaper deployment in this run.

- **Crow Postman: DONE.** Texture exit 0 (1,206.26 s; load 108.65 s,
  bake 1,075.93 s; peak VRAM 11,881 MiB); genuine lab textured.glb
  sha-verified (92f448a5…). The tracking-limit failure mode in point
  4 above RECURRED: the client read the stale result at ~15 min and
  fetched the stale texture; it was killed before segment consumed
  it (one proxy.glb built from the wrong mesh — deleted), the stage
  finished detached, and the genuine output was recovered by hash.
  Finish: P3-SAM 14 parts, biped rig (distance-fallback weights,
  coverage 1.0), clips idle/walk/run/bow, catalog-verify MATCH
  (c2e23612…). Posed gate: PASS with disclosed weakness — shipped
  poses all clean; forward arm raise sails the coat panel (onset
  1.2–1.7 rad; full sail at the 2.2 rad stress pose); no shipped
  clip raises the arm past ~0.6 rad. Genuine prep/mesh/texture
  records restored into the manifest + catalog provenance after
  the --resume finish overwrote them with placeholders.
- **Toasty: DONE.** Texture exit 0 (906.87 s; load 112.82 s, bake
  773.77 s; peak VRAM 11,823 MiB); genuine lab textured.glb
  sha-verified (b5ed9eda…). The VM runtime restarted mid-run: the
  client had already recorded the genuine texture result locally
  (verified against the lab result JSON + STAGE_JSON re-read after
  the restart) but died before fetching the GLB — recovered from
  the lab by hash, no re-dispatch. Finish: P3-SAM 7 parts, biped
  rig with bone-heat weights ACCEPTED (geodesic + label vetoes;
  torso arm share 0.0238; coverage 1.0), clips idle/walk/run/
  bounce, catalog-verify MATCH (3818679c…). Posed gate: PASS with
  disclosed weakness — leg fusion (the audited defect) absent in
  every pose incl. the stress step; body surface peels into a
  flap beside the arm only at the 2.2 rad stress raise, far
  beyond any shipped clip's arm motion.
