"""Conformance guards: the JSON Schemas (schemas/*.json) are the interchange
contract and studio/schema.py is the hand-rolled runtime validator. These
tests fail if the two drift apart on the shared vocabulary — op set, emotion
set, camera shot set and schema_version — or if validate_scene stops
accepting/rejecting the fixture scenes it is contractually bound to.
"""
import copy
import json
import unittest
from pathlib import Path

from studio.schema import EMOTIONS, OPS, SHOTS, VERSION, ValidationError, validate_scene

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


def load_schema(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def minimal_scene():
    return {
        "schema_version": VERSION,
        "scene_id": "conformance_scene",
        "environment_id": "preview_stage",
        "actors": [{"id": "solo", "recipe_id": "solo_01", "color": "#a1b2c3"}],
        "events": [
            {"at_ms": 0, "op": "spawn", "actor_id": "solo", "position": [0, 0, 0]},
        ],
    }


class SchemaVocabularyTests(unittest.TestCase):
    def test_schema_versions_match_validator(self):
        for name in ("scene.schema.json", "asset.schema.json", "character.schema.json"):
            with self.subTest(schema=name):
                doc = load_schema(name)
                self.assertEqual(doc["properties"]["schema_version"]["const"], VERSION)

    def test_op_set_matches_scene_schema(self):
        doc = load_schema("scene.schema.json")
        enum = doc["properties"]["events"]["items"]["properties"]["op"]["enum"]
        self.assertEqual(set(enum), set(OPS))

    def test_emotion_set_matches_scene_schema(self):
        doc = load_schema("scene.schema.json")
        enum = doc["properties"]["events"]["items"]["properties"]["emotion"]["enum"]
        self.assertEqual(set(enum), set(EMOTIONS))

    def test_shot_set_matches_scene_schema(self):
        doc = load_schema("scene.schema.json")
        enum = doc["properties"]["events"]["items"]["properties"]["shot"]["enum"]
        self.assertEqual(set(enum), set(SHOTS))


class SceneFixtureTests(unittest.TestCase):
    def test_valid_minimal_scene_accepted(self):
        scene = minimal_scene()
        self.assertIs(validate_scene(scene), scene)

    def test_unknown_op_rejected(self):
        scene = minimal_scene()
        scene["events"].append({"at_ms": 10, "op": "explode", "actor_id": "solo"})
        with self.assertRaises(ValidationError):
            validate_scene(scene)

    def test_unsorted_events_rejected(self):
        scene = minimal_scene()
        scene["events"][0]["at_ms"] = 100
        scene["events"].append(
            {"at_ms": 50, "op": "speak", "actor_id": "solo", "line": "Too early."}
        )
        with self.assertRaises(ValidationError):
            validate_scene(scene)

    def test_unknown_actor_rejected(self):
        scene = minimal_scene()
        scene["events"].append(
            {
                "at_ms": 10,
                "op": "move",
                "actor_id": "ghost",
                "target": [1, 0, 0],
                "duration_ms": 500,
            }
        )
        with self.assertRaises(ValidationError):
            validate_scene(scene)

    def test_out_of_bounds_vector_rejected(self):
        scene = minimal_scene()
        bad = copy.deepcopy(scene)
        bad["events"][0]["position"] = [1001, 0, 0]
        with self.assertRaises(ValidationError):
            validate_scene(bad)


if __name__ == "__main__":
    unittest.main()
