"""Texture stage: Hunyuan3D-2 paint — runs as its OWN process on the
owner's PC inside the lab venv (load -> run -> exit), strictly after the
mesh process has exited (the orchestrator verifies VRAM was released
before this stage is dispatched). Parameters are the bake-off winner's,
unchanged: ``Hunyuan3DPaintPipeline.from_pretrained('tencent/Hunyuan3D-2',
subfolder='hunyuan3d-paint-v2-0')``, ``pipeline(mesh, image=RGBA)``.

Usage (PC): hunyuan_paint.py <shape.glb> <cutout.png> <out.glb>
The Hunyuan repo path comes from GAB_HUNYUAN_REPO (default: the lab's).
Prints a final ``STAGE_JSON {...}`` line with counts and timings.
Note: the texturing phase logs nothing while it works — silence for
tens of minutes on a ~1M-face shape is normal. A run that exceeds the
success curve (see docs/PAINT_STALL.md) by an order of magnitude is
NOT normal: that was the allocator stall fixed below.
"""

import json
import os
import sys
import time

# PAINT STALL FIX (2026-11-10, docs/PAINT_STALL.md): with the paint
# pipeline's models resident, the batch-6 VAE encode inside
# pipe(mesh, image) could spin forever in the default CUDA caching
# allocator (GPU pinned at 100% but ~70 W, one CPU core busy).
# Expandable segments change the allocation strategy and the encode
# completes in seconds. Must be set before torch initializes CUDA,
# so it lives here at module import, ahead of main()'s torch import.
# An operator-provided PYTORCH_CUDA_ALLOC_CONF is respected.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF",
                      "expandable_segments:True")

REPO = os.environ.get("GAB_HUNYUAN_REPO",
                      r"D:\asset-forge-lab\repos\Hunyuan3D-2")
sys.path.insert(0, REPO)


def main() -> int:
    import torch
    import trimesh
    from PIL import Image
    from hy3dgen.texgen import Hunyuan3DPaintPipeline

    shape_glb, input_png, out_glb = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(os.path.dirname(out_glb), exist_ok=True)

    t0 = time.time()
    pipe = Hunyuan3DPaintPipeline.from_pretrained(
        "tencent/Hunyuan3D-2", subfolder="hunyuan3d-paint-v2-0")
    print(f"[paint] pipeline loaded in {time.time() - t0:.1f}s", flush=True)

    loaded = trimesh.load(shape_glb)
    if isinstance(loaded, trimesh.Scene):
        mesh = trimesh.util.concatenate(
            [g for g in loaded.geometry.values()])
    else:
        mesh = loaded
    print(f"[paint] input mesh verts={len(mesh.vertices)} "
          f"faces={len(mesh.faces)}", flush=True)

    image = Image.open(input_png).convert("RGBA")
    t1 = time.time()
    textured = pipe(mesh, image=image)
    texture_s = time.time() - t1
    print(f"[paint] texturing in {texture_s:.1f}s", flush=True)
    textured.export(out_glb)
    stats = {
        "stage": "texture",
        "model": "tencent/Hunyuan3D-2 hunyuan3d-paint-v2-0",
        "verts": len(textured.vertices),
        "faces": len(textured.faces),
        "load_s": round(t1 - t0, 2),
        "texture_s": round(texture_s, 2),
        "total_s": round(time.time() - t0, 2),
        "torch_peak_mib": round(
            torch.cuda.max_memory_allocated() / 2**20, 1),
        "output": out_glb,
    }
    print("STAGE_JSON " + json.dumps(stats), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
