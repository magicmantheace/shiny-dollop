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

Next (P0, in order):
1. Model bake-off on the owner's PC: set up a uv-managed Python 3.12 stage
   environment on D: (system Python 3.14 is too new for PyTorch wheels);
   run each candidate as its own process on the benchmark input; record
   time + peak VRAM; bring meshes back for scoring.
2. Build the Blender scorer (normalize + matched-camera renders +
   silhouette IoU vs the reference) and write `benchmarks/pip/scores.md`
   with a side-by-side sheet for the owner.
3. Pick the winning mesh/texture pair with the owner, then build the full
   P0 pipeline around it: prep → mesh → texture → rig (winged-creature
   template) → animate → catalog.

Boundaries: no cloud fallback exists or may be added; weights and outputs
never enter git; GPU claims only from PC runs; merges are the owner's call.
