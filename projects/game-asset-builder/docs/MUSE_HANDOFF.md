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

Next:
1. Owner decisions outstanding: merge of the skinning PR (draft,
   against main; PR #36 merged 2026-11-06 at `8b6609b`); whether to
   unblock Stable Fast 3D (owner-side HF action, only if wanted).
2. P1 when directed: quadruped/biped rig templates, the unrigged prop
   path, and trying the optional rembg prep upgrade.

Boundaries: no cloud fallback exists or may be added; weights and outputs
never enter git; GPU claims only from PC runs; merges are the owner's call.
