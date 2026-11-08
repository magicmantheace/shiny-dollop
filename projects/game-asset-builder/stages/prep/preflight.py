"""Prep stage: concept-image pre-flight fused-limb check.

A silhouette heuristic — nothing more. It looks at the concept image
the way the skinning stage will suffer from it: if two limbs read as
one solid mass in the silhouette, automatic weights have no boundary
to respect and will drag one limb with the other (the Snow Goblin's
fused fur ruff is the standing example: the shipped wave dragged the
torso with the arm). This check flags that risk *before* the GPU
stages spend time on a concept that needs re-posing or re-generating
under the pose spec in docs/DESIGN.md ("Concept pose & separation
spec"). It never proves a concept is good; a "pass" only means this
one known failure shape was not detected.

Method
------
Foreground mask: if the image carries meaningful alpha, the mask is
alpha > 128. Otherwise the background colour is estimated from the
image corners (in this project that is plain white or a near-white
light grey) and the mask is everything *not* reachable from the image
border through near-background pixels — the same flood-fill idea as
cutout.py, so a white-furred subject on a light-grey ground still
reads as a silhouette instead of vanishing into a raw near-white
threshold.

Quadruped leg separation: the belly line is found by scanning from
the bottom of the foreground bounding box upward for the first row
whose widest single foreground run reaches
``BELLY_WIDTH_FRAC`` of the widest run anywhere in the silhouette and
stays there for a few rows. Row width is the widest *run*, not the
total foreground count: chunky cartoon legs sum to almost the body
width in count while remaining separate runs (the giraffe proof
concept's legs are ~0.66 of the body width by count, ~0.17 by widest
run), so a count-based scan places the "belly" at the feet. In the
leg band below the belly line the mask is eroded by
``EROSION_FRAC`` of the bounding-box width — enough to break thin
fur/web joins, far less than a real leg's width — and the surviving
connected components are counted; the minimum background gap between
adjacent runs is also measured at rows around mid-leg height.

Biped arm daylight: in the arm band (rows 25%-65% of the bounding-box
height) a row has daylight when a background gap of at least
``MIN_GAP_FRAC`` of the bounding-box width sits inside the row's
foreground span — background that can only be the space between an
arm and the torso. The metric is the fraction of arm-band rows (with
any foreground) that have such a gap. A fused silhouette is one solid
run on essentially every such row, so it scores near zero.

Thresholds below are calibrated on exactly the project's two known
cases — the giraffe concept generated to the pose spec (quadruped,
clearly separated legs; passes) and the original Snow Goblin concept
(biped, arms fused into one fur mass; arm daylight 0.009, warns) —
plus the synthetic silhouettes in tests/test_preflight.py. They are
heuristic constants, not measured truths; recalibrate them openly
when a new known case disagrees.

Pure Python + PIL + numpy. No Blender, no network.

CLI:  python3 preflight.py <image> <body_plan>
      prints the result dict as JSON; exit 0 on pass, 3 on warn.
"""

import json
import sys
from collections import deque

BODY_PLANS = ("biped", "quadruped", "winged")

# --- Calibrated constants (see module docstring) -------------------------
BG_TOLERANCE = 18          # max per-channel distance from the corner
                           # background colour that still counts as ground
BELLY_WIDTH_FRAC = 0.60    # widest-run width, relative to the silhouette's
                           # widest run, that marks the solid body mass
BELLY_SUSTAIN_ROWS = 5     # rows the belly width must hold for
EROSION_FRAC = 0.015       # leg-band erosion radius, relative to bbox width
MIN_GAP_FRAC = 0.02        # smallest background gap that counts as daylight,
                           # relative to bbox width (both checks)
QUAD_MIN_COMPONENTS = 3    # leg components that must survive erosion
                           # (4 legs are ideal; a 3/4 view may merge one pair)
BIPED_MIN_DAYLIGHT_ROW_FRAC = 0.40  # arm-band daylight rows needed to pass;
                           # separated A-pose synthetics score ~0.8, the
                           # fused goblin scores 0.009
ARM_BAND = (0.25, 0.65)    # arm band, as fractions of bbox height
MIN_COMPONENT_AREA_FRAC = 0.0005  # of leg-band area; smaller surviving
                           # specks after erosion are noise, not legs


# --- Mask ----------------------------------------------------------------

def _foreground_mask(image_path):
    """Boolean foreground mask for the concept at ``image_path``."""
    import numpy as np
    from PIL import Image

    img = Image.open(image_path)
    if img.mode in ("RGBA", "LA") or "transparency" in img.info:
        rgba = img.convert("RGBA")
        alpha = np.asarray(rgba)[:, :, 3]
        if float((alpha < 250).mean()) > 0.01:
            return alpha > 128

    a = np.asarray(img.convert("RGB")).astype(np.int16)
    h, w, _ = a.shape
    p = 8
    corners = np.concatenate([
        a[:p, :p].reshape(-1, 3), a[:p, -p:].reshape(-1, 3),
        a[-p:, :p].reshape(-1, 3), a[-p:, -p:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    near_bg = np.abs(a - bg).max(axis=2) <= BG_TOLERANCE

    # Flood fill from every border pixel through near-background pixels;
    # whatever the flood cannot reach is foreground.
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
    return ~outside


# --- Silhouette helpers ----------------------------------------------------

def _runs(row):
    """Foreground runs in one boolean row, as (start, end) inclusive."""
    import numpy as np

    idx = np.flatnonzero(row)
    if len(idx) == 0:
        return []
    splits = np.where(np.diff(idx) > 1)[0]
    starts = np.concatenate([[0], splits + 1])
    ends = np.concatenate([splits, [len(idx) - 1]])
    return [(int(idx[s]), int(idx[e])) for s, e in zip(starts, ends)]


def _erode(mask, radius):
    """Binary erosion by a 3x3 square, ``radius`` iterations."""
    import numpy as np

    m = mask
    for _ in range(radius):
        padded = np.pad(m, 1, mode="constant", constant_values=False)
        m = (padded[:-2, :-2] & padded[:-2, 1:-1] & padded[:-2, 2:]
             & padded[1:-1, :-2] & padded[1:-1, 1:-1] & padded[1:-1, 2:]
             & padded[2:, :-2] & padded[2:, 1:-1] & padded[2:, 2:])
    return m


def _count_components(mask, min_area):
    """Connected foreground components via run-length union-find."""
    parent = {}

    def find(label):
        root = label
        while parent[root] != root:
            root = parent[root]
        while parent[label] != root:
            parent[label], label = root, parent[label]
        return root

    areas = {}
    prev = []
    next_label = 0
    for y in range(mask.shape[0]):
        current = []
        for start, end in _runs(mask[y]):
            label = None
            for p_start, p_end, p_label in prev:
                if p_start <= end + 1 and start <= p_end + 1:
                    if label is None:
                        label = p_label
                    else:
                        ra, rb = find(label), find(p_label)
                        if ra != rb:
                            parent[rb] = ra
            if label is None:
                label = next_label
                next_label += 1
                parent[label] = label
            current.append((start, end, label))
            root = find(label)
            areas[root] = areas.get(root, 0) + (end - start + 1)
        prev = current
    roots = {find(label) for label in list(parent)}
    return sum(1 for r in roots if areas.get(r, 0) >= min_area)


# --- Per-plan checks ---------------------------------------------------------

def _quadruped_check(sub, bw, bh):
    """Leg-separation metrics for a bbox-cropped mask."""
    import numpy as np

    widths = np.array([
        max((end - start + 1 for start, end in _runs(row)), default=0)
        for row in sub], dtype=float)
    widest = float(widths.max()) if len(widths) else 0.0
    metrics = {"widest_run_frac": round(widest / bw, 4) if bw else 0.0}
    reasons = []
    if widest <= 0:
        return metrics, reasons

    threshold = BELLY_WIDTH_FRAC * widest
    belly = None
    for y in range(bh - 1, BELLY_SUSTAIN_ROWS - 2, -1):
        if widths[y] >= threshold and all(
                widths[y - k] >= threshold
                for k in range(1, BELLY_SUSTAIN_ROWS)):
            belly = y
            break
    if belly is None:
        metrics.update({
            "belly_row_frac": 0.0,
            "leg_band_height_frac": 0.0,
            "leg_components_after_erosion": 0.0,
            "min_leg_gap_frac": 0.0,
            "erosion_radius_px": 0.0,
        })
        reasons.append(
            "no belly line found: no row reaches the solid body width "
            "sustained from below — the silhouette may be a single blob")
        return metrics, reasons

    band = sub[belly + 1:]
    band_h = band.shape[0]
    metrics["belly_row_frac"] = round(belly / bh, 4)
    metrics["leg_band_height_frac"] = round(band_h / bh, 4)
    if band_h < max(3, int(0.04 * bh)):
        metrics.update({
            "leg_components_after_erosion":
 0.0,
            "min_leg_gap_frac": 0.0,
            "erosion_radius_px": 0.0,
        })
        reasons.append(
            "no leg band below the belly line: the silhouette stays "
            "body-wide almost to the ground (legs fused into one mass, "
            "or the belly is resting on the ground)")
        return metrics, reasons

    radius = max(1, int(round(EROSION_FRAC * bw)))
    eroded = _erode(band, radius)
    min_area = max(16, int(MIN_COMPONENT_AREA_FRAC * band.size))
    components = _count_components(eroded, min_area)
    metrics["leg_components_after_erosion"] = float(components)
    metrics["erosion_radius_px"] = float(radius)

    gap_px_needed = MIN_GAP_FRAC * bw
    # Minimum adjacent-run gap at rows around mid-leg height; the
    # reported metric is the median of the three samples, so one
    # flared foot or a tail crossing a single row cannot carry it.
    min_gaps = []
    for frac in (0.35, 0.50, 0.65):
        row = band[min(band_h - 1, int(frac * band_h))]
        runs = _runs(row)
        gaps = [runs[i + 1][0] - runs[i][1] - 1
                for i in range(len(runs) - 1)]
        min_gaps.append(float(min(gaps)) if gaps else 0.0)
    metrics["min_leg_gap_frac"] = round(
        float(np.median(min_gaps)) / bw, 4)

    if components < QUAD_MIN_COMPONENTS:
        reasons.append(
            f"only {components} leg component(s) survive erosion in "
            f"the leg band (need {QUAD_MIN_COMPONENTS}+): legs read as "
            "one fused mass")
    if metrics["min_leg_gap_frac"] * bw < gap_px_needed:
        reasons.append(
            f"minimum leg gap at mid-leg height is "
            f"{metrics['min_leg_gap_frac']:.3f} of bbox width "
            f"(need >= {MIN_GAP_FRAC}): adjacent legs are touching or "
            "nearly touching")
    return metrics, reasons


def _biped_check(sub, bw, bh):
    """Arm-daylight metrics for a bbox-cropped mask (also used for
    winged plans, whose wing separation this heuristic does not see)."""
    lo = int(ARM_BAND[0] * bh)
    hi = int(ARM_BAND[1] * bh)
    gap_px_needed = max(2.0, MIN_GAP_FRAC * bw)
    rows_with_fg = 0
    daylight_rows = 0
    max_gap = 0
    for y in range(lo, max(lo + 1, hi)):
        runs = _runs(sub[y])
        if not runs:
            continue
        rows_with_fg += 1
        gaps = [runs[i + 1][0] - runs[i][1] - 1
                for i in range(len(runs) - 1)]
        if gaps:
            max_gap = max(max_gap, max(gaps))
            if max(gaps) >= gap_px_needed:
                daylight_rows += 1
    frac = (daylight_rows / rows_with_fg) if rows_with_fg else 0.0
    metrics = {
        "arm_daylight_row_frac": round(frac, 4),
        "arm_band_row_count": float(rows_with_fg),
        "arm_daylight_row_count": float(daylight_rows),
        "max_arm_gap_frac": round(max_gap / bw, 4) if bw else 0.0,
    }
    reasons = []
    if rows_with_fg == 0:
        reasons.append("no foreground in the arm band (rows "
                       "25%-65% of the silhouette height)")
    elif frac < BIPED_MIN_DAYLIGHT_ROW_FRAC:
        reasons.append(
            f"arm daylight on only {frac:.3f} of arm-band rows "
            f"(need >= {BIPED_MIN_DAYLIGHT_ROW_FRAC}): the arms read "
            "as fused with the torso — no background gap separates "
            "them along the arm")
    return metrics, reasons


# --- Public API --------------------------------------------------------------

def analyze_concept(image_path: str, body_plan: str) -> dict:
    """Pre-flight fused-limb check on one concept image.

    ``body_plan`` is one of "biped", "quadruped", "winged" (winged
    reuses the biped arm check and says so in its reasons). Returns
    {"verdict": "pass"|"warn", "body_plan": ..., "metrics": {...},
    "reasons": [...]}. Never raises for a bad *image* — unreadable or
    empty input is a warn — but an unknown body plan is a ValueError.
    """
    if body_plan not in BODY_PLANS:
        raise ValueError(
            f"body_plan must be one of {BODY_PLANS}, got {body_plan!r}")

    try:
        mask = _foreground_mask(image_path)
    except Exception as exc:  # unreadable file, unknown format, ...
        return {"verdict": "warn", "body_plan": body_plan,
                "metrics": {"foreground_fraction": 0.0},
                "reasons": [f"could not read concept image: {exc}"]}

    import numpy as np

    result = {"verdict": "warn", "body_plan": body_plan,
              "metrics": {}, "reasons": []}
    if mask is None or not mask.any():
        result["metrics"]["foreground_fraction"] = 0.0
        result["reasons"].append(
            "no foreground found: the image reads as empty background")
        return result

    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    result["metrics"]["foreground_fraction"] = round(
        float(mask.mean()), 4)
    if bw < 8 or bh < 8:
        result["reasons"].append(
            f"foreground is only {bw}x{bh}px: too small to assess")
        return result

    sub = mask[y0:y1 + 1, x0:x1 + 1]
    if body_plan == "quadruped":
        metrics, fail_reasons = _quadruped_check(sub, bw, bh)
    else:
        metrics, fail_reasons = _biped_check(sub, bw, bh)
    result["metrics"].update(metrics)
    result["reasons"].extend(fail_reasons)
    if not fail_reasons:
        result["verdict"] = "pass"
    if body_plan == "winged":
        # A note, not a finding: appended after the verdict is set so
        # it never reads as a failure reason.
        result["reasons"].append(
            "note: winged plan reuses the biped arm-daylight check; "
            "wing/torso separation is not assessed by this heuristic")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: preflight.py <image> <biped|quadruped|winged>")
    try:
        outcome = analyze_concept(sys.argv[1], sys.argv[2])
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(json.dumps(outcome, indent=1))
    raise SystemExit(0 if outcome["verdict"] == "pass" else 3)
