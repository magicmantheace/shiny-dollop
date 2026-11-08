"""Tests for the concept pre-flight fused-limb check.

Pure PIL/numpy: every case is a small synthetic silhouette drawn on
white, shaped to the geometry the check claims to measure (see
stages/prep/preflight.py's docstring). The real-concept calibration
(the spec-posed giraffe passes, the fused Snow Goblin warns) is a
one-off proof recorded in the P2 cleanup notes, not a unit test —
those images live outside the repo.

The module is loaded by file path because ``stages`` (the registry
module, stages.py) and the ``stages/`` directory share a name by
design — same pattern as test_pipeline_units.py.
"""

import importlib.util
import os

import pytest
from PIL import Image, ImageDraw

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PROJECT, relpath))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preflight = _load("gab_preflight", "stages/prep/preflight.py")

DARK = (60, 60, 60)
WHITE = (255, 255, 255)


def _save(draw_fn, size, tmp_path, name):
    img = Image.new("RGB", size, WHITE)
    draw_fn(ImageDraw.Draw(img))
    path = tmp_path / name
    img.save(path)
    return str(path)


def _quadruped_separated(d):
    # Body, head, and four legs with clear background between them.
    d.rectangle([100, 80, 380, 190], fill=DARK)          # body
    d.ellipse([320, 25, 385, 85], fill=DARK)             # head
    d.rectangle([335, 70, 360, 85], fill=DARK)           # neck stub
    for x in (130, 205, 280, 340):
        d.rectangle([x, 190, x + 34, 300], fill=DARK)    # legs


def _quadruped_block_legs(d):
    # Same body, but the "legs" are one solid slab to the ground.
    d.rectangle([100, 80, 380, 190], fill=DARK)
    d.ellipse([320, 25, 385, 85], fill=DARK)
    d.rectangle([335, 70, 360, 85], fill=DARK)
    d.rectangle([170, 190, 310, 300], fill=DARK)


def _biped_arms_out(d):
    # A-pose: head, torso, arms angled away with daylight under the
    # shoulder join, legs apart.
    d.ellipse([170, 30, 230, 90], fill=DARK)             # head
    d.rectangle([165, 95, 235, 300], fill=DARK)          # torso
    d.line([(166, 118), (82, 295)], fill=DARK, width=24)   # arm L
    d.line([(234, 118), (318, 295)], fill=DARK, width=24)  # arm R
    d.line([(182, 300), (172, 430)], fill=DARK, width=26)  # leg L
    d.line([(218, 300), (228, 430)], fill=DARK, width=26)  # leg R


def _biped_arms_fused(d):
    # One fur-mass silhouette: arms are bumps merged into the torso
    # ellipse, no background gap anywhere along them.
    d.ellipse([170, 30, 230, 90], fill=DARK)             # head
    d.ellipse([150, 95, 250, 310], fill=DARK)            # torso mass
    d.ellipse([105, 130, 185, 300], fill=DARK)           # arm L, merged
    d.ellipse([215, 130, 295, 300], fill=DARK)           # arm R, merged
    d.rectangle([150, 300, 195, 430], fill=DARK)         # leg L
    d.rectangle([205, 300, 250, 430], fill=DARK)         # leg R


def test_quadruped_separated_legs_pass(tmp_path):
    path = _save(_quadruped_separated, (480, 340), tmp_path, "q_sep.png")
    result = preflight.analyze_concept(path, "quadruped")
    assert result["verdict"] == "pass", result
    assert result["metrics"]["leg_components_after_erosion"] >= 3
    assert result["metrics"]["min_leg_gap_frac"] >= 0.02


def test_quadruped_block_legs_warn(tmp_path):
    path = _save(_quadruped_block_legs, (480, 340), tmp_path, "q_blk.png")
    result = preflight.analyze_concept(path, "quadruped")
    assert result["verdict"] == "warn", result
    assert result["reasons"]


def test_biped_arms_out_pass(tmp_path):
    path = _save(_biped_arms_out, (400, 480), tmp_path, "b_out.png")
    result = preflight.analyze_concept(path, "biped")
    assert result["verdict"] == "pass", result
    assert result["metrics"]["arm_daylight_row_frac"] >= 0.40


def test_biped_arms_fused_warn(tmp_path):
    path = _save(_biped_arms_fused, (400, 480), tmp_path, "b_fuse.png")
    result = preflight.analyze_concept(path, "biped")
    assert result["verdict"] == "warn", result
    assert result["metrics"]["arm_daylight_row_frac"] < 0.40


def test_empty_image_warns_without_raising(tmp_path):
    path = _save(lambda d: None, (200, 200), tmp_path, "empty.png")
    for plan in ("biped", "quadruped", "winged"):
        result = preflight.analyze_concept(path, plan)
        assert result["verdict"] == "warn", result
        assert result["reasons"]


def test_winged_reuses_biped_check_and_says_so(tmp_path):
    path = _save(_biped_arms_out, (400, 480), tmp_path, "w_out.png")
    result = preflight.analyze_concept(path, "winged")
    assert result["verdict"] == "pass", result
    assert any(r.startswith("note:") for r in result["reasons"])


def test_unknown_body_plan_raises(tmp_path):
    path = _save(_biped_arms_out, (400, 480), tmp_path, "b_out2.png")
    with pytest.raises(ValueError):
        preflight.analyze_concept(path, "hexapod")
