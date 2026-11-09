"""Gaze + animation layering (F4.1): the `look_at` field on speak/emote/move
events — schema acceptance/rejection, JSON Schema parity, the gaze windows
in studio/timing.py compute_schedule (gaze follows the scheduled window,
never changes it) — plus markers for the Godot preview's mirror: two-layer
playback (base player + upper-body overlay) and head-bone gaze in
godot/main.gd. The headless probe evidence is recorded in
docs/IMPLEMENTATION_STATUS.md, F4 slice 1.
"""
import json
import unittest
from pathlib import Path

from studio.schema import ValidationError, validate_scene
from studio.timing import compute_schedule

ROOT = Path(__file__).resolve().parents[1]

SPAWN_ANNA = {"at_ms": 0, "op": "spawn", "actor_id": "anna", "position": [-2, 0, 2]}
SPAWN_BORIS = {"at_ms": 0, "op": "spawn", "actor_id": "boris", "position": [2, 0, -2]}


def scene_with(events):
    return {
        "schema_version": "1.0.0",
        "scene_id": "gaze_scene",
        "environment_id": "preview_stage",
        "actors": [
            {"id": "anna", "recipe_id": "anna_01", "color": "#a1b2c3"},
            {"id": "boris", "recipe_id": "boris_01", "color": "#c3b2a1"},
        ],
        "events": events,
    }


def speak(at_ms, actor="anna", **extra):
    event = {"at_ms": at_ms, "op": "speak", "actor_id": actor, "line": "Hello there."}
    event.update(extra)
    return event


def emote(at_ms, actor="anna", **extra):
    event = {"at_ms": at_ms, "op": "emote", "actor_id": actor,
             "emotion": "happy", "intensity": 0.5}
    event.update(extra)
    return event


def move(at_ms, actor="anna", **extra):
    event = {"at_ms": at_ms, "op": "move", "actor_id": actor,
             "target": [0, 0, 0], "duration_ms": 1000}
    event.update(extra)
    return event


def by_index(records):
    return {r["index"]: r for r in records}


class LookAtValidationTests(unittest.TestCase):
    def test_actor_target_accepted_on_speak_emote_move(self):
        for event in (speak(10, look_at={"actor_id": "boris"}),
                      emote(10, look_at={"actor_id": "boris"}),
                      move(10, look_at={"actor_id": "boris"})):
            scene = scene_with([SPAWN_ANNA, SPAWN_BORIS, event])
            with self.subTest(op=event["op"]):
                self.assertIs(validate_scene(scene), scene)

    def test_position_target_accepted_on_speak_emote_move(self):
        for event in (speak(10, look_at={"position": [10, 0, 10]}),
                      emote(10, look_at={"position": [10, 0, 10]}),
                      move(10, look_at={"position": [10, 0, 10]})):
            scene = scene_with([SPAWN_ANNA, SPAWN_BORIS, event])
            with self.subTest(op=event["op"]):
                self.assertIs(validate_scene(scene), scene)

    def test_look_at_refused_on_spawn_and_camera(self):
        spawn = dict(SPAWN_ANNA, look_at={"actor_id": "boris"})
        with self.assertRaises(ValidationError):
            validate_scene(scene_with([spawn, SPAWN_BORIS]))
        camera = {"at_ms": 10, "op": "camera", "shot": "wide",
                  "look_at": {"actor_id": "anna"}}
        with self.assertRaises(ValidationError):
            validate_scene(scene_with([SPAWN_ANNA, SPAWN_BORIS, camera]))

    def test_both_targets_refused(self):
        scene = scene_with([SPAWN_ANNA, SPAWN_BORIS,
                            speak(10, look_at={"actor_id": "boris",
                                               "position": [0, 0, 0]})])
        with self.assertRaises(ValidationError):
            validate_scene(scene)

    def test_neither_target_refused(self):
        scene = scene_with([SPAWN_ANNA, SPAWN_BORIS, speak(10, look_at={})])
        with self.assertRaises(ValidationError):
            validate_scene(scene)

    def test_unknown_key_refused(self):
        scene = scene_with([SPAWN_ANNA, SPAWN_BORIS,
                            speak(10, look_at={"actor_id": "boris", "speed": 2})])
        with self.assertRaises(ValidationError):
            validate_scene(scene)

    def test_non_object_refused(self):
        for bad in ("boris", ["boris"], 3, None):
            scene = scene_with([SPAWN_ANNA, SPAWN_BORIS, speak(10, look_at=bad)])
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    validate_scene(scene)

    def test_unknown_target_actor_refused(self):
        scene = scene_with([SPAWN_ANNA, SPAWN_BORIS,
                            speak(10, look_at={"actor_id": "carol"})])
        with self.assertRaises(ValidationError):
            validate_scene(scene)

    def test_bad_target_id_shape_refused(self):
        scene = scene_with([SPAWN_ANNA, SPAWN_BORIS,
                            speak(10, look_at={"actor_id": "Boris"})])
        with self.assertRaises(ValidationError):
            validate_scene(scene)

    def test_bad_position_refused(self):
        for bad in ([0, 0], [0, 0, 0, 0], [0, 0, 2000], "origin"):
            scene = scene_with([SPAWN_ANNA, SPAWN_BORIS,
                                speak(10, look_at={"position": bad})])
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    validate_scene(scene)

    def test_self_target_accepted(self):
        scene = scene_with([SPAWN_ANNA, SPAWN_BORIS,
                            speak(10, look_at={"actor_id": "anna"})])
        self.assertIs(validate_scene(scene), scene)


class GazeWindowTests(unittest.TestCase):
    def test_speak_gaze_window_is_occupancy_window(self):
        records = by_index(compute_schedule([
            SPAWN_ANNA, SPAWN_BORIS,
            speak(1000, duration_ms=3000, look_at={"actor_id": "boris"}),
        ]))
        record = records[2]
        self.assertEqual(record["look_at"], {"actor_id": "boris"})
        self.assertEqual(record["gaze_window_start_ms"], 1000)
        self.assertEqual(record["gaze_window_end_ms"], 4000)

    def test_speak_gaze_window_follows_interrupt_truncation(self):
        records = by_index(compute_schedule([
            SPAWN_ANNA, SPAWN_BORIS,
            speak(0, duration_ms=5000, look_at={"actor_id": "boris"}),
            speak(2000, interrupt=True),
        ]))
        self.assertEqual(records[2]["gaze_window_start_ms"], 0)
        self.assertEqual(records[2]["gaze_window_end_ms"], 2000)

    def test_move_gaze_window_is_duration_window(self):
        records = by_index(compute_schedule([
            SPAWN_ANNA, SPAWN_BORIS,
            move(500, duration_ms=2500, look_at={"position": [10, 0, 10]}),
        ]))
        record = records[2]
        self.assertEqual(record["gaze_window_start_ms"], 500)
        self.assertEqual(record["gaze_window_end_ms"], 3000)

    def test_move_gaze_window_uses_delayed_effective_start(self):
        records = by_index(compute_schedule([
            SPAWN_ANNA, SPAWN_BORIS,
            speak(0, duration_ms=5000),
            move(2000, duration_ms=1000, look_at={"actor_id": "boris"}),
        ]))
        record = records[3]
        self.assertEqual(record["effective_ms"], 5000)
        self.assertEqual(record["gaze_window_start_ms"], 5000)
        self.assertEqual(record["gaze_window_end_ms"], 6000)

    def test_emote_gaze_runs_until_next_same_actor_event(self):
        records = by_index(compute_schedule([
            SPAWN_ANNA, SPAWN_BORIS,
            emote(1000, look_at={"actor_id": "boris"}),
            speak(3000, actor="boris"),
            speak(4000),
        ]))
        record = records[2]
        self.assertEqual(record["gaze_window_start_ms"], 1000)
        # Boris's speak at 3000 does not close Anna's gaze; Anna's own
        # next event (speak at 4000) does.
        self.assertEqual(record["gaze_window_end_ms"], 4000)

    def test_emote_gaze_as_last_event_runs_to_schedule_end(self):
        records = by_index(compute_schedule([
            SPAWN_ANNA, SPAWN_BORIS,
            speak(1000, actor="boris", duration_ms=6000),
            emote(2000, look_at={"actor_id": "boris"}),
        ]))
        record = records[3]
        self.assertEqual(record["gaze_window_start_ms"], 2000)
        self.assertEqual(record["gaze_window_end_ms"], 7000)

    def test_no_look_at_no_gaze_window(self):
        records = by_index(compute_schedule([
            SPAWN_ANNA, SPAWN_BORIS, speak(1000), emote(2000), move(3000),
        ]))
        for record in records.values():
            self.assertIsNone(record["look_at"])
            self.assertIsNone(record["gaze_window_start_ms"])
            self.assertIsNone(record["gaze_window_end_ms"])

    def test_look_at_does_not_change_scheduling(self):
        plain = [SPAWN_ANNA, SPAWN_BORIS,
                 speak(0, duration_ms=5000),
                 move(2000),
                 emote(2500),
                 speak(3000, actor="boris")]
        gazed = [SPAWN_ANNA, SPAWN_BORIS,
                 speak(0, duration_ms=5000, look_at={"actor_id": "boris"}),
                 move(2000, look_at={"position": [1, 2, 3]}),
                 emote(2500, look_at={"actor_id": "boris"}),
                 speak(3000, actor="boris", look_at={"actor_id": "anna"})]

        def shape(records):
            return [(r["index"], r["op"], r["effective_ms"],
                     r["window_start_ms"], r["window_end_ms"]) for r in records]

        self.assertEqual(shape(compute_schedule(plain)),
                         shape(compute_schedule(gazed)))


class ParityTests(unittest.TestCase):
    def test_scene_schema_carries_look_at_exactly_one_target(self):
        doc = json.loads((ROOT / "schemas" / "scene.schema.json").read_text(encoding="utf-8"))
        prop = doc["properties"]["events"]["items"]["properties"]["look_at"]
        self.assertEqual(prop["type"], "object")
        self.assertEqual(set(prop["properties"]), {"actor_id", "position"})
        self.assertEqual(len(prop["oneOf"]), 2)

    def test_godot_preview_mirrors_gaze_and_layering(self):
        gd = (ROOT / "godot" / "main.gd").read_text(encoding="utf-8")
        self.assertIn("func _begin_gaze", gd)
        self.assertIn("func _update_gaze", gd)
        self.assertIn("func _upper_body_clip", gd)
        self.assertIn("GAZE_MAX_YAW_DEG := 60.0", gd)
        self.assertIn("GAZE_MAX_PITCH_DEG := 30.0", gd)
        self.assertIn("ANIMATION_CALLBACK_MODE_PROCESS_MANUAL", gd)
        self.assertIn('"_gaze_start_ms"', gd)
        self.assertIn('"_gaze_end_ms"', gd)
        self.assertIn("Gaze skipped: ", gd)


if __name__ == "__main__":
    unittest.main()
