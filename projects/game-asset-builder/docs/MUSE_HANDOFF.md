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

Next (P0):
1. Build the pipeline around the Hunyuan3D-2 pair: prep → shape →
   paint → rig (winged-creature template) → animate → catalog, reusing
   the lab's stage environments on the PC.
2. Prove it end-to-end on a second creature that isn't Pip.
3. Owner decisions outstanding: PR #36 merge; whether to unblock
   Stable Fast 3D (owner-side HF action, only if wanted).

Boundaries: no cloud fallback exists or may be added; weights and outputs
never enter git; GPU claims only from PC runs; merges are the owner's call.
