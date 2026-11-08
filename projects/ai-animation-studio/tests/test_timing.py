"""Speak timing semantics (ADR-009): the derivation in studio/timing.py is
the shared quantity the Godot preview schedules with. These tests pin the
derivation, the clamps, the explicit-duration override, the changeable
rate/clamp variables, scene-level validation of the `timing` object and
speak `duration_ms`, and parity between the Python defaults, the JSON
Schema, and the preview's exported settings in godot/main.gd.
"""
import json
import re
import unittest
from pathlib import Path

from studio.schema import ValidationError, validate_scene
from studio.timing import (
    DEFAULT_SPEAK_CHARS_PER_SECOND,
    DEFAULT_SPEAK_MAX_HOLD_MS,
    DEFAULT_SPEAK_MIN_HOLD_MS,
    DEFAULT_TIMING,
    TIMING_KEYS,
    TimingConfig,
    resolve_timing,
    speak_hold_ms,
)

ROOT = Path(__file__).resolve().parents[1]


def scene_with(events, timing_marker=object(), timing=None):
    scene = {
        "schema_version": "1.0.0",
        "scene_id": "timing_scene",
        "environment_id": "preview_stage",
        "actors": [{"id": "solo", "recipe_id": "solo_01", "color": "#a1b2c3"}],
        "events": events,
    }
    if timing_marker is not None:
        scene["timing"] = timing
    return scene


SPAWN = {"at_ms": 0, "op": "spawn", "actor_id": "solo", "position": [0, 0, 0]}


class DerivationTests(unittest.TestCase):
    def test_derived_hold_millisecond_precision(self):
        # 43 chars at 15 chars/sec -> ceil(43000/15) = 2867 ms (protocol demo check).
        self.assertEqual(speak_hold_ms("x" * 43), 2867)
        self.assertEqual(speak_hold_ms("x" * 45), 3000)
        self.assertEqual(speak_hold_ms("x" * 30), 2000)

    def test_min_clamp(self):
        self.assertEqual(speak_hold_ms("Hi"), DEFAULT_SPEAK_MIN_HOLD_MS)

    def test_max_clamp(self):
        self.assertEqual(speak_hold_ms("x" * 500), DEFAULT_SPEAK_MAX_HOLD_MS)

    def test_explicit_duration_wins(self):
        self.assertEqual(speak_hold_ms("x" * 500, 5000), 5000)
        self.assertEqual(speak_hold_ms("Hi", 100), 100)

    def test_explicit_duration_bounds(self):
        for bad in (99, 60001, "5000", 5000.5, True, 0, -5):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    speak_hold_ms("Hello.", bad)

    def test_rate_is_a_variable(self):
        fast = TimingConfig(speak_chars_per_second=30.0)
        self.assertEqual(speak_hold_ms("x" * 45, timing=fast), 1500)
        slow = TimingConfig(speak_chars_per_second=7.5)
        self.assertEqual(speak_hold_ms("x" * 45, timing=slow), 6000)

    def test_clamps_are_variables(self):
        cfg = TimingConfig(speak_min_hold_ms=250, speak_max_hold_ms=4000)
        self.assertEqual(speak_hold_ms("Hi", timing=cfg), 250)
        self.assertEqual(speak_hold_ms("x" * 500, timing=cfg), 4000)


class ResolveTimingTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(resolve_timing(None), DEFAULT_TIMING)
        self.assertEqual(resolve_timing({}), DEFAULT_TIMING)
        self.assertEqual(DEFAULT_TIMING.speak_chars_per_second, 15.0)
        self.assertEqual(DEFAULT_TIMING.speak_min_hold_ms, 800)
        self.assertEqual(DEFAULT_TIMING.speak_max_hold_ms, 15000)

    def test_partial_override(self):
        cfg = resolve_timing({"speak_chars_per_second": 20})
        self.assertEqual(cfg.speak_chars_per_second, 20.0)
        self.assertEqual(cfg.speak_min_hold_ms, 800)

    def test_rejections(self):
        for bad in (
            "fast",
            {"bogus_key": 1},
            {"speak_chars_per_second": 0},
            {"speak_chars_per_second": 101},
            {"speak_chars_per_second": True},
            {"speak_min_hold_ms": -1},
            {"speak_max_hold_ms": 60001},
            {"speak_min_hold_ms": 5000, "speak_max_hold_ms": 1000},
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    resolve_timing(bad)


class SceneValidationTests(unittest.TestCase):
    def test_scene_with_timing_accepted(self):
        scene = scene_with(
            [SPAWN, {"at_ms": 10, "op": "speak", "actor_id": "solo", "line": "Hello."}],
            timing={"speak_chars_per_second": 30, "speak_min_hold_ms": 500},
        )
        self.assertIs(validate_scene(scene), scene)

    def test_scene_without_timing_accepted(self):
        scene = scene_with(
            [SPAWN, {"at_ms": 10, "op": "speak", "actor_id": "solo", "line": "Hello."}],
            timing_marker=None,
        )
        self.assertIs(validate_scene(scene), scene)

    def test_scene_with_bad_timing_rejected(self):
        scene = scene_with([SPAWN], timing={"speak_min_hold_ms": 9000, "speak_max_hold_ms": 1000})
        with self.assertRaises(ValidationError):
            validate_scene(scene)

    def test_speak_explicit_duration_accepted(self):
        scene = scene_with(
            [SPAWN, {"at_ms": 10, "op": "speak", "actor_id": "solo", "line": "Hello.", "duration_ms": 5000}],
            timing_marker=None,
        )
        self.assertIs(validate_scene(scene), scene)

    def test_speak_bad_duration_rejected(self):
        for bad in (99, 60001, "5000"):
            scene = scene_with(
                [SPAWN, {"at_ms": 10, "op": "speak", "actor_id": "solo", "line": "Hello.", "duration_ms": bad}],
                timing_marker=None,
            )
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    validate_scene(scene)


class ParityTests(unittest.TestCase):
    def test_scene_schema_carries_timing_keys(self):
        doc = json.loads((ROOT / "schemas" / "scene.schema.json").read_text(encoding="utf-8"))
        timing_props = doc["properties"]["timing"]["properties"]
        self.assertEqual(set(timing_props), set(TIMING_KEYS))

    def test_godot_exported_defaults_match_python(self):
        gd = (ROOT / "godot" / "main.gd").read_text(encoding="utf-8")
        rate = re.search(r"@export var speak_chars_per_second: float = ([0-9.]+)", gd)
        min_hold = re.search(r"@export var speak_min_hold_ms: int = ([0-9]+)", gd)
        max_hold = re.search(r"@export var speak_max_hold_ms: int = ([0-9]+)", gd)
        self.assertIsNotNone(rate, "main.gd must export speak_chars_per_second")
        self.assertIsNotNone(min_hold, "main.gd must export speak_min_hold_ms")
        self.assertIsNotNone(max_hold, "main.gd must export speak_max_hold_ms")
        self.assertEqual(float(rate.group(1)), DEFAULT_SPEAK_CHARS_PER_SECOND)
        self.assertEqual(int(min_hold.group(1)), DEFAULT_SPEAK_MIN_HOLD_MS)
        self.assertEqual(int(max_hold.group(1)), DEFAULT_SPEAK_MAX_HOLD_MS)


if __name__ == "__main__":
    unittest.main()
