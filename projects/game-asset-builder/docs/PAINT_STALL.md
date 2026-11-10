# Hunyuan paint stall — investigation summary (2026-11-10)

Status: **root cause narrowed, not proven. Fix deferred at the owner's
direction (2026-11-10); the environment pack shipped with procedural
vertex-colour paint instead.** Full evidence lives in the goal
workspace (`game-asset-builder-fully-local-asset-pipeline` hidden
files, `paint-investigation/findings.md`).

## Symptom
The texture stage intermittently never finishes: it loads, logs the
input mesh, then sits inside `pipe()` indefinitely — pine attempts ran
10,801 s and 7,728 s vs a success curve of ~630–2,400 s for comparable
or larger meshes. Ember Owl-Cat stalled the same way. Successes and
stalls use the identical code path.

## What was proven (instrumented, on the owner's PC)
- The stall is inside the multiview VAE encode:
  texgen `pipelines.py` → `encode_images` (normal maps) → diffusers
  `AutoencoderKL.encode` → encoder down blocks, fp32.
- Per-block timing: `conv_in` returns in ~0.04 s; **down_block 0 never
  returns**. Its faulthandler dump sits in `F.pad`
  (`torch/nn/functional.py`) called from diffusers
  `Downsample2D.forward` (`downsampling.py`).
- The stall is **data-independent**: a random (1,6,3,512,512) tensor
  stalls identically. It reproduces with the **standalone VAE** in a
  fresh process on an empty GPU — not memory pressure, not the
  pipeline, not the mesh.
- Raw references on the same GPU/venv are fast (fp32 conv 3→128 @512²
  0.093 s, GroupNorm 0.037 s, conv 128→128 0.098 s). Stack: torch
  2.14.1+cu126, driver 610.62, RTX 3060; `cudnn.benchmark=False`, TF32
  allowed for conv.

## Standing suspicion (not a finding)
A pathology in the VAE encoder's first Downsample2D pad/stride-conv
path in fp32 on this torch build.

## Next steps for the fix attempt
1. Time `Downsample2D` alone with the real VAE weights/shapes.
2. Try `cudnn.benchmark=True`; try the VAE in fp16.
3. Try a stable torch build in a scratch venv; compare.

## Correction recorded during the investigation
Mandrake Toddler's P5 "texture failure" was a bookkeeping error, not
a paint failure: its retry stage completed exit 0 in 967.81 s and left
a valid `textured.glb` in the lab, which was never fetched. The GLB
was recovered and verified (558,050 verts, UVs, 2048² texture, Cycles
render inspected). Its remaining stages (segment/rig/animate/catalog)
were never run — finishing it is the owner's call.
