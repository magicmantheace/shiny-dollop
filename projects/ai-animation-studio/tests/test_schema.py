import copy
import json
import unittest
from pathlib import Path
from studio.schema import validate_scene, validate_asset, validate_character, ValidationError

ROOT = Path(__file__).resolve().parents[1] / "examples"

def sample(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))

class SceneTests(unittest.TestCase):
    def test_good_scene(self):
        self.assertEqual(validate_scene(sample("scene_demo.json"))["schema_version"], "1.0.0")

    def test_reject_unknown_actor(self):
        s = sample("scene_demo.json")
        s["events"][2]["actor_id"] = "intruder"
        with self.assertRaises(ValidationError):
            validate_scene(s)

    def test_reject_unsorted_time(self):
        s = sample("scene_demo.json")
        s["events"][2]["at_ms"] = 0
        s["events"][3]["at_ms"] = 0
        with self.assertRaises(ValidationError):
            validate_scene(s)

    def test_reject_bad_op(self):
        s = sample("scene_demo.json")
        s["events"][2]["op"] = "run_shell"
        with self.assertRaises(ValidationError):
            validate_scene(s)

    def test_asset_path_traversal_rejected(self):
        a = sample("asset_mug.json")
        a["uri"] = "assets/../passwords.txt"
        with self.assertRaises(ValidationError):
            validate_asset(a)

    def test_asset_and_recipe(self):
        self.assertEqual(validate_asset(sample("asset_mug.json"))["status"], "candidate")
        self.assertEqual(validate_character(sample("character_traveler.json"))["rig_id"], "studio_humanoid_v1")

if __name__ == "__main__":
    unittest.main()
