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

Instrumentation added 2026-11-16 at the owner's direction, after the
#29/#31 stalls recurred with the allocator fix in place: the stage
logs its effective PYTORCH_CUDA_ALLOC_CONF and whether the value was
operator-provided or the stage default (the fix below is a
``setdefault``, so an operator value silently replaces it), dumps all
thread stacks to ``<out>.threads.log`` every 900 s via faulthandler,
and prints a heartbeat with elapsed time and peak VRAM every 300 s.
The next stall should name the wedged call instead of running silent.
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
_OPERATOR_ALLOC_CONF = os.environ.get("PYTORCH_CUDA_ALLOC_CONF")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF",
                      "expandable_segments:True")
ALLOC_CONF = os.environ["PYTORCH_CUDA_ALLOC_CONF"]
ALLOC_CONF_SOURCE = ("operator" if _OPERATOR_ALLOC_CONF is not None
                     else "stage-default")

REPO = os.environ.get("GAB_HUNYUAN_REPO",
                      r"D:\asset-forge-lab\repos\Hunyuan3D-2")
sys.path.insert(0, REPO)


def main() -> int:
    import faulthandler
    import threading

    import torch
    import trimesh
    from PIL import Image
    from hy3dgen.texgen import Hunyuan3DPaintPipeline

    shape_glb, input_png, out_glb = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(os.path.dirname(out_glb), exist_ok=True)

    print(f"[paint] PYTORCH_CUDA_ALLOC_CONF={ALLOC_CONF} "
          f"(source: {ALLOC_CONF_SOURCE})", flush=True)

    # Stall instrumentation (2026-11-16): periodic all-thread dumps go
    # to a sidecar file so the stage log stays readable; if the stage
    # wedges, the dumps name the wedged call (the method that found
    # the 2026-11-10 allocator stall, docs/PAINT_STALL.md). The file
    # object must stay referenced for the life of the process.
    threads_log = open(out_glb + ".threads.log", "a", buffering=1)
    faulthandler.enable(file=threads_log)
    faulthandler.dump_traceback_later(900, repeat=True, file=threads_log)

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

    stop_beat = threading.Event()

    def heartbeat() -> None:
        start = time.time()
        while not stop_beat.wait(300):
            peak = torch.cuda.max_memory_allocated() / 2**20
            print(f"[paint] heartbeat elapsed={time.time() - start:.0f}s "
                  f"peak_vram={peak:.0f} MiB", flush=True)

    threading.Thread(target=heartbeat, daemon=True).start()
    t1 = time.time()
    try:
        textured = pipe(mesh, image=image)
    finally:
        stop_beat.set()
        faulthandler.cancel_dump_traceback_later()
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
