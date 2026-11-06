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
  `cutout`, and `catalog-verify` commands. 23 unit tests pass.
- Ember Dragon run (PC, RTX 3060): shape 334 s (peak 7,233 MiB;
  423,908 verts out), paint 909 s (peak 12,043 MiB — ~250 MiB headroom
  again; 657,672 verts textured), VRAM back at baseline after each
  stage. Rig: welded 395,731 → decimated 45,012 verts, 14 bones
  (arms in, ears out), idle (4.8 s) + hop (1.24 s) clips baked; final
  GLB 20.7 MB, sha256 pinned in `catalog/ember-dragon/metadata.json`
  and re-verified via `catalog-verify`.
- Skinning reality: Blender bone-heat yields **zero** weights on these
  Hunyuan meshes (both Pip and the dragon), so the rig's deterministic
  distance-to-bone fallback did the skinning both times — coverage
  1.0, and the hop renders show clean, tear-free deformation with
  both wings sweeping up. Treat distance weights as the working
  method, bone heat as an attempted-first check.
- Incident, recovered honestly: the first pipeline process died on a
  transient bridge disconnect while polling the paint job. The job
  kept running server-side and finished; its outputs were adopted via
  the new reattach path, and the catalog provenance records the
  recovery. (The bridge job wrapper also reported that job "failed"
  while the stage's own result JSON records exit 0 — the stage
  artifacts and result JSON are the authority.)

Next:
1. Owner decisions outstanding: PR #36 merge; whether to unblock
   Stable Fast 3D (owner-side HF action, only if wanted).
2. P1 when directed: quadruped/biped rig templates, the unrigged prop
   path, and trying the optional rembg prep upgrade.

Boundaries: no cloud fallback exists or may be added; weights and outputs
never enter git; GPU claims only from PC runs; merges are the owner's call.
