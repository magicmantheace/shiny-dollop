"""P3-SAM segmentation driver — runs ON the owner's PC, in the
p3sam venv, as its own process (load -> run -> exit; the lab
runner verifies VRAM returns to baseline afterwards).

Invokes the lab copy of Hunyuan3D-Part's auto_mask.py with the
bake-off's scored configuration (seed 42, --parallel 0, upstream
defaults otherwise; the lab copy carries the shims the bake-off
documented: prompt_bs default 4, Sonata flash-attention off, era
pins — see benchmarks/segmentation/scores.md).

Usage: p3sam_driver.py <proxy.glb> <output_dir> <ckpt_path> <demo_dir>

Prints STAGE_JSON {...} (picked up from the stage log by the
pipeline) and SEGMENT_OK.
"""

import json
import os
import subprocess
import sys


def main():
    proxy, out_dir, ckpt, demo = sys.argv[1:5]
    os.makedirs(out_dir, exist_ok=True)
    cmd = [sys.executable, os.path.join(demo, "auto_mask.py"),
           "--mesh_path", proxy,
           "--output_path", out_dir,
           "--ckpt_path", ckpt,
           "--seed", "42",
           "--parallel", "0"]
    proc = subprocess.run(cmd, cwd=demo)
    if proc.returncode != 0:
        print(f"SEGMENT_FAIL auto_mask exited {proc.returncode}")
        return proc.returncode or 1
    ids_path = os.path.join(
        out_dir, "auto_mask_mesh_final_face_ids.npy")
    if not os.path.exists(ids_path):
        print("SEGMENT_FAIL no face_ids output")
        return 1
    import numpy as np
    ids = np.load(ids_path).reshape(-1)
    parts = sorted(int(u) for u in set(ids.tolist()) if u >= 0)
    stats = {"segmentation_model": "tencent/Hunyuan3D-Part P3-SAM",
             "seed": 42,
             "proxy_faces_labelled": int(len(ids)),
             "parts": len(parts),
             "raw_label_ids": parts,
             "unlabelled_faces": int((ids < 0).sum())}
    print("STAGE_JSON " + json.dumps(stats))
    print("SEGMENT_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
