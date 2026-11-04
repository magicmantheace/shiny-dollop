"""Dialogue runtime semantics (F3.3): the speak `interrupt` field and the
precomputed dispatch schedule in studio/timing.py (compute_schedule) —
truncation, unchanged delay semantics, equal-timestamp dispatch priority —
plus schema acceptance/rejection of the field and parity with the JSON
Schema and the Godot preview's mirror in godot/main.gd.
"""
import copy
import json
import unittest
from pathlib import Path

from studio.schema import ValidationError, validate_scene
from studio.timing import compute_schedule

ROOT = Path(__file__).resolve().parents[1]

SPAWN = {"at_ms": 0, "op": "spawn", "actor_id": "solo", "position": [0, 0, 0]}


def scene_with(events):
    return {
        "schema_version": "1.0.0",
        "scene_id": "dialogue_scene",
        "environment_id": "preview_stage",
        "actors": [{"id": "solo", "recipe_id": "solo_01", "color": "#a1b2c3"}],
        "events": events,
    }


def speak(at_ms, line="Hello there.", **extra):
    event = {"at_ms": at_ms, "op": "speak", "actor_id": "solo", "line": line}
    event.update(extra)
    return event


def by_index(records):
    return {r["index"]: r for r in records}


class InterruptFieldValidationTests(unittest.TestCase):
    def test_interrupt_true_and_false_accepted(self):
        for value in (True, False):
            scene = scene_with([SPAWN, speak(10, interrupt=value)])
            with self.subTest(value=value):
                self.assertIs(validate_scene(scene), scene)

    def test_interrupt_absent_accepted(self):
        scene = scene_with([SPAWN, speak(10)])
        self.assertIs(validate_scene(scene), scene)

    def test_interrupt_non_bool_rejected(self):
        for bad in ("yes", 1, 0, None, 1.0):
            scene = scene_with([SPAWN, speak(10, interrupt=bad)])
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    validate_scene(scene)


class ScheduleDelayTests(unittest.TestCase):
    """Pre-F3.3 ADR-009 semantics must be unchanged for non-interrupts."""

    def test_non_interrupt_speak_delayed_to_hold_end(self):
        records = by_index(compute_schedule([
            SPAWN,
            speak(0, duration_ms=5000),
            speak(2000),
        ]))
        self.assertEqual(records[2]["effective_ms"], 5000)
        self.assertEqual(records[1]["window_start_ms"], 0)
        self.assertEqual(records[1]["window_end_ms"], 5000)
        self.assertFalse(records[1]["interrupted"])
        self.assertIsNone(records[2]["interrupts"])

    def test_move_delayed_by_hold_but_camera_never_gated(self):
        records = by_index(compute_schedule([
            SPAWN,
            speak(0, duration_ms=5000),
            {"at_ms": 2000, "op": "move", "actor_id": "solo", "target": [1, 0, 0], "duration_ms": 500},
            {"at_ms": 2000, "op": "camera", "shot": "wide"},
        ]))
        self.assertEqual(records[2]["effective_ms"], 5000)
        self.assertEqual(records[3]["effective_ms"], 2000)

    def test_other_actor_not_gated(self):
        records = by_index(compute_schedule([
            SPAWN,
            {"at_ms": 0, "op": "spawn", "actor_id": "duo", "position": [2, 0, 0]},
            speak(0, duration_ms=5000),
            {"at_ms": 2000, "op": "speak", "actor_id": "duo", "line": "My turn."},
        ]))
        self.assertEqual(records[3]["effective_ms"], 2000)


class InterruptScheduleTests(unittest.TestCase):
    def test_interrupt_truncates_current_window(self):
        records = by_index(compute_schedule([
            SPAWN,
            speak(0, duration_ms=5000),
            speak(2000, interrupt=True),
        ]))
        first, second = records[1], records[2]
        self.assertEqual(first["window_start_ms"], 0)
        self.assertEqual(first["window_end_ms"], 2000)
        self.assertTrue(first["interrupted"])
        self.assertEqual(first["hold_ms"], 5000)  # hold as authored is kept
        self.assertEqual(second["effective_ms"], 2000)
        self.assertEqual(second["interrupts"], 1)
        self.assertEqual(second["window_start_ms"], 2000)
        self.assertEqual(second["window_end_ms"], 2000 + second["hold_ms"])

    def test_interrupt_after_hold_end_is_noop(self):
        records = by_index(compute_schedule([
            SPAWN,
            speak(0, duration_ms=5000),
            speak(6000, interrupt=True),
        ]))
        self.assertEqual(records[1]["window_end_ms"], 5000)
        self.assertFalse(records[1]["interrupted"])
        self.assertEqual(records[2]["effective_ms"], 6000)
        self.assertIsNone(records[2]["interrupts"])

    def test_interrupt_exactly_at_window_end_is_noop(self):
        records = by_index(compute_schedule([
            SPAWN,
            speak(0, duration_ms=5000),
            speak(5000, interrupt=True),
        ]))
        self.assertFalse(records[1]["interrupted"])
        self.assertEqual(records[2]["effective_ms"], 5000)

    def test_chained_interrupts(self):
        records = by_index(compute_schedule([
            SPAWN,
            speak(0, duration_ms=5000),
            speak(2000, duration_ms=4000, interrupt=True),
            speak(3000, interrupt=True),
        ]))
        self.assertEqual(records[1]["window_end_ms"], 2000)
        self.assertTrue(records[1]["interrupted"])
        self.assertEqual(records[2]["window_start_ms"], 2000)
        self.assertEqual(records[2]["window_end_ms"], 3000)
        self.assertTrue(records[2]["interrupted"])
        self.assertEqual(records[2]["interrupts"], 1)
        self.assertEqual(records[3]["effective_ms"], 3000)
        self.assertEqual(records[3]["interrupts"], 2)

    def test_interrupt_truncates_derived_hold(self):
        line = "x" * 75  # derived hold 5000 ms at the default rate
        records = by_index(compute_schedule([
            SPAWN,
            speak(0, line=line),
            speak(2500, interrupt=True),
        ]))
        self.assertEqual(records[1]["hold_ms"], 5000)
        self.assertEqual(records[1]["window_end_ms"], 2500)
        self.assertTrue(records[1]["interrupted"])

    def test_interrupt_without_open_window_is_plain_speak(self):
        records = by_index(compute_schedule([
            SPAWN,
            speak(1000, interrupt=True),
        ]))
        self.assertEqual(records[1]["effective_ms"], 1000)
        self.assertIsNone(records[1]["interrupts"])
        self.assertFalse(records[1]["interrupted"])

    def test_interrupt_does_not_cut_other_actor(self):
        records = by_index(compute_schedule([
            SPAWN,
            {"at_ms": 0, "op": "spawn", "actor_id": "duo", "position": [2, 0, 0]},
            speak(0, duration_ms=5000),
            {"at_ms": 2000, "op": "speak", "actor_id": "duo", "line": "Cutting in.", "interrupt": True},
        ]))
        self.assertEqual(records[2]["window_end_ms"], 5000)
        self.assertFalse(records[2]["interrupted"])
        self.assertEqual(records[3]["effective_ms"], 2000)

    def test_later_event_uses_truncated_window_end(self):
        records = by_index(compute_schedule([
            SPAWN,
            speak(0, duration_ms=5000),
            speak(2000, duration_ms=1000, interrupt=True),
            {"at_ms": 2500, "op": "emote", "actor_id": "solo", "emotion": "happy", "intensity": 0.5},
        ]))
        # Without the truncation the emote would wait until 5000; the
        # interrupting speak's window ends at 3000, so it lands there.
        self.assertEqual(records[3]["effective_ms"], 3000)

    def test_input_events_are_not_mutated(self):
        events = [dict(SPAWN), speak(0, duration_ms=5000), speak(2000, interrupt=True)]
        snapshot = copy.deepcopy(events)
        compute_schedule(events)
        self.assertEqual(events, snapshot)


class DispatchPriorityTests(unittest.TestCase):
    def test_camera_beats_speak_at_same_time_despite_scene_order(self):
        records = compute_schedule([
            SPAWN,
            speak(1000),
            {"at_ms": 1000, "op": "camera", "shot": "wide"},
        ])
        order = [r["index"] for r in records if r["effective_ms"] == 1000]
        self.assertEqual(order, [2, 1])  # camera (index 2) before speak (index 1)

    def test_spawn_beats_speak_at_same_time(self):
        records = compute_schedule([
            speak(0, line="Too soon."),  # schedule math only; validation is separate
            {"at_ms": 0, "op": "spawn", "actor_id": "solo", "position": [0, 0, 0]},
        ])
        self.assertEqual([r["op"] for r in records], ["spawn", "speak"])

    def test_same_priority_falls_back_to_scene_order(self):
        records = compute_schedule([
            SPAWN,
            {"at_ms": 1000, "op": "emote", "actor_id": "solo", "emotion": "happy", "intensity": 0.5},
            speak(1000),
        ])
        order = [r["index"] for r in records if r["effective_ms"] == 1000]
        self.assertEqual(order, [1, 2])


class ParityTests(unittest.TestCase):
    def test_scene_schema_carries_interrupt_as_boolean(self):
        doc = json.loads((ROOT / "schemas" / "scene.schema.json").read_text(encoding="utf-8"))
        prop = doc["properties"]["events"]["items"]["properties"]["interrupt"]
        self.assertEqual(prop["type"], "boolean")

    def test_godot_preview_mirrors_interrupt_and_priority(self):
        gd = (ROOT / "godot" / "main.gd").read_text(encoding="utf-8")
        self.assertIn("_dispatch_priority", gd)
        self.assertIn("Speak interrupted for ", gd)
        self.assertIn("Dispatch skipped:", gd)
        self.assertIn("compute_schedule in studio/timing.py", gd)


if __name__ == "__main__":
    unittest.main()
