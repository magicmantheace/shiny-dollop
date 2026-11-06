# Test plan — Game Asset Builder

## Verified on the build VM (no GPU) — 2026-11-06

- Unit tests: 28/28 pass (`python3 -m unittest discover -s tests`).
  The original 8 pin the pipeline order, the mesh-before-texture rule,
  and the unload discipline (every model stage is an isolated GPU
  process). The P0 additions pin the rig template's shape (Pip config
  = the proven 14 bones; dragon config swaps ears for arms; parents
  precede children), the pose recipes' math (hop arch, lift peak,
  idle bounds, clip frame counts), the catalog record (sha256
  round-trip + tamper detection), the flood-fill cutout on a synthetic
  image, and the bridge runner's token discipline. The skinning
  additions pin the heat-acceptance policy (healthy result accepted;
  low coverage, an empty bone, and wingtips left to other bones each
  rejected with named reasons; multiple failures all reported).
- Prep stage on the real Ember Dragon concept: clean cutout
  (foreground 29.6% of frame), visually inspected against the concept.
- Rig + animate + verify chain exercised twice in Blender: on the
  bake-off's Hunyuan Pip GLB as a stand-in (ears config) and on the
  Ember Dragon's own textured GLB (arms config). Both produced a
  14-bone armature, 14 populated vertex groups, weight coverage 1.0,
  embedded `idle` + `hop` clips, and cold-re-import renders showing
  rest pose intact and the hop apex airborne (+0.17–0.19 ground
  clearance) with both wings swept up and no tearing.
- Skinning (P0 state): bone-heat automatic weights produced ZERO
  weights on both Hunyuan meshes (recorded in each rig report); the
  deterministic distance-to-bone fallback skinned both, coverage 1.0.
- Skinning hardening (2026-11-06, same VM): the failure was diagnosed
  by measurement — rig inputs carried 28 (dragon) / 135 (Pip)
  non-manifold edges plus debris shells after the weld, and only
  5/28 template bone endpoints sat inside the dragon mesh (validated
  ray-parity test, controls 6/6 and 0/6). With geometry cleanup +
  endpoint snapping in the rigger, bone heat succeeds on both meshes
  through the shipped code path: dragon — coverage 1.0, wingtip
  dominance 1.0 (fallback: 0.0), distance rescue on 6 verts only;
  Pip — coverage 1.0, wingtip 1.0, no rescue. The dragon was
  re-animated and re-catalogued (catalog-verify MATCH on the new
  sha256); cold re-import shows 14 bones / 14 groups / idle + hop,
  hop apex clearance 0.19 vs 0.025 at rest.
- Stress deformation (`stages/catalog/stress_render.py`): a pose
  beyond the shipped clips (wing.L at 1.25 rad vs the hop's 0.65,
  head turned 0.65 rad, tail curled ~1.75 rad total) rendered from
  two angles and inspected: raised wing intact, no tearing, no joint
  collapse, no candy-wrapper twist at the neck. A belly-centreline
  texture-seam streak grows with deformation (faint at hop apex,
  pronounced in the stress pose, absent at rest); the same artifact
  is present in the P0 fallback rig's hop render, so it predates the
  skinning change.
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
- **P0 pipeline proof run (Ember Dragon)**: dispatched through the
  project's own `gpu_bridge.py` + lab stage runner. Shape: exit 0,
  334 s, peak 7,233 MiB, after-exit 790 MiB (≈ baseline 809). Paint:
  exit 0 (stage result JSON; the bridge job wrapper misreported the
  job as failed — artifacts + result JSON are the authority), 909 s,
  peak 12,043 MiB, after-exit 778 MiB (≈ baseline 788). The mesh
  process had fully exited before paint was dispatched — unload
  discipline verified by the runner's VRAM samples, not assumed.
  One transient bridge disconnect killed the first local poller
  mid-paint; the job completed server-side and was reattached.

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
- The catalogued GLB in a game engine (Godot/three.js playback of the
  baked clips) — verified in Blender only; engine hand-off is P3.
- The rig template on non-dragonoid winged creatures (the template's
  proportions were exercised on two Hunyuan outputs with similar
  anatomy: Pip and the Ember Dragon).
- The cleanup's debris-shell rule (< 0.5% of the largest shell) on a
  mesh whose small shells are real anatomy (detached eyes, teeth,
  held props): unexercised — on both current meshes the dropped
  shells were interior floaters, verified by vert counts only.

## Rules

- A result is claimed only from the machine it ran on: GPU results cite PC
  runs, never VM runs.
- Bake-off scores are recorded in `benchmarks/pip/scores.md` in the same
  commit series that produces them, failures included.
