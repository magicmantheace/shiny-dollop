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

## Verified on the owner's PC (GPU stages) — 2026-11-06

- Bake-off round 1 ran end-to-end (lab at `D:\asset-forge-lab`, per-stage
  venvs, uv-managed Python 3.12): Hunyuan3D-2 shape (305 s, peak
  8,762 MiB) and paint (1,520 s, peak 12,086 MiB) as separate processes
  with VRAM released between; TripoSR (39 s, 6,100 MiB); TRELLIS
  inference (176 s, 12,020 MiB, no OOM). Output meshes were fetched to
  the VM and re-verified (counts + sha256) before scoring.
- Stable Fast 3D did NOT run: its HF repo is gated (401). Recorded as
  BLOCKED in `benchmarks/pip/scores.md`, not as a failure of the model.

## Verified on the build VM — 2026-11-06 (scoring)

- The silhouette-IoU scorer (`benchmarks/pip/score_render.py` +
  `iou_sheet.py`) scored all three delivered candidates against the
  Meshy reference: Hunyuan3D-2 RIGGABLE (front IoU 0.84), TRELLIS and
  TripoSR MELTED — full table and method notes in
  `benchmarks/pip/scores.md`. The comparison sheet was inspected
  visually; it overruled TRELLIS's numeric 0.55, per protocol.
- Two scorer defects were caught by that inspection and fixed before
  the recorded scores were produced: importer axis-conversion rotations
  must be baked before transform work, and yaw is orbited by the camera
  because glTF objects in quaternion mode ignore `rotation_euler`
  writes. (Details in `scores.md` method notes.)

## Not yet verified

- TRELLIS's proper textured export — blocked on the
  `diff_gaussian_rasterization` CUDA build on the PC.
- Rig/animation stages against a locally generated mesh — proven in
  2026-11 against the Meshy Pip mesh (Drabbit Pet), not yet against a
  local (Hunyuan) mesh; that is the P0 pipeline's acceptance test.

## Rules

- A result is claimed only from the machine it ran on: GPU results cite PC
  runs, never VM runs.
- Bake-off scores are recorded in `benchmarks/pip/scores.md` in the same
  commit series that produces them, failures included.
