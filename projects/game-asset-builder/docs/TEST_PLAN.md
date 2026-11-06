# Test plan — Game Asset Builder

## Verified on the build VM (no GPU) — 2026-11-06

- Stage registry unit tests: 8/8 pass (`python3 -m unittest discover -s tests`).
  They pin the pipeline order, the mesh-before-texture rule, and the
  unload discipline (every model stage is an isolated GPU process).
- CLI `stages` and `benchmark-plan` run and print the registry/protocol.
- CLI `doctor` runs and honestly reports this machine: no GPU, GPU stages
  "CANNOT RUN on this machine". That report is correct for the VM and is
  itself a checked behavior — the tool must never pretend a GPU stage ran
  where it cannot.

## Verified hardware facts (owner's PC, via the PC bridge) — 2026-11-06

- RTX 3060: 12,288 MiB total VRAM, 9,210 MiB free at rest; D: 3.1 TB free.
- These numbers bound the bake-off: any candidate needing more than the
  free VRAM must offload or be recorded as not fitting.

## Not yet verified (P0 bake-off)

- Every candidate model (Hunyuan3D-2 shape + paint, TripoSR on GPU,
  Stable Fast 3D, TRELLIS) — none has run on the PC yet.
- The silhouette-IoU scorer (Blender matched-camera renders) — protocol is
  written in `docs/DESIGN.md`; the scorer is built and first exercised
  during the bake-off.
- Rig/animation stages against a locally generated mesh — proven in 2026-11
  against the Meshy Pip mesh (Drabbit Pet), not yet against a local mesh.

## Rules

- A result is claimed only from the machine it ran on: GPU results cite PC
  runs, never VM runs.
- Bake-off scores are recorded in `benchmarks/pip/scores.md` in the same
  commit series that produces them, failures included.
