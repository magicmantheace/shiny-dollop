"""P4 gait-animation tests: invariants of the procedural locomotion
model in stages/animate/poses.py and clip presence/durations in the
regenerated catalog GLBs (via stages/animate/glb_clips.py).

The pose-model tests are hermetic. The GLB tests read the real
outputs/<slug>/<slug>.glb files when they exist (generated outputs
are local-only, never in git) and skip otherwise; a synthetic-GLB
test keeps the clip reader itself covered everywhere.
"""

import importlib.util
import json
import os
import struct
import sys
import unittest

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, rel):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PROJECT, rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


poses = load("gab_poses_t", "stages/animate/poses.py")
glb_clips = load("gab_glb_clips_t", "stages/animate/glb_clips.py")

FPS = 24
# template -> (walk seconds, run seconds, leg channels, fold channels)
GAITS = {
    "winged-creature": (1.5, 1.0, ("leg.L", "leg.R"), ()),
    "biped": (1.5, 1.0, ("leg.L", "leg.R"), ("leg2.L", "leg2.R")),
    "quadruped": (2.0, 1.0,
                  ("leg.FL", "leg.FR", "leg.HL", "leg.HR"),
                  ("leg2.FL", "leg2.FR", "leg2.HL", "leg2.HR")),
    "winged-quadruped": (2.0, 1.0,
                          ("leg.FL", "leg.FR", "leg.HL", "leg.HR"),
                          ("leg2.FL", "leg2.FR", "leg2.HL", "leg2.HR")),
}


def recipe_fn(template, clip):
    return poses.template_spec(template)["recipes"][clip]


class GaitRegistryTests(unittest.TestCase):
    def test_every_template_has_walk_and_run(self):
        for template, (walk_s, run_s, _l, _f) in GAITS.items():
            recipes = poses.template_spec(template)["recipes"]
            self.assertIn("walk", recipes, template)
            self.assertIn("run", recipes, template)
            self.assertEqual(recipes["walk"][1], walk_s, template)
            self.assertEqual(recipes["run"][1], run_s, template)

    def test_gait_recipes_cover_exactly_the_template_channels(self):
        for template in GAITS:
            spec = poses.template_spec(template)
            for clip in ("walk", "run"):
                fn, _ = spec["recipes"][clip]
                self.assertEqual(set(fn(0.3)), set(spec["channels"]),
                                 f"{template}/{clip}")


class GaitLoopTests(unittest.TestCase):
    def test_loop_closure_pose_zero_equals_pose_period(self):
        for template, spec in poses.TEMPLATE_RECIPES.items():
            for clip in poses.LOCOMOTION[template]:
                fn, seconds = spec["recipes"][clip]
                start, end = fn(0.0), fn(seconds)
                for channel in spec["channels"]:
                    self.assertAlmostEqual(
                        start[channel], end[channel], places=6,
                        msg=f"{template}/{clip}/{channel}")

    def test_baked_last_frame_matches_first_frame_step(self):
        # The sampler keys frames 1..N; the wrap from frame N back to
        # frame 1 must be one ordinary frame step, not a jump.
        for template in GAITS:
            for clip in ("walk", "run"):
                samples = poses.sample_for(template, clip, fps=FPS)
                fn, seconds = recipe_fn(template, clip)
                last_pose = samples[-1][1]
                wrapped = fn(0.0)
                for channel, value in last_pose.items():
                    self.assertAlmostEqual(
                        value, wrapped[channel], places=6,
                        msg=f"{template}/{clip}/{channel} wrap")


class GaitPhaseTests(unittest.TestCase):
    def test_biped_legs_are_antiphase_and_arms_counter_swing(self):
        fn, period = recipe_fn("biped", "walk")
        for i in range(0, 37):
            pose = fn(i * period / 36)
            self.assertAlmostEqual(pose["leg.L"], -pose["leg.R"])
            self.assertAlmostEqual(pose["arm.L"], -pose["arm.R"])
            # arm opposes the same-side leg
            self.assertLessEqual(pose["arm.L"] * pose["leg.L"], 0.0)

    def test_winged_legs_are_antiphase(self):
        fn, period = recipe_fn("winged-creature", "walk")
        for i in range(0, 31):
            pose = fn(i * period / 30)
            self.assertAlmostEqual(pose["leg.L"], -pose["leg.R"])
            self.assertAlmostEqual(pose["arm.L"], -pose["arm.R"])

    def test_quadruped_walk_uses_lateral_sequence_offsets(self):
        fn, period = recipe_fn("quadruped", "walk")
        for corner, off in poses.QUAD_WALK_OFFSETS.items():
            for i in range(0, 9):
                t = i * period / 8
                # corner's phase at t equals FL's phase at t + off*P
                shifted = fn(t + off * period)
                self.assertAlmostEqual(
                    fn(t)[f"leg.{corner}"], shifted["leg.FL"],
                    places=6, msg=f"{corner} offset {off}")

    def test_quadruped_run_fronts_and_hinds_move_in_pairs(self):
        fn, period = recipe_fn("quadruped", "run")
        for i in range(0, 21):
            pose = fn(i * period / 20)
            self.assertAlmostEqual(pose["leg.FL"], pose["leg.FR"])
            self.assertAlmostEqual(pose["leg.HL"], pose["leg.HR"])
            self.assertAlmostEqual(pose["leg.FL"], -pose["leg.HL"])

    def test_fold_is_zero_in_mid_stance_and_positive_in_swing(self):
        for phase in (0.45, 0.5, 0.55, 0.65):
            self.assertEqual(poses.gait_fold(phase), 0.0, phase)
        self.assertGreater(poses.gait_fold(0.13), 0.9)
        for template in ("biped", "quadruped"):
            fn, period = recipe_fn(template, "walk")
            _w, _r, _legs, folds = GAITS[template]
            for i in range(0, 49):
                pose = fn(i * period / 48)
                for channel in folds:
                    self.assertGreaterEqual(pose[channel], 0.0,
                                            channel)

    def test_run_is_faster_and_bigger_than_walk(self):
        for template, spec in poses.TEMPLATE_RECIPES.items():
            if template not in GAITS:
                continue  # snail: glide only, no walk/run pair
            walk_fn, walk_s = spec["recipes"]["walk"]
            run_fn, run_s = spec["recipes"]["run"]
            self.assertLess(run_s, walk_s, template)
            _w, _r, legs, _f = GAITS[template]
            walk_peak = max(abs(walk_fn(i * walk_s / 96)[legs[0]])
                            for i in range(97))
            run_peak = max(abs(run_fn(i * run_s / 96)[legs[0]])
                           for i in range(97))
            self.assertGreater(run_peak, walk_peak, template)


def _synthetic_glb() -> bytes:
    """Minimal GLB: one animation whose time accessor tops at 1.5 s."""
    times = struct.pack("<4f", 0.0, 0.5, 1.0, 1.5)
    gltf = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(times)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0,
                         "byteLength": len(times)}],
        "accessors": [{"bufferView": 0, "componentType": 5126,
                       "count": 4, "type": "SCALAR",
                       "min": [0.0], "max": [1.5]}],
        "animations": [{"name": "walk", "channels": [],
                        "samplers": [{"input": 0, "output": 0}]}],
    }
    js = json.dumps(gltf).encode()
    js += b" " * (-len(js) % 4)
    binp = times + b"\x00" * (-len(times) % 4)
    body = (struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(binp), 0x004E4942) + binp)
    return b"glTF" + struct.pack("<II", 2, 12 + len(body)) + body


class GlbClipReaderTests(unittest.TestCase):
    def test_reads_synthetic_glb(self):
        import tempfile
        with tempfile.NamedTemporaryFile(
                suffix=".glb", delete=False) as fh:
            fh.write(_synthetic_glb())
            path = fh.name
        try:
            self.assertEqual(glb_clips.read_glb_animations(path),
                             {"walk": 1.5})
        finally:
            os.unlink(path)


EXPECTED_CLIPS = {
    "ember-dragon": {"idle": 4.8, "hop": 1.24, "walk": 1.5, "run": 1.0},
    "snow-goblin": {"idle": 4.8, "wave": 2.4, "walk": 1.5, "run": 1.0},
    "triceratops": {"idle": 4.8, "bounce": 1.24, "walk": 2.0,
                    "run": 1.0},
}


@unittest.skipUnless(
    all(os.path.exists(os.path.join(PROJECT, "outputs", slug,
                                     f"{slug}.glb"))
        for slug in EXPECTED_CLIPS),
    "regenerated catalog GLBs not present in outputs/")
class RegeneratedGlbTests(unittest.TestCase):
    def test_clips_present_with_expected_durations(self):
        for slug, expected in EXPECTED_CLIPS.items():
            path = os.path.join(PROJECT, "outputs", slug, f"{slug}.glb")
            clips = glb_clips.read_glb_animations(path)
            self.assertEqual(set(clips), set(expected), slug)
            for name, seconds in expected.items():
                self.assertAlmostEqual(clips[name], seconds,
                                       delta=0.06, msg=f"{slug}/{name}")
                self.assertGreater(clips[name], 0.0)


if __name__ == "__main__":
    unittest.main()
