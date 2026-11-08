"""Prep stage: concept image -> RGBA cutout.

Method (per docs/DESIGN.md stage 0): estimate the background colour from
the image corners, flood-fill from the borders through near-background
pixels, then feather the mask edge. Fully local, no learned model; the
optional rembg path stays a future upgrade. Works on any PIL-readable
input (png/jpg/webp).

CLI:  python3 cutout.py <input> <output.png>
"""

import sys
from collections import deque


def make_cutout(input_path: str, output_path: str,
                tolerance: int = 26, feather: int = 2,
                crop_pad: int | None = 24) -> dict:
    """Write an RGBA PNG cutout; return stats about the result.

    With ``crop_pad`` set, the output is cropped to the foreground
    bounding box plus that many pixels of margin — the mesh models are
    fed a frame-filling subject, like the benchmark's fixed input.
    """
    import numpy as np
    from PIL import Image

    img = Image.open(input_path).convert("RGB")
    a = np.asarray(img).astype(np.int16)
    h, w, _ = a.shape

    # Background colour: median of the four corner patches.
    p = 8
    corners = np.concatenate([
        a[:p, :p].reshape(-1, 3), a[:p, -p:].reshape(-1, 3),
        a[-p:, :p].reshape(-1, 3), a[-p:, -p:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)

    dist = np.abs(a - bg).max(axis=2)
    near_bg = dist <= tolerance

    # Flood fill from every border pixel through near-background pixels.
    outside = np.zeros((h, w), dtype=bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if near_bg[y, x] and not outside[y, x]:
                outside[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if near_bg[y, x] and not outside[y, x]:
                outside[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and near_bg[ny, nx] \
                    and not outside[ny, nx]:
                outside[ny, nx] = True
                q.append((ny, nx))

    alpha = np.where(outside, 0, 255).astype(np.float32)
    if feather > 0:
        # Box-blur the mask a couple of passes for a soft edge, but keep
        # deep-interior pixels fully opaque.
        for _ in range(feather):
            padded = np.pad(alpha, 1, mode="edge")
            alpha = (padded[:-2, :-2] + padded[:-2, 1:-1] + padded[:-2, 2:]
                     + padded[1:-1, :-2] + padded[1:-1, 1:-1]
                     + padded[1:-1, 2:] + padded[2:, :-2]
                     + padded[2:, 1:-1] + padded[2:, 2:]) / 9.0
        alpha = np.clip(alpha * 1.5 - 32, 0, 255)

    rgba = np.dstack([np.asarray(img), alpha.astype(np.uint8)])
    ys, xs = np.nonzero(alpha > 8)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    fraction = round(float((alpha > 8).mean()), 4)
    out_img = Image.fromarray(rgba, "RGBA")
    if crop_pad is not None:
        box = (max(0, bbox[0] - crop_pad), max(0, bbox[1] - crop_pad),
               min(w, bbox[2] + crop_pad + 1),
               min(h, bbox[3] + crop_pad + 1))
        out_img = out_img.crop(box)
    out_img.save(output_path)
    return {
        "input": input_path,
        "output": output_path,
        "size": [int(out_img.width), int(out_img.height)],
        "source_size": [int(w), int(h)],
        "background_rgb": [int(round(c)) for c in bg],
        "foreground_fraction": fraction,
        "foreground_bbox": bbox,
    }


if __name__ == "__main__":
    import json
    if len(sys.argv) != 3:
        raise SystemExit("usage: cutout.py <input> <output.png>")
    print(json.dumps(make_cutout(sys.argv[1], sys.argv[2]), indent=1))
