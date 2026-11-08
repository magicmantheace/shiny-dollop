"""Create-and-promote proof (F5.3, the F5 exit): a previously missing
reusable asset — a tavern lantern prop — is created by the committed
deterministic generator (tools/generate_lantern.py), registered from
its examples catalog, reviewed, and promoted through the real ADR-008
gates, then used by a scene whose manifest export carries the ADR-008
pin. The whole chain runs through public APIs / the CLI: no manual
database edits anywhere. The headless Godot probe that loads the
promoted lantern in the preview is recorded as evidence in
docs/IMPLEMENTATION_STATUS.md, F5 slice 3.
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from studio import gltf
from studio.cli import enrich_manifest, load, main
from studio.library import Library
from studio.promotion import promote_asset
from studio.reviews import latest_review, list_candidates
from studio.schema import validate_catalog, validate_scene

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_lantern.py"
ASSET_ID = "lantern_procedural_01"
URI = "assets/props/lantern_procedural_01.glb"

_spec = importlib.util.spec_from_file_location("generate_lantern", GENERATOR)
generate_lantern = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_lantern)


def catalog_asset() -> dict:
    catalog = load("lantern_procedural_catalog.json")
    return next(a for a in catalog["assets"] if a["asset_id"] == ASSET_ID)


class LanternGeneratorTests(unittest.TestCase):
    def test_build_is_byte_deterministic_and_matches_catalog(self):
        first = generate_lantern.build_lantern_glb()
        second = generate_lantern.build_lantern_glb()
        self.assertEqual(first, second)
        digest = hashlib.sha256(first).hexdigest()
        self.assertEqual(digest, catalog_asset()["metadata"]["sha256"])

    def test_cli_output_matches_in_process_build(self):
        with tempfile.TemporaryDirectory() as temp:
            out_a = Path(temp) / "a.glb"
            out_b = Path(temp) / "nested" / "b.glb"
            for out in (out_a, out_b):
                result = subprocess.run(
                    [sys.executable, str(GENERATOR), "--out", str(out)],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            expected = generate_lantern.build_lantern_glb()
            self.assertEqual(out_a.read_bytes(), expected)
            self.assertEqual(out_b.read_bytes(), expected)

    def test_generated_glb_is_a_valid_skeletonless_prop(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "lantern.glb"
            out.write_bytes(generate_lantern.build_lantern_glb())
            doc = gltf.load_gltf_json(out)
        self.assertEqual([n["name"] for n in doc["nodes"]],
                         ["Lantern", "LanternFrame", "LanternCore"])
        self.assertNotIn("skins", doc)
        self.assertEqual(gltf.joint_count(doc), 0)
        self.assertEqual(len(doc["meshes"]), 2)
        materials = {m["name"]: m for m in doc["materials"]}
        self.assertIn("emissiveFactor", materials["lantern_flame_core"])

    def test_catalog_record_is_a_valid_candidate(self):
        catalog = validate_catalog(load("lantern_procedural_catalog.json"))
        asset = catalog_asset()
        self.assertEqual(asset["kind"], "prop")
        self.assertEqual(asset["status"], "candidate")
        self.assertEqual(asset["uri"], URI)
        self.assertEqual(asset["license"], "CC0-1.0")
        self.assertIn("generate_lantern.py", asset["source"])
        self.assertEqual(catalog["characters"], [])


class CreatePromoteChainTests(unittest.TestCase):
    def test_create_review_promote_use_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / "store"
            glb_path = store / URI
            self.assertEqual(
                generate_lantern.main(["--out", str(glb_path)]), 0)
            digest = hashlib.sha256(glb_path.read_bytes()).hexdigest()

            db = Path(temp) / "library.db"
            self.assertEqual(main([
                "register", "--db", str(db),
                "--catalog", "lantern_procedural_catalog.json"]), 0)

            lib = Library(db)
            try:
                lib.init()
                # Quarantine: the new asset sits in the candidate store,
                # unreviewed, provenance attached.
                candidates = {c["asset_id"]: c for c in list_candidates(lib)}
                self.assertIn(ASSET_ID, candidates)
                entry = candidates[ASSET_ID]
                self.assertEqual(entry["review"], "unreviewed")
                self.assertEqual(entry["license"], "CC0-1.0")
                self.assertIn("generate_lantern.py", entry["source"])

                # Review through the CLI (F5.2 flow): an approve record.
                # Reviews are advisory — the asset stays a candidate.
                self.assertEqual(main([
                    "review", "--db", str(db), "--asset", ASSET_ID,
                    "--reviewer", "f5.3-proof", "--decision", "approve",
                    "--note", "Procedural original; generator + hash "
                              "verified."]), 0)
                self.assertEqual(
                    latest_review(lib, ASSET_ID)["decision"], "approve")
                self.assertEqual(lib.get_asset(ASSET_ID)["status"],
                                 "candidate")
                self.assertIn(ASSET_ID,
                              {c["asset_id"] for c in list_candidates(lib)})

                # Promote through the real ADR-008 machine gates.
                result = promote_asset(lib, ASSET_ID, store)
                self.assertTrue(result["promoted"], result["gates"])
                gates = {g["gate"]: g["passed"] for g in result["gates"]}
                self.assertEqual(gates, {"status_is_candidate": True,
                                         "source_present": True,
                                         "hash_match": True})
                self.assertEqual(result["pending"],
                                 ["visual_review", "owner_hardware_visual"])
                self.assertEqual(lib.get_asset(ASSET_ID)["status"],
                                 "approved")
                # Approved means out of the quarantine view.
                self.assertNotIn(
                    ASSET_ID, {c["asset_id"] for c in list_candidates(lib)})

                # Use: a scene declares the lantern as a prop and picks
                # it up; the manifest export pins the promoted asset.
                scene = {
                    "schema_version": "1.0.0",
                    "scene_id": "lantern_pickup_proof",
                    "environment_id": "preview_stage",
                    "actors": [{"id": "traveler",
                                "recipe_id": "traveler_01",
                                "color": "#a1b2c3"}],
                    "props": [{"id": "lantern", "asset_id": ASSET_ID,
                               "position": [0.2, 0.78, 1.7]}],
                    "events": [
                        {"at_ms": 0, "op": "spawn", "actor_id": "traveler",
                         "position": [0, 0, 1.7]},
                        {"at_ms": 100, "op": "interact",
                         "actor_id": "traveler", "action": "pick_up",
                         "prop_id": "lantern", "duration_ms": 2000},
                    ],
                }
                self.assertIs(validate_scene(scene), scene)
                base = {"schema_version": "1.0.0", "clips": {},
                        "recipes": {}}
                enriched = enrich_manifest(base, lib, store,
                                           scene["props"])
                pin = enriched["props"]["lantern"]
                self.assertEqual(pin["asset_id"], ASSET_ID)
                self.assertEqual(pin["uri"], URI)
                self.assertEqual(pin["status"], "approved")
                self.assertEqual(pin["version"], "1.0.0")
                self.assertEqual(pin["sha256"], digest)
            finally:
                lib.close()


if __name__ == "__main__":
    unittest.main()
