# stages/

One folder per pipeline stage. The authoritative stage list and order
live in `../stages.py`; the orchestrator is `../pipeline.py`
(`asset_builder.py run`).

- `prep/cutout.py` — flood-fill/feather cutout, concept image → RGBA
  PNG cropped to the subject. In-process, CPU.
- `mesh/hunyuan_shape.py` — Hunyuan3D-2 shape (DiT). Runs on the
  owner's PC in the lab venv as its own process (load → run → exit),
  dispatched by `../gpu_bridge.py`.
- `texture/hunyuan_paint.py` — Hunyuan3D-2 paint. Same discipline,
  dispatched only after the mesh process has exited and its VRAM
  release is verified.
- `rig/template.py` — the winged-creature armature template (pure
  data; ears/arms parameterized). `rig/rig_blender.py` — Blender
  headless: canonicalize, weld, decimate, fit template, skin
  (bone-heat attempted first; deterministic distance-to-bone fallback
  is what actually skins Hunyuan meshes — see docs/TEST_PLAN.md).
- `animate/poses.py` — procedural pose recipes ported from Drabbit
  Pet's pose driver (pure functions), plus the P4 parametric gait
  model (walk/run for every template). `animate/animate_blender.py` —
  bakes them as named GLB actions. `animate/glb_clips.py` — stdlib
  reader for a GLB's clip names + durations.
- `catalog/catalog.py` — metadata JSON + sha256 (stdlib).
  `catalog/render_verify.py` — Blender cold re-import check + preview
  renders (rest + hop apex) for every catalogued asset.
