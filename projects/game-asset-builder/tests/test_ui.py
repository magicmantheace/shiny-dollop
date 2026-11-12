"""P2 local UI: data layer, run validation, and HTTP surface.

Hermetic: fixture catalogs/outputs live in a temp dir; the one
exception is a smoke read of the project's real catalog (read-only).
HTTP tests run the real server on an ephemeral localhost port.
"""

import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from ui import catalog_data
from ui.runs import RunManager, build_run_argv
from ui.server import make_handler

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _write_entry(catalog_dir, slug, name, rigged, bones, actions):
    entry = {
        "entry_version": 1,
        "name": name,
        "slug": slug,
        "source_concept": "concept.webp",
        "asset_file": f"{slug}.glb",
        "asset_location": "outputs/<slug>/ (local; not in git)",
        "sha256": "ab" * 32,
        "bytes": 1234,
        "counts": {"verts": 100, "faces": 200},
        "bones": bones,
        "actions": actions,
        "provenance": {"rigged": rigged,
                       "rig_template": "biped" if rigged else None,
                       "weight_method": "bone-heat" if rigged else None,
                       "mesh_model": "m", "texture_model": "t"},
    }
    folder = os.path.join(catalog_dir, slug)
    os.makedirs(folder)
    with open(os.path.join(folder, "metadata.json"), "w") as fh:
        json.dump(entry, fh)
    return entry


class CatalogDataTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.catalog = os.path.join(self._tmp.name, "catalog")
        self.outputs = os.path.join(self._tmp.name, "outputs")
        os.makedirs(self.catalog)
        os.makedirs(self.outputs)
        _write_entry(self.catalog, "test-goblin", "Test Goblin", True,
                     ["root", "head"], ["idle", "wave"])
        _write_entry(self.catalog, "test-chest", "Test Chest", False,
                     [], [])
        # The chest's GLB exists locally with the recorded size.
        chest_dir = os.path.join(self.outputs, "test-chest", "renders")
        os.makedirs(chest_dir)
        with open(os.path.join(self.outputs, "test-chest",
                               "test-chest.glb"), "wb") as fh:
            fh.write(b"x" * 1234)
        with open(os.path.join(chest_dir, "beauty.png"), "wb") as fh:
            fh.write(b"\x89PNG")

    def test_summaries_cover_rigged_and_prop(self):
        summaries = {s["slug"]: s for s in
                     catalog_data.list_catalog(self.catalog, self.outputs)}
        self.assertEqual(set(summaries), {"test-goblin", "test-chest"})
        goblin = summaries["test-goblin"]
        self.assertTrue(goblin["rigged"])
        self.assertEqual(goblin["bone_count"], 2)
        self.assertEqual(goblin["actions"], ["idle", "wave"])
        self.assertFalse(goblin["glb_present"])
        chest = summaries["test-chest"]
        self.assertFalse(chest["rigged"])
        self.assertTrue(chest["glb_present"])
        self.assertTrue(chest["glb_size_ok"])
        self.assertEqual(chest["previews"], ["beauty.png"])

    def test_rigged_falls_back_to_bones_for_p0_entries(self):
        # The P0 catalog entry predates provenance.rigged; bones decide.
        entry = {"bones": ["root"], "provenance": {}}
        self.assertTrue(catalog_data._is_rigged(entry))
        entry = {"bones": [], "provenance": {}}
        self.assertFalse(catalog_data._is_rigged(entry))

    def test_real_catalog_has_the_proven_assets(self):
        summaries = {s["slug"]: s for s in catalog_data.list_catalog()}
        self.assertEqual(set(summaries), {"ember-dragon", "snow-goblin",
                                          "treasure-chest", "triceratops",
                                          "moth-hart", "toasty",
                                          "lantern-snail",
                                          "axolotl-capybara",
                                          "geode-tortoise", "crow-postman",
                                          "mandrake-toddler", "ember-owl-cat",
                                          "pine-tree", "boulder", "bush",
                                          "fern", "mushroom-cluster",
                                          "fallen-log", "stump",
                                          "delver", "lantern", "cot",
                                          "gloam-lurker"})
        self.assertEqual(summaries["ember-dragon"]["bone_count"], 14)
        self.assertEqual(summaries["moth-hart"]["bone_count"], 21)
        self.assertEqual(summaries["toasty"]["bone_count"], 11)
        self.assertEqual(summaries["lantern-snail"]["bone_count"], 9)
        self.assertEqual(summaries["axolotl-capybara"]["bone_count"], 15)
        self.assertEqual(summaries["geode-tortoise"]["bone_count"], 15)
        self.assertEqual(summaries["crow-postman"]["bone_count"], 11)
        self.assertEqual(summaries["mandrake-toddler"]["bone_count"], 11)
        self.assertEqual(summaries["ember-owl-cat"]["bone_count"], 14)
        self.assertEqual(summaries["gloam-lurker"]["bone_count"], 15)
        self.assertFalse(summaries["treasure-chest"]["rigged"])
        for slug in ("pine-tree", "boulder", "bush", "fern",
                     "mushroom-cluster", "fallen-log", "stump"):
            self.assertFalse(summaries[slug]["rigged"])

    def test_preview_path_rejects_traversal_and_non_png(self):
        self.assertIsNotNone(catalog_data.preview_path(
            self.outputs, "test-chest", "beauty.png"))
        self.assertIsNone(catalog_data.preview_path(
            self.outputs, "test-chest", "../test-chest.glb"))
        self.assertIsNone(catalog_data.preview_path(
            self.outputs, "test-chest", "test-chest.glb"))
        self.assertIsNone(catalog_data.preview_path(
            self.outputs, "../catalog", "beauty.png"))
        self.assertIsNone(catalog_data.preview_path(
            self.outputs, "test-chest", "missing.png"))

    def test_stage_table_matches_registry(self):
        table = catalog_data.stage_table()
        self.assertEqual([t["name"] for t in table],
                         ["prep", "mesh", "texture", "segment", "rig",
                          "animate", "catalog"])

    def test_doctor_info_shape(self):
        info = catalog_data.doctor_info()
        self.assertIn("python", info)
        self.assertEqual(len(info["stages"]), 7)
        cpu = [s for s in info["stages"] if s["needs"] == "cpu"]
        self.assertTrue(all(s["can_run"] for s in cpu))


class RunValidationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.concept = os.path.join(self._tmp.name, "concept.png")
        with open(self.concept, "wb") as fh:
            fh.write(b"\x89PNG")

    def test_argv_mirrors_cli_flags(self):
        argv = build_run_argv({"concept": self.concept, "name": "X",
                               "template": "biped", "rotate_z": 90,
                               "ears": True})
        self.assertIn("--template", argv)
        self.assertEqual(argv[argv.index("--template") + 1], "biped")
        self.assertIn("--ears", argv)
        self.assertEqual(argv[argv.index("--rotate-z") + 1], "90")

    def test_invalid_specs_raise_and_spawn_nothing(self):
        manager = RunManager()
        for spec in ({"concept": "/nonexistent.png", "name": "X"},
                     {"concept": self.concept, "name": "  "},
                     {"concept": self.concept, "name": "X",
                      "template": "centaur"},
                     {"concept": self.concept, "name": "X",
                      "rotate_z": 45}):
            with self.assertRaises(ValueError):
                manager.start(spec)
        self.assertEqual(manager.list(), [])


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        catalog = os.path.join(cls._tmp.name, "catalog")
        outputs = os.path.join(cls._tmp.name, "outputs")
        os.makedirs(catalog)
        os.makedirs(outputs)
        _write_entry(catalog, "test-chest", "Test Chest", False, [], [])
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(catalog, outputs, RunManager()))
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def _get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port,
                                          timeout=10)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body

    def test_index_page_served(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Game Asset Builder", body)

    def test_catalog_endpoint(self):
        status, body = self._get("/api/catalog")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual([d["slug"] for d in data], ["test-chest"])

    def test_unknown_asset_is_404(self):
        status, _ = self._get("/api/catalog/nope")
        self.assertEqual(status, 404)

    def test_preview_traversal_is_404(self):
        status, _ = self._get("/api/preview/test-chest/..%2Ftest-chest.glb")
        self.assertEqual(status, 404)

    def test_post_run_with_bad_spec_is_400(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port,
                                          timeout=10)
        conn.request("POST", "/api/runs",
                     body=json.dumps({"concept": "/nope.png",
                                      "name": "X"}),
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 400)


if __name__ == "__main__":
    unittest.main()
