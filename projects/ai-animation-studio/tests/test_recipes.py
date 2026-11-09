"""Recipe composition (F2 slice 2): assemble_character checks a character
spec against the library — part existence, slot/kind fit, rig agreement and
(on request) approval — where validate_character checks shape only.
Fixtures are a small synthetic part catalog in a temp library: parts on the
canonical rig, one foreign-rig part, one wrong-kind asset, a rig-agnostic
outfit piece, and candidate vs approved variants.
"""
import json
import tempfile
import unittest
from pathlib import Path

from studio import cli
from studio.library import Library
from studio.recipes import RecipeError, assemble_character, unapproved_parts

RIG = "studio_humanoid_v1"


def asset(asset_id, kind, rig=RIG, status="approved"):
    return {
        "schema_version": "1.0.0",
        "asset_id": asset_id,
        "kind": kind,
        "uri": f"assets/{kind}/{asset_id}.gltf",
        "rig_id": rig,
        "status": status,
        "tags": [],
        "metadata": {},
    }


def spec(**overrides):
    base = {
        "schema_version": "1.0.0",
        "character_id": "hero_01",
        "rig_id": RIG,
        "body_base": "body_main",
        "head": "head_main",
        "hair": "hair_main",
        "outfit": ["outfit_coat", "outfit_boots"],
        "colors": {"hair": "#663e32"},
        "status": "candidate",
    }
    base.update(overrides)
    return base


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.lib = Library(Path(self._tmp.name) / "test.db")
        self.addCleanup(self.lib.close)
        self.lib.init()
        for part in (
            asset("body_main", "body"),
            asset("head_main", "head"),
            asset("hair_main", "hair", status="candidate"),
            asset("hair_approved", "hair"),
            asset("outfit_coat", "outfit"),
            asset("outfit_boots", "outfit", rig=None),  # rig-agnostic piece
            asset("body_alien", "body", rig="other_rig"),
            asset("prop_mug", "prop", rig=None),
        ):
            self.lib.put_asset(part)

    def test_happy_path_save_and_round_trip(self):
        recipe = assemble_character(self.lib, spec())
        self.lib.put_character(recipe)
        self.assertEqual(self.lib.get_character("hero_01"), spec())
        # The candidate hair is reported, not stored on the recipe.
        self.assertEqual(unapproved_parts(self.lib, recipe), ["hair_main"])

    def test_all_approved_with_require_approved(self):
        recipe = assemble_character(
            self.lib, spec(hair="hair_approved"), require_approved=True)
        self.assertEqual(unapproved_parts(self.lib, recipe), [])
        self.lib.put_character(recipe)
        self.assertEqual(self.lib.get_character("hero_01")["hair"],
                         "hair_approved")

    def test_unknown_part(self):
        with self.assertRaises(RecipeError) as ctx:
            assemble_character(self.lib, spec(body_base="missing_body"))
        self.assertIn("missing_body", str(ctx.exception))
        self.assertIn("no such asset", str(ctx.exception))

    def test_unknown_outfit_entry(self):
        with self.assertRaises(RecipeError) as ctx:
            assemble_character(
                self.lib, spec(outfit=["outfit_coat", "missing_outfit"]))
        self.assertIn("missing_outfit", str(ctx.exception))

    def test_wrong_kind_for_slot(self):
        with self.assertRaises(RecipeError) as ctx:
            assemble_character(self.lib, spec(head="prop_mug"))
        self.assertIn("prop_mug", str(ctx.exception))
        self.assertIn("kind", str(ctx.exception))

    def test_wrong_kind_in_outfit(self):
        with self.assertRaises(RecipeError):
            assemble_character(self.lib, spec(outfit=["hair_approved"]))

    def test_rig_mismatch(self):
        with self.assertRaises(RecipeError) as ctx:
            assemble_character(self.lib, spec(body_base="body_alien"))
        self.assertIn("other_rig", str(ctx.exception))

    def test_require_approved_rejects_candidate_part(self):
        with self.assertRaises(RecipeError) as ctx:
            assemble_character(self.lib, spec(), require_approved=True)
        self.assertIn("hair_main", str(ctx.exception))
        self.assertIn("candidate", str(ctx.exception))

    def test_malformed_spec_is_recipe_error(self):
        with self.assertRaises(RecipeError):
            assemble_character(self.lib, spec(character_id="Not An Id"))

    def test_cli_assemble_round_trip(self):
        db = str(self.lib.path)  # the catalog populated in setUp lives here
        spec_path = Path(self._tmp.name) / "spec.json"
        spec_path.write_text(json.dumps(spec()), encoding="utf-8")
        self.assertEqual(
            cli.main(["assemble", "--db", db, "--spec", str(spec_path)]), 0)
        self.assertEqual(self.lib.get_character("hero_01"), spec())
        # --require-approved refuses the same spec (candidate hair).
        with self.assertRaises(SystemExit) as ctx:
            cli.main(["assemble", "--db", db, "--spec", str(spec_path),
                      "--require-approved"])
        self.assertNotEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
