"""Saved recipe editor + F2 exit chain (F2 slice 3).

The editor (`studio.recipes.edit_character`) edits recipes already in the
library and re-runs the F2.2 assembly checks before saving: an incompatible
edit is refused with a named reason and the stored recipe is left
byte-identical. The CLI verbs show-character / edit-character /
export-character wrap it, and export -> assemble must round-trip losslessly.

The exit-proof tests assemble, save and load 5 distinct recipes from a
synthetic part catalog (two bodies, varied hair/outfit/colors, all on the
canonical rig, no manual rig changes) and build a validated replay scene
whose actors reference the saved recipe ids. The matching headless Godot
run is recorded as evidence in docs/IMPLEMENTATION_STATUS.md; the scene
builder below is the single source both use.
"""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from studio import cli
from studio.library import Library
from studio.recipes import (RecipeError, assemble_character, edit_character,
                            require_character)
from studio.schema import validate_scene

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


PARTS = [
    asset("body_tall", "body"),
    asset("body_stout", "body", status="candidate"),
    asset("head_round", "head"),
    asset("head_long", "head"),
    asset("hair_curly", "hair"),
    asset("hair_mohawk", "hair", status="candidate"),
    asset("hair_ponytail", "hair"),
    asset("outfit_tunic", "outfit"),
    asset("outfit_robe", "outfit"),
    asset("outfit_boots", "outfit", rig=None),  # rig-agnostic piece
    asset("outfit_cape", "outfit"),
    asset("body_alien", "body", rig="other_rig"),  # foreign-rig refusal case
    asset("prop_mug", "prop", rig=None),          # wrong-kind refusal case
]


def recipe(character_id, body, head, hair, outfit, outfit_color):
    return {
        "schema_version": "1.0.0",
        "character_id": character_id,
        "rig_id": RIG,
        "body_base": body,
        "head": head,
        "hair": hair,
        "outfit": outfit,
        "colors": {"hair": "#663e32", "eyes": "#4a86b8", "outfit": outfit_color},
        "status": "candidate",
    }


# The F2 exit cast: 5 distinct recipes — two bodies, varied heads, hair,
# outfit combinations and colors, all on the canonical rig.
CAST = [
    recipe("cast_anna", "body_tall", "head_round", "hair_curly",
           ["outfit_tunic", "outfit_boots"], "#b0413e"),
    recipe("cast_boris", "body_tall", "head_long", "hair_mohawk",
           ["outfit_robe"], "#3e6fb0"),
    recipe("cast_cleo", "body_stout", "head_round", "hair_ponytail",
           ["outfit_robe", "outfit_cape"], "#3fa065"),
    recipe("cast_dmitri", "body_stout", "head_long", "hair_curly",
           ["outfit_tunic"], "#8a5fb0"),
    recipe("cast_eda", "body_tall", "head_round", "hair_mohawk",
           ["outfit_cape", "outfit_boots"], "#c2a13a"),
]

_BEATS = [
    (500, {"op": "speak", "actor_id": "cast_anna",
           "line": "Anna here, ready when you are."}),
    (1000, {"op": "emote", "actor_id": "cast_boris",
            "emotion": "happy", "intensity": 0.7}),
    (1500, {"op": "speak", "actor_id": "cast_cleo",
            "line": "Cleo, at your service."}),
    (2000, {"op": "emote", "actor_id": "cast_dmitri",
            "emotion": "surprised", "intensity": 0.6}),
    (2500, {"op": "speak", "actor_id": "cast_eda",
            "line": "Eda. Let us begin."}),
]


def seed_parts(lib):
    for part in PARTS:
        lib.put_asset(copy.deepcopy(part))


def save_cast(lib):
    """Assemble and save the 5 exit-cast recipes; returns the recipes."""
    saved = []
    for spec in CAST:
        saved.append(assemble_character(lib, copy.deepcopy(spec)))
        lib.put_character(saved[-1])
    return saved


def build_replay_scene(cast=None):
    """Scene whose 5 actors reference the saved cast recipe ids.

    Each actor spawns at t=0 and gets one speak or emote beat; the actor
    color is the recipe's outfit color, so the recipes stay visually
    distinguishable even through the capsule fallback.
    """
    cast = CAST if cast is None else cast
    actors = [
        {"id": spec["character_id"], "recipe_id": spec["character_id"],
         "color": spec["colors"]["outfit"]}
        for spec in cast
    ]
    events = [
        {"at_ms": 0, "op": "spawn", "actor_id": spec["character_id"],
         "position": [-4 + 2 * i, 0, 0]}
        for i, spec in enumerate(cast)
    ]
    events += [{"at_ms": at, **beat} for at, beat in _BEATS]
    events.append({"at_ms": 3000, "op": "camera", "shot": "wide"})
    return {
        "schema_version": "1.0.0",
        "scene_id": "f2_cast_replay",
        "environment_id": "preview_stage",
        "actors": actors,
        "events": events,
    }


def raw_recipe_json(lib, character_id):
    row = lib.db.execute(
        "SELECT recipe_json FROM characters WHERE character_id=?",
        (character_id,)).fetchone()
    return row["recipe_json"] if row else None


class TempLibraryCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.lib = Library(Path(self._tmp.name) / "test.db")
        self.addCleanup(self.lib.close)
        self.lib.init()
        seed_parts(self.lib)


class EditorTests(TempLibraryCase):
    def setUp(self):
        super().setUp()
        self.hero = recipe("hero_01", "body_tall", "head_round", "hair_curly",
                           ["outfit_tunic"], "#577c59")
        self.lib.put_character(assemble_character(self.lib, copy.deepcopy(self.hero)))

    def test_edit_slot_round_trip(self):
        edited = edit_character(self.lib, "hero_01", {"hair": "hair_ponytail"})
        self.assertEqual(edited["hair"], "hair_ponytail")
        stored = self.lib.get_character("hero_01")
        self.assertEqual(stored["hair"], "hair_ponytail")
        # Untouched fields survive the edit unchanged.
        for field in ("body_base", "head", "outfit", "colors", "rig_id", "status"):
            self.assertEqual(stored[field], self.hero[field])

    def test_edit_outfit_and_colors(self):
        edit_character(self.lib, "hero_01", {
            "outfit": ["outfit_robe", "outfit_cape"],
            "colors": {"hair": "#101010", "outfit": "#202020"},
        })
        stored = self.lib.get_character("hero_01")
        self.assertEqual(stored["outfit"], ["outfit_robe", "outfit_cape"])
        self.assertEqual(stored["colors"], {"hair": "#101010", "outfit": "#202020"})

    def test_edit_unknown_character(self):
        with self.assertRaises(RecipeError) as ctx:
            edit_character(self.lib, "ghost_01", {"hair": "hair_curly"})
        self.assertIn("ghost_01", str(ctx.exception))

    def test_require_character_unknown(self):
        with self.assertRaises(RecipeError):
            require_character(self.lib, "ghost_01")

    def test_edit_wrong_kind_refused_and_stored_identical(self):
        before = raw_recipe_json(self.lib, "hero_01")
        with self.assertRaises(RecipeError) as ctx:
            edit_character(self.lib, "hero_01", {"head": "prop_mug"})
        self.assertIn("prop_mug", str(ctx.exception))
        self.assertIn("kind", str(ctx.exception))
        self.assertEqual(raw_recipe_json(self.lib, "hero_01"), before)

    def test_edit_rig_mismatch_refused_and_stored_identical(self):
        before = raw_recipe_json(self.lib, "hero_01")
        with self.assertRaises(RecipeError) as ctx:
            edit_character(self.lib, "hero_01", {"body_base": "body_alien"})
        self.assertIn("other_rig", str(ctx.exception))
        self.assertEqual(raw_recipe_json(self.lib, "hero_01"), before)

    def test_edit_unknown_part_refused_and_stored_identical(self):
        before = raw_recipe_json(self.lib, "hero_01")
        with self.assertRaises(RecipeError) as ctx:
            edit_character(self.lib, "hero_01", {"outfit": ["missing_outfit"]})
        self.assertIn("missing_outfit", str(ctx.exception))
        self.assertEqual(raw_recipe_json(self.lib, "hero_01"), before)

    def test_edit_unsupported_field_refused(self):
        with self.assertRaises(RecipeError) as ctx:
            edit_character(self.lib, "hero_01", {"rig_id": "other_rig"})
        self.assertIn("rig_id", str(ctx.exception))

    def test_edit_no_changes_refused(self):
        with self.assertRaises(RecipeError):
            edit_character(self.lib, "hero_01", {})

    def test_edit_bad_shape_refused_and_stored_identical(self):
        before = raw_recipe_json(self.lib, "hero_01")
        with self.assertRaises(RecipeError):
            edit_character(self.lib, "hero_01", {"colors": ["#ff0000"]})
        self.assertEqual(raw_recipe_json(self.lib, "hero_01"), before)


class CliEditorTests(TempLibraryCase):
    def setUp(self):
        super().setUp()
        self.hero = recipe("hero_01", "body_tall", "head_round", "hair_curly",
                           ["outfit_tunic"], "#577c59")
        self.lib.put_character(assemble_character(self.lib, copy.deepcopy(self.hero)))
        self.db = str(self.lib.path)

    def run_cli(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(argv)
        return code, out.getvalue()

    def test_cli_show_prints_recipe_json(self):
        code, out = self.run_cli(
            ["show-character", "--db", self.db, "--character", "hero_01"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), self.lib.get_character("hero_01"))

    def test_cli_show_unknown_character_refused(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli(
                ["show-character", "--db", self.db, "--character", "ghost_01"])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_cli_edit_round_trip(self):
        code, _ = self.run_cli(
            ["edit-character", "--db", self.db, "--character", "hero_01",
             "--hair", "hair_ponytail", "--outfit", "outfit_robe,outfit_cape",
             "--colors", '{"outfit": "#123456"}'])
        self.assertEqual(code, 0)
        stored = self.lib.get_character("hero_01")
        self.assertEqual(stored["hair"], "hair_ponytail")
        self.assertEqual(stored["outfit"], ["outfit_robe", "outfit_cape"])
        self.assertEqual(stored["colors"], {"outfit": "#123456"})

    def test_cli_edit_refusal_leaves_stored_identical(self):
        before = raw_recipe_json(self.lib, "hero_01")
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli(
                ["edit-character", "--db", self.db, "--character", "hero_01",
                 "--head", "prop_mug"])
        self.assertNotEqual(ctx.exception.code, 0)
        self.assertEqual(raw_recipe_json(self.lib, "hero_01"), before)

    def test_cli_export_assemble_round_trip_lossless(self):
        exported = Path(self._tmp.name) / "hero_export.json"
        code, _ = self.run_cli(
            ["export-character", "--db", self.db, "--character", "hero_01",
             "--out", str(exported)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(exported.read_text(encoding="utf-8")),
                         self.lib.get_character("hero_01"))
        # The exported spec assembles into a fresh library unchanged.
        other = Library(Path(self._tmp.name) / "other.db")
        self.addCleanup(other.close)
        other.init()
        seed_parts(other)
        code, _ = self.run_cli(
            ["assemble", "--db", str(other.path), "--spec", str(exported)])
        self.assertEqual(code, 0)
        self.assertEqual(other.get_character("hero_01"),
                         self.lib.get_character("hero_01"))


class ExitProofTests(TempLibraryCase):
    def signature(self, spec):
        return (spec["body_base"], spec["head"], spec["hair"],
                tuple(spec["outfit"]),
                json.dumps(spec["colors"], sort_keys=True))

    def test_five_distinct_recipes_assemble_save_load(self):
        saved = save_cast(self.lib)
        loaded = self.lib.list_characters()
        self.assertEqual(len(loaded), 5)
        self.assertEqual(
            {spec["character_id"] for spec in loaded},
            {spec["character_id"] for spec in CAST})
        # Distinct part combinations and/or colors, substantively:
        # 5 unique signatures across at least two bodies and 3+ hairs.
        self.assertEqual(len({self.signature(spec) for spec in loaded}), 5)
        self.assertGreaterEqual(
            len({spec["body_base"] for spec in loaded}), 2)
        self.assertGreaterEqual(len({spec["hair"] for spec in loaded}), 3)
        # No manual rig changes: every recipe is on the canonical rig.
        self.assertTrue(all(spec["rig_id"] == RIG for spec in loaded))
        # Load returns exactly what was saved.
        for spec in saved:
            self.assertEqual(
                self.lib.get_character(spec["character_id"]), spec)

    def test_replay_scene_references_saved_recipes(self):
        save_cast(self.lib)
        scene = build_replay_scene(self.lib.list_characters())
        self.assertIs(validate_scene(scene), scene)
        saved_ids = {spec["character_id"] for spec in CAST}
        self.assertEqual(
            {actor["recipe_id"] for actor in scene["actors"]}, saved_ids)
        # Every actor spawns and gets exactly one speak/emote beat.
        spawned = {e["actor_id"] for e in scene["events"] if e["op"] == "spawn"}
        acted = {e["actor_id"] for e in scene["events"]
                 if e["op"] in ("speak", "emote")}
        self.assertEqual(spawned, saved_ids)
        self.assertEqual(acted, saved_ids)


if __name__ == "__main__":
    unittest.main()
