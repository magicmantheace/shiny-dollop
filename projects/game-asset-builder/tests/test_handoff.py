"""P3 engine hand-offs: exporters produce packages whose bytes match
the catalog record, in the shapes the targets expect.

Hermetic: a fixture catalog + outputs area in a temp dir, with real
sha256 entries built through the catalog module itself. The .glb
payloads are dummy bytes — exporters copy and hash, they do not
parse; engine playback is proven by the harnesses on the owner's PC
(see handoff/README.md), not here.
"""

import hashlib
import importlib.util
import json
import os
import re
import tempfile
import unittest

from handoff import export as hx

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _catalog_module():
    spec = importlib.util.spec_from_file_location(
        "gab_catalog_for_tests",
        os.path.join(PROJECT_DIR, "stages", "catalog", "catalog.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HandoffFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.catalog_dir = os.path.join(self._tmp.name, "catalog")
        self.outputs_dir = os.path.join(self._tmp.name, "outputs")
        os.makedirs(self.catalog_dir)
        os.makedirs(self.outputs_dir)
        catalog_mod = _catalog_module()
        self.entries = {}
        for slug, name, bones, actions, rigged in (
                ("test-goblin", "Test Goblin", ["root", "head"],
                 ["idle", "wave"], True),
                ("test-chest", "Test Chest", [], [], False)):
            workdir = os.path.join(self.outputs_dir, slug)
            os.makedirs(workdir)
            glb_path = os.path.join(workdir, f"{slug}.glb")
            with open(glb_path, "wb") as fh:
                fh.write(b"glTF-dummy-" + slug.encode() * 64)
            entry = catalog_mod.build_entry(
                name=name, source_concept="concept.webp",
                glb_path=glb_path,
                counts={"verts": 10, "faces": 20},
                bones=bones, actions=actions,
                provenance={
                    "rigged": rigged,
                    "rig_template": "biped" if rigged else None,
                    "weight_method": "bone-heat" if rigged else None,
                    "mesh_model": "m", "texture_model": "t"})
            catalog_mod.write_entry(self.catalog_dir, entry)
            self.entries[slug] = (entry, glb_path)

    def load(self, slug):
        return hx.load_verified_entry(slug, self.catalog_dir,
                                      self.outputs_dir)


class LoadVerifiedTests(HandoffFixture):
    def test_loads_and_verifies(self):
        entry, _ = self.load("test-goblin")
        self.assertEqual(entry["slug"], "test-goblin")

    def test_tampered_glb_is_refused(self):
        _, glb_path = self.entries["test-chest"]
        with open(glb_path, "ab") as fh:
            fh.write(b"x")
        with self.assertRaises(ValueError):
            self.load("test-chest")

    def test_unknown_slug_is_refused(self):
        with self.assertRaises(ValueError):
            self.load("no-such-asset")


class GodotExportTests(HandoffFixture):
    def test_package_shape_and_bytes(self):
        entry, glb_path = self.load("test-goblin")
        dest = os.path.join(self._tmp.name, "godot-out")
        manifest = hx.export_godot(entry, glb_path, dest)
        folder = os.path.join(dest, "test-goblin")
        for name in ("test-goblin.glb", "test-goblin.tscn",
                     "test-goblin.json", "README.md",
                     "handoff-manifest.json"):
            self.assertTrue(os.path.isfile(os.path.join(folder, name)),
                            name)
        with open(os.path.join(folder, "test-goblin.glb"), "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(),
                             entry["sha256"])
        self.assertEqual(manifest["sha256"], entry["sha256"])
        self.assertEqual(manifest["target"], "godot")

    def test_tscn_instances_the_glb_at_the_documented_path(self):
        entry, glb_path = self.load("test-goblin")
        dest = os.path.join(self._tmp.name, "godot-out")
        hx.export_godot(entry, glb_path, dest)
        with open(os.path.join(dest, "test-goblin",
                               "test-goblin.tscn")) as fh:
            tscn = fh.read()
        self.assertIn('path="res://assets/test-goblin/test-goblin.glb"',
                      tscn)
        self.assertIn('instance=ExtResource("1")', tscn)


class ThreejsExportTests(HandoffFixture):
    def test_package_shape(self):
        entry, glb_path = self.load("test-goblin")
        dest = os.path.join(self._tmp.name, "three-out")
        hx.export_threejs(entry, glb_path, dest)
        folder = os.path.join(dest, "test-goblin")
        with open(os.path.join(folder, "asset.json")) as fh:
            asset = json.load(fh)
        self.assertEqual(asset["file"], "test-goblin.glb")
        self.assertEqual(asset["clips"], ["idle", "wave"])
        self.assertEqual(asset["bones"], ["root", "head"])
        self.assertEqual(asset["sha256"], entry["sha256"])
        with open(os.path.join(folder, "loader-snippet.js")) as fh:
            snippet = fh.read()
        self.assertIn("GLTFLoader", snippet)
        self.assertIn("AnimationMixer", snippet)
        self.assertIn("test-goblin.glb", snippet)


class StudioExportTests(HandoffFixture):
    def test_record_matches_the_studio_intake_rules(self):
        entry, _ = self.entries["test-goblin"]
        record = hx.studio_record(entry)
        self.assertEqual(record["schema_version"], "1.0.0")
        self.assertEqual(record["kind"], "body")
        self.assertEqual(record["status"], "candidate")
        # The GAB rig is NOT the studio's humanoid rig; never claim it.
        self.assertEqual(record["rig_id"], "biped")
        self.assertNotEqual(record["rig_id"], "studio_humanoid_v1")
        self.assertIn(record["license"],
                      ("CC0-1.0", "MIT", "proprietary", "unknown"))
        self.assertRegex(record["asset_id"], r"^[a-z][a-z0-9_-]{0,63}$")
        self.assertRegex(record["uri"],
                         r"^assets/(?!.*\.\.)[A-Za-z0-9_./-]+$")
        self.assertEqual(record["metadata"]["sha256"], entry["sha256"])
        self.assertEqual(record["metadata"]["clips"], ["idle", "wave"])
        self.assertEqual(record["metadata"]["joints"], 2)
        self.assertEqual(len(record["tags"]),
                         len(set(record["tags"])))

    def test_prop_record_is_a_prop_with_no_rig(self):
        entry, _ = self.entries["test-chest"]
        record = hx.studio_record(entry)
        self.assertEqual(record["kind"], "prop")
        self.assertIsNone(record["rig_id"])
        self.assertTrue(record["uri"].startswith("assets/props/"))

    def test_export_writes_glb_and_merges_catalog(self):
        root = os.path.join(self._tmp.name, "studio-root")
        for slug in ("test-goblin", "test-chest"):
            entry, glb_path = self.load(slug)
            result = hx.export_studio(entry, glb_path, root)
            with open(result["glb_path"], "rb") as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(),
                                 entry["sha256"])
        # Re-export the goblin: replaced, not duplicated.
        entry, glb_path = self.load("test-goblin")
        result = hx.export_studio(entry, glb_path, root)
        with open(result["catalog_path"]) as fh:
            catalog = json.load(fh)
        ids = [a["asset_id"] for a in catalog["assets"]]
        self.assertEqual(ids, ["test-chest", "test-goblin"])
        self.assertTrue(os.path.isfile(
            os.path.join(root, "assets", "characters",
                         "test-goblin.glb")))
        self.assertTrue(os.path.isfile(
            os.path.join(root, "assets", "props", "test-chest.glb")))


if __name__ == "__main__":
    unittest.main()
