"""Prop sockets + composite action macros (F4.2): the scene-level `props`
registry and the `interact` op (pick_up / put_down / sit / drink) —
schema acceptance/rejection incl. the holding-sequence rules, JSON
Schema parity, the deterministic composite expansion in
studio/timing.py compute_schedule (occupancy windows, phase windows,
attach/release points, gating), the manifest prop pins from
studio/cli.py enrich_manifest, plus markers for the Godot preview's
mirror (BoneAttachment3D socket attach/release) in godot/main.gd. The
headless probe evidence is recorded in docs/IMPLEMENTATION_STATUS.md,
F4 slice 2.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from studio.cli import enrich_manifest
from studio.library import Library
from studio.schema import (INTERACT_ACTIONS, PROP_SOCKETS,
                           ValidationError, validate_scene)
from studio.timing import compute_schedule

ROOT = Path(__file__).resolve().parents[1]

SPAWN_ANNA = {"at_ms": 0, "op": "spawn", "actor_id": "anna", "position": [-2, 0, 2]}
SPAWN_BORIS = {"at_ms": 0, "op": "spawn", "actor_id": "boris", "position": [2, 0, -2]}
MUG = {"id": "mug", "asset_id": "mug_wood_01", "position": [0.2, 0.78, 1.7]}
JUG = {"id": "jug", "asset_id": "jug_clay_01", "position": [0.5, 0.78, 1.7]}


def scene_with(events, props=(MUG,)):
    scene = {
        "schema_version": "1.0.0",
        "scene_id": "interact_scene",
        "environment_id": "preview_stage",
        "actors": [
            {"id": "anna", "recipe_id": "anna_01", "color": "#a1b2c3"},
            {"id": "boris", "recipe_id": "boris_01", "color": "#c3b2a1"},
        ],
        "events": events,
    }
    if props is not None:
        scene["props"] = [dict(p) for p in props]
    return scene


def interact(at_ms, action, actor="anna", **extra):
    event = {"at_ms": at_ms, "op": "interact", "actor_id": actor,
             "action": action, "duration_ms": 1000}
    event.update(extra)
    return event


def speak(at_ms, actor="anna", **extra):
    event = {"at_ms": at_ms, "op": "speak", "actor_id": actor,
             "line": "Hello there."}
    event.update(extra)
    return event


def happy():
    """A full valid pick_up -> drink -> put_down sequence."""
    return [SPAWN_ANNA, SPAWN_BORIS,
            interact(500, "pick_up", prop_id="mug"),
            interact(2500, "drink", prop_id="mug"),
            interact(5000, "put_down", prop_id="mug")]


def by_index(records):
    return {r["index"]: r for r in records}


class PropRegistryValidationTests(unittest.TestCase):
    def test_full_sequence_accepted(self):
        scene = scene_with(happy())
        self.assertIs(validate_scene(scene), scene)

    def test_scene_without_props_still_valid(self):
        scene = scene_with([SPAWN_ANNA], props=None)
        self.assertIs(validate_scene(scene), scene)

    def test_socket_defaults_and_explicit_hand_l_accepted(self):
        scene = scene_with([SPAWN_ANNA])
        validate_scene(scene)
        scene["props"] = [dict(MUG, socket="hand_l")]
        validate_scene(scene)

    def test_bad_socket_refused(self):
        scene = scene_with([SPAWN_ANNA])
        scene["props"] = [dict(MUG, socket="back")]
        with self.assertRaises(ValidationError):
            validate_scene(scene)

    def test_duplicate_prop_id_refused(self):
        scene = scene_with([SPAWN_ANNA], props=(MUG, MUG))
        with self.assertRaises(ValidationError):
            validate_scene(scene)

    def test_prop_bad_position_refused(self):
        scene = scene_with([SPAWN_ANNA])
        scene["props"] = [dict(MUG, position=[2000, 0, 0])]
        with self.assertRaises(ValidationError):
            validate_scene(scene)


class InteractValidationTests(unittest.TestCase):
    def assert_refused(self, events, props=(MUG,)):
        with self.assertRaises(ValidationError):
            validate_scene(scene_with(events, props=props))

    def test_unknown_action_refused(self):
        self.assert_refused([SPAWN_ANNA, interact(100, "juggle", prop_id="mug")])

    def test_missing_duration_refused(self):
        event = interact(100, "sit", target=[0, 0, 0])
        del event["duration_ms"]
        self.assert_refused([SPAWN_ANNA, event])

    def test_duration_bounds_refused(self):
        for bad in (99, 60001, 1000.5, True):
            with self.subTest(duration_ms=bad):
                self.assert_refused(
                    [SPAWN_ANNA, interact(100, "sit", duration_ms=bad,
                                          target=[0, 0, 0])])

    def test_prop_actions_require_prop_id(self):
        for action in ("pick_up", "drink", "put_down"):
            with self.subTest(action=action):
                self.assert_refused([SPAWN_ANNA, interact(100, action)])

    def test_undeclared_prop_refused(self):
        self.assert_refused([SPAWN_ANNA, interact(100, "pick_up", prop_id="tankard")])

    def test_prop_id_on_sit_refused(self):
        self.assert_refused(
            [SPAWN_ANNA, interact(100, "sit", prop_id="mug", target=[0, 0, 0])])

    def test_sit_requires_target(self):
        self.assert_refused([SPAWN_ANNA, interact(100, "sit")])

    def test_put_down_target_optional_but_validated(self):
        events = happy()
        events[4] = interact(5000, "put_down", prop_id="mug", target=[0, 0, 0])
        validate_scene(scene_with(events))
        events[4] = interact(5000, "put_down", prop_id="mug", target=[0, 0])
        self.assert_refused(events)

    def test_target_on_pick_up_and_drink_refused(self):
        events = happy()
        events[2] = interact(500, "pick_up", prop_id="mug", target=[0, 0, 0])
        self.assert_refused(events)
        events = happy()
        events[3] = interact(2500, "drink", prop_id="mug", target=[0, 0, 0])
        self.assert_refused(events)

    def test_drink_without_holding_refused(self):
        self.assert_refused([SPAWN_ANNA, interact(100, "drink", prop_id="mug")])

    def test_put_down_without_holding_refused(self):
        self.assert_refused([SPAWN_ANNA, interact(100, "put_down", prop_id="mug")])

    def test_drink_wrong_prop_refused(self):
        events = [SPAWN_ANNA, interact(100, "pick_up", prop_id="mug"),
                  interact(200, "drink", prop_id="jug")]
        self.assert_refused(events, props=(MUG, JUG))

    def test_double_pick_up_refused(self):
        events = [SPAWN_ANNA, interact(100, "pick_up", prop_id="mug"),
                  interact(200, "pick_up", prop_id="mug")]
        self.assert_refused(events)

    def test_pick_up_prop_held_by_other_actor_refused(self):
        events = [SPAWN_ANNA, SPAWN_BORIS,
                  interact(100, "pick_up", prop_id="mug"),
                  interact(200, "pick_up", actor="boris", prop_id="mug")]
        self.assert_refused(events)

    def test_actor_holding_two_props_refused(self):
        events = [SPAWN_ANNA, interact(100, "pick_up", prop_id="mug"),
                  interact(200, "pick_up", prop_id="jug")]
        self.assert_refused(events, props=(MUG, JUG))

    def test_look_at_on_interact_refused(self):
        events = happy()
        events[2] = interact(500, "pick_up", prop_id="mug",
                             look_at={"actor_id": "boris"})
        self.assert_refused(events)

    def test_sit_while_holding_allowed(self):
        events = [SPAWN_ANNA, interact(100, "pick_up", prop_id="mug"),
                  interact(200, "sit", target=[0, 0, 0]),
                  interact(300, "put_down", prop_id="mug")]
        validate_scene(scene_with(events))


class ScheduleExpansionTests(unittest.TestCase):
    def schedule(self, events, props=(MUG,)):
        scene = validate_scene(scene_with(events, props=props))
        return by_index(compute_schedule(scene["events"]))

    def test_expansion_is_deterministic_and_pure(self):
        events = happy()
        snapshot = copy.deepcopy(events)
        first = compute_schedule(events)
        second = compute_schedule(events)
        self.assertEqual(first, second)
        self.assertEqual(events, snapshot)

    def test_pick_up_phases_and_attach_midpoint(self):
        records = self.schedule(
            [SPAWN_ANNA, interact(500, "pick_up", duration_ms=1600, prop_id="mug")])
        rec = records[1]
        self.assertEqual(rec["action"], "pick_up")
        self.assertEqual(rec["prop_id"], "mug")
        self.assertEqual((rec["window_start_ms"], rec["window_end_ms"]), (500, 2100))
        self.assertEqual(rec["attach_ms"], 1300)
        self.assertEqual(rec["phases"], [
            {"name": "reach", "start_ms": 500, "end_ms": 1300},
            {"name": "hold", "start_ms": 1300, "end_ms": 2100},
        ])
        self.assertEqual(rec["holding_after"], "mug")

    def test_drink_and_put_down_phases(self):
        records = self.schedule(happy())
        drink = records[3]
        self.assertEqual(drink["phases"],
                         [{"name": "consume", "start_ms": 2500, "end_ms": 3500}])
        self.assertEqual(drink["holding_after"], "mug")
        self.assertIsNone(drink["release_ms"])
        down = records[4]
        self.assertEqual(down["phases"],
                         [{"name": "lower", "start_ms": 5000, "end_ms": 6000}])
        self.assertEqual(down["release_ms"], 6000)
        self.assertIsNone(down["holding_after"])

    def test_sit_phase_and_seated_until_move(self):
        events = [SPAWN_ANNA, interact(500, "sit", duration_ms=2000,
                                        target=[-0.85, 0, 1.7]),
                  speak(3000),
                  {"at_ms": 6000, "op": "move", "actor_id": "anna",
                   "target": [0, 0, 0], "duration_ms": 1000}]
        records = self.schedule(events)
        sit = records[1]
        self.assertEqual(sit["phases"],
                         [{"name": "enter", "start_ms": 500, "end_ms": 2500}])
        self.assertTrue(sit["seated_after"])
        self.assertTrue(records[2]["seated_after"])
        self.assertFalse(records[3]["seated_after"])

    def test_speak_after_composite_is_delayed_to_window_end(self):
        events = [SPAWN_ANNA, interact(500, "pick_up", duration_ms=1600,
                                       prop_id="mug"),
                  speak(1000)]
        records = self.schedule(events)
        self.assertEqual(records[2]["effective_ms"], 2100)
        self.assertEqual(records[2]["window_start_ms"], 2100)

    def test_composite_gated_by_speak_hold(self):
        events = [SPAWN_ANNA, speak(0, duration_ms=3000),
                  interact(1000, "pick_up", duration_ms=1000, prop_id="mug")]
        records = self.schedule(events)
        self.assertEqual(records[2]["effective_ms"], 3000)
        self.assertEqual(records[2]["window_start_ms"], 3000)
        self.assertEqual(records[2]["attach_ms"], 3500)

    def test_composites_gate_each_other(self):
        events = [SPAWN_ANNA, interact(0, "pick_up", duration_ms=1000, prop_id="mug"),
                  interact(500, "drink", duration_ms=1000, prop_id="mug")]
        records = self.schedule(events)
        self.assertEqual(records[2]["effective_ms"], 1000)

    def test_interrupt_speak_runs_concurrently_with_composite(self):
        # An interrupting speak is never delayed (F3.3) and truncates
        # speak windows only: inside an interact window it starts at its
        # at_ms while the composite window stands.
        events = [SPAWN_ANNA, interact(0, "pick_up", duration_ms=4000, prop_id="mug"),
                  speak(1000, interrupt=True)]
        records = self.schedule(events)
        self.assertEqual(records[2]["effective_ms"], 1000)
        self.assertEqual(records[1]["window_end_ms"], 4000)
        self.assertFalse(records[1]["interrupted"])


class ManifestPinTests(unittest.TestCase):
    def test_enrich_manifest_attaches_prop_pins(self):
        with tempfile.TemporaryDirectory() as temp:
            lib = Library(Path(temp) / "test.db")
            try:
                lib.init()
                lib.put_asset({
                    "schema_version": "1.0.0", "asset_id": "mug_wood_01",
                    "kind": "prop", "uri": "assets/props/mug_wood_01.glb",
                    "status": "approved", "tags": ["hand_prop"],
                    "rig_id": None,
                    "metadata": {"version": "2.0.0", "sha256": "ab" * 32},
                })
                base = {"schema_version": "1.0.0", "clips": {}, "recipes": {}}
                enriched = enrich_manifest(base, lib, None, [MUG])
                pin = enriched["props"]["mug"]
                self.assertEqual(pin["uri"], "assets/props/mug_wood_01.glb")
                self.assertEqual(pin["status"], "approved")
                self.assertEqual(pin["version"], "2.0.0")
                self.assertEqual(pin["sha256"], "ab" * 32)
            finally:
                lib.close()

    def test_unregistered_prop_gets_no_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            lib = Library(Path(temp) / "test.db")
            try:
                lib.init()
                base = {"schema_version": "1.0.0", "clips": {}, "recipes": {}}
                enriched = enrich_manifest(base, lib, None, [MUG])
                self.assertEqual(enriched["props"], {})
            finally:
                lib.close()


class ParityTests(unittest.TestCase):
    def test_scene_schema_action_enum_matches_validator(self):
        doc = json.loads((ROOT / "schemas" / "scene.schema.json").read_text(encoding="utf-8"))
        items = doc["properties"]["events"]["items"]["properties"]
        self.assertEqual(set(items["action"]["enum"]), set(INTERACT_ACTIONS))
        self.assertIn("prop_id", items)
        props = doc["properties"]["props"]["items"]
        self.assertEqual(set(props["properties"]["socket"]["enum"]), set(PROP_SOCKETS))
        self.assertEqual(props["required"], ["id", "asset_id", "position"])

    def test_godot_preview_mirrors_interactions(self):
        gd = (ROOT / "godot" / "main.gd").read_text(encoding="utf-8")
        self.assertIn('"interact"', gd)
        for action in INTERACT_ACTIONS:
            self.assertIn(f'"{action}"', gd)
        self.assertIn("func _build_props", gd)
        self.assertIn("func _dispatch_interact", gd)
        self.assertIn("func _attach_prop", gd)
        self.assertIn("func _release_prop", gd)
        self.assertIn("BoneAttachment3D", gd)
        self.assertIn("Prop attached: ", gd)
        self.assertIn("Prop attach skipped: ", gd)
        self.assertIn("Prop released: ", gd)
        self.assertIn("Prop unavailable: ", gd)
        self.assertIn('"_attach_ms"', gd)
        self.assertIn('"_release_ms"', gd)
        for tag in ("pickup", "consume", "sit_enter", "sit_idle"):
            self.assertIn(f'"{tag}"', gd)


if __name__ == "__main__":
    unittest.main()
