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


## RESOLVED (2026-11-10) — CUDA caching-allocator pathology

The stall is fixed. Root cause, established by controlled probes on
the owner's PC (RTX 3060, torch 2.14.1+cu126, driver 610.62):

- The standalone VAE encodes a batch-6 (6,3,512,512) tensor fine
  (~1.9 s). `cudnn.benchmark=True` is NOT the fix (11–12 s, slower).
- Inside the **full paint pipeline** (all models resident), the same
  batch-6 encode never returns: a faulthandler dump places the main
  thread in the first down-block convolution of the VAE encoder,
  GPU pinned at 100% / ~73 W.
- The identical pipeline encoding **batch-1 six times** completes in
  3.67 s. Batch size is the trigger, in-process, once the paint
  models are resident.
- Setting **`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`**
  makes the batch-6 encode complete in **2.63 s** in the full
  pipeline. Verdict: a pathology of the default CUDA caching
  allocator in this resident-memory state — not the VAE math, not
  cuDNN. (Why it spins rather than errors is not proven beyond that;
  not over-claimed.)

**The fix:** `stages/texture/hunyuan_paint.py` now sets
`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` via
`os.environ.setdefault` at import, before torch initializes CUDA;
an operator-provided value is respected.

**End-to-end proof (production stage, not a probe):** the Ember
Owl-Cat — whose paint stalled on two prior attempts — completed its
texture stage with exit 0: loaded in 104.5 s, "texturing in
6202.2 s" on the 1,405,816-face mesh, peak VRAM 11,910 MiB, cleanly
released after exit. The run then continued segment → rig →
animate → catalog; catalog-verify sha256 MATCH. The stage remains
slow on very large meshes (tortoise: ~2,524 s at 1.64M faces; the
owl-cat's 6,202 s is the current worst case) and the ~17 GB
private-memory plateau remains its normal footprint — the
corrected kill criteria in this document still apply. The earlier
"standing suspicion" (Downsample2D pad/stride path) is superseded:
the dump did place the hang at the down-block, but the allocator
setting is what cures it.
