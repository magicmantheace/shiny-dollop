"""Mesh stage: Hunyuan3D-2 shape (DiT) — runs as its OWN process on the
owner's PC inside the lab venv (load -> run -> exit), per the project's
unload discipline. Parameters are the bake-off winner's, unchanged:
``Hunyuan3DDiTFlowMatchingPipeline.from_pretrained('tencent/Hunyuan3D-2')``
(default subfolder hunyuan3d-dit-v2-0, fp16), ``pipeline(image=RGBA)[0]``.

Usage (PC): hunyuan_shape.py <cutout.png> <out.glb> [offload]
The Hunyuan repo path comes from GAB_HUNYUAN_REPO (default: the lab's).
Prints a final ``STAGE_JSON {...}`` line with counts and timings.
"""

import json
import os
import sys
import time

REPO = os.environ.get("GAB_HUNYUAN_REPO",
                      r"D:\asset-forge-lab\repos\Hunyuan3D-2")
sys.path.insert(0, REPO)


def main() -> int:
    import torch
    from PIL import Image
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    input_png, out_glb = sys.argv[1], sys.argv[2]
    offload = len(sys.argv) > 3 and sys.argv[3] == "offload"
    os.makedirs(os.path.dirname(out_glb), exist_ok=True)

    t0 = time.time()
    pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        "tencent/Hunyuan3D-2")
    print(f"[shape] pipeline loaded in {time.time() - t0:.1f}s", flush=True)
    if offload:
        pipe.enable_model_cpu_offload()
        print("[shape] model CPU offload enabled", flush=True)

    image = Image.open(input_png).convert("RGBA")
    t1 = time.time()
    mesh = pipe(image=image)[0]
    inference_s = time.time() - t1
    print(f"[shape] inference in {inference_s:.1f}s", flush=True)
    mesh.export(out_glb)
    stats = {
        "stage": "mesh",
        "model": "tencent/Hunyuan3D-2 hunyuan3d-dit-v2-0",
        "verts": len(mesh.vertices),
        "faces": len(mesh.faces),
        "load_s": round(t1 - t0, 2),
        "inference_s": round(inference_s, 2),
        "total_s": round(time.time() - t0, 2),
        "torch_peak_mib": round(
            torch.cuda.max_memory_allocated() / 2**20, 1),
        "output": out_glb,
    }
    print("STAGE_JSON " + json.dumps(stats), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
