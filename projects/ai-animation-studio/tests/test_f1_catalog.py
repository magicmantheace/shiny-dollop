"""F1 Quaternius adoption fixtures: catalog, manifest and register flow.

The catalog and manifest are committed metadata fixtures; the media files
they reference stay in the local asset store outside git, so these tests
verify internal consistency (URIs, clip names, counts) rather than files.
"""
import json
import tempfile
import unittest
from pathlib import Path

from studio.cli import load, main
from studio.library import Library, ROOT
from studio.schema import (
    VERSION,
    validate_asset,
    validate_catalog,
    validate_character,
)

CATALOG = load("quaternius_f1_catalog.json")
MANIFEST = load("asset_manifest.json")


class CatalogTests(unittest.TestCase):
    def test_catalog_records_are_valid_candidates(self):
        catalog = validate_catalog(CATALOG)
        self.assertEqual(len(catalog["assets"]), 9)
        self.assertEqual(len(catalog["characters"]), 2)
        for asset in catalog["assets"]:
            validate_asset(asset)
            self.assertEqual(asset["status"], "candidate")
        for character in catalog["characters"]:
            validate_character(character)
            self.assertEqual(character["status"], "candidate")
            self.assertEqual(character["rig_id"], "studio_humanoid_v1")

    def test_motion_clip_counts_match_inventory(self):
        for asset in CATALOG["assets"]:
            if asset["kind"] != "motion":
                continue
            meta = asset["metadata"]
            self.assertEqual(meta["clip_count"], len(meta["clips"]))
            self.assertGreaterEqual(meta["clip_count"], 40)
            self.assertEqual(meta["joints"], 65)

    def test_bodies_record_no_blendshapes(self):
        for asset in CATALOG["assets"]:
            if asset["kind"] == "body":
                self.assertEqual(asset["metadata"]["morph_targets"], 0)


class ManifestTests(unittest.TestCase):
    def test_manifest_matches_catalog(self):
        self.assertEqual(MANIFEST["schema_version"], VERSION)
        self.assertEqual(MANIFEST["rig_id"], "studio_humanoid_v1")
        by_uri = {a["uri"]: a for a in CATALOG["assets"]}
        character_ids = {c["character_id"] for c in CATALOG["characters"]}
        self.assertEqual(set(MANIFEST["recipes"]), character_ids)
        for recipe in MANIFEST["recipes"].values():
            self.assertIn(recipe["body"], by_uri)
            for uri in recipe["animations"]:
                self.assertIn(uri, by_uri)

    def test_clip_tags_map_to_real_clips(self):
        by_uri = {a["uri"]: a for a in CATALOG["assets"]}
        clips = MANIFEST["clips"]
        self.assertGreaterEqual(len(clips), 10)
        for tag in ("idle", "walk", "speak", "sit_enter", "sit_idle"):
            self.assertIn(tag, clips)
        for entry in clips.values():
            owner = by_uri[entry["file"]]
            self.assertEqual(owner["kind"], "motion")
            self.assertIn(entry["clip"], owner["metadata"]["clips"])
            self.assertAlmostEqual(
                entry["duration_s"], owner["metadata"]["clips"][entry["clip"]], places=2
            )


class RegisterCliTests(unittest.TestCase):
    def test_register_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "register.db"
            self.assertEqual(main(["register", "--db", str(db)]), 0)
            self.assertEqual(main(["register", "--db", str(db)]), 0)
            lib = Library(db)
            try:
                assets = lib.list_assets()
                self.assertEqual(len(assets), 9)
                self.assertTrue(all(a["status"] == "candidate" for a in assets))
                rows = lib.db.execute("SELECT COUNT(*) FROM characters").fetchone()[0]
                self.assertEqual(rows, 2)
            finally:
                lib.close()

    def test_demo_exports_v2_scene_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "scene_runtime.json"
            code = main(["demo", "--scene", "scene_tavern_v2.json", "--out", str(out)])
            self.assertEqual(code, 0)
            scene = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(scene["scene_id"], "tavern_meeting_v2")
            manifest_copy = Path(temp) / "asset_manifest.json"
            self.assertTrue(manifest_copy.exists())
            self.assertEqual(
                json.loads(manifest_copy.read_text(encoding="utf-8"))["rig_id"],
                "studio_humanoid_v1",
            )


if __name__ == "__main__":
    unittest.main()
