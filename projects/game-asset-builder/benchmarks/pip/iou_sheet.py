#!/usr/bin/env python3
"""Score bake-off candidates against the reference by silhouette IoU and
compose the side-by-side sheet.

Reads scored/<label>/mask_<view>_yaw<N>.png + beauty renders produced by
score_render.py. The reference is canonical at yaw 0. For each candidate,
the best-facing yaw is the one whose front mask best matches the reference
front mask; all views are then scored at that yaw.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

BASE = (sys.argv[1] if len(sys.argv) > 1
        else os.path.join(os.getcwd(), "scored"))
VIEWS = ["front", "side", "back", "threeq"]
CANDIDATES = ["hunyuan3d2", "trellis", "triposr"]


def load_mask(label, view, yaw):
    p = os.path.join(BASE, label, f"mask_{view}_yaw{yaw}.png")
    a = np.asarray(Image.open(p).convert("RGBA"))[:, :, 3]
    return a > 127


def iou(a, b):
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 0.0


def main():
    ref = {v: load_mask("reference", v, 0) for v in VIEWS}
    results = {"reference": {"verts_note": "owner Meshy Pip"}}
    best_yaw = {"reference": 0}
    for cand in CANDIDATES:
        scores_by_yaw = {y: iou(load_mask(cand, "front", y), ref["front"])
                          for y in (0, 90, 180, 270)}
        yaw = max(scores_by_yaw, key=scores_by_yaw.get)
        best_yaw[cand] = yaw
        per_view = {v: round(iou(load_mask(cand, v, yaw), ref[v]), 4)
                    for v in VIEWS}
        results[cand] = {"best_yaw": yaw, "front_iou_by_yaw":
                         {str(k): round(v, 4) for k, v in scores_by_yaw.items()},
                         "iou": per_view,
                         "iou_mean": round(float(np.mean(list(per_view.values()))), 4)}
    with open(os.path.join(BASE, "scores.json"), "w") as f:
        json.dump(results, f, indent=1)
    print(json.dumps(results, indent=1))

    # ---- sheet: rows = reference + candidates; cols = front beauty,
    # three-quarter beauty (best yaw), front-mask overlay vs reference.
    labels = ["reference"] + CANDIDATES
    cell = 384
    header_h = 30
    sheet = Image.new("RGB", (cell * 3 + 8, (cell + header_h) * len(labels) + 8),
                      (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    for r, lab in enumerate(labels):
        y0 = 4 + r * (cell + header_h)
        yaw = best_yaw[lab]
        title = lab if lab == "reference" else (
            f"{lab}  front IoU {results[lab]['iou']['front']:.2f}  "
            f"mean {results[lab]['iou_mean']:.2f}")
        d.text((8, y0 + 6), title, fill=(235, 235, 240))
        for c, kind in enumerate(("front", "threeq")):
            p = os.path.join(BASE, lab, f"beauty_{kind}_yaw{yaw}.png")
            img = Image.open(p).convert("RGBA").resize((cell, cell))
            bg = Image.new("RGBA", (cell, cell), (40, 40, 48, 255))
            bg.alpha_composite(img)
            sheet.paste(bg.convert("RGB"), (4 + c * cell, y0 + header_h))
        # overlay: reference front mask in red, candidate in green alpha
        ov = np.zeros((512, 512, 3), dtype=np.uint8) + 30
        cand_mask = ref["front"] if lab == "reference" else load_mask(lab, "front", yaw)
        ov[ref["front"]] = [200, 60, 60]
        both = np.logical_and(cand_mask, ref["front"])
        only_c = np.logical_and(cand_mask, ~ref["front"])
        ov[only_c] = [60, 200, 60]
        ov[both] = [230, 230, 230]
        oimg = Image.fromarray(ov).resize((cell, cell))
        sheet.paste(oimg, (4 + 2 * cell, y0 + header_h))
    out = os.path.join(BASE, "comparison-sheet.png")
    sheet.save(out)
    print("SHEET_OK", out)


if __name__ == "__main__":
    sys.exit(main())
