"""Promotion gates: candidate -> approved only through machine checks.

Fixtures are tiny synthetic GLBs built in a temp asset store; the real
F1 catalog promotion against the real store is exercised manually and
recorded in docs/IMPLEMENTATION_STATUS.md, not in the unit suite.
"""
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from studio.library import Library
from studio.promotion import promote_asset, promote_character


def write_glb(path: Path, joints: int = 2, clips: dict | None = None) -> None:
    doc = {
        "asset": {"version": "2.0"},
        "nodes": [{"name": f"joint_{i}"} for i in range(joints)],
        "skins": [{"joints": list(range(joints))}],
        "accessors": [{"max": [2.5]}, {}],
        "animations": [
            {"name": name, "samplers": [{"input": 0, "output": 1}], "channels": []}
            for name in (clips or {})
        ],
    }
    payload = json.dumps(doc).encode("utf-8")
    payload += b" " * (-len(payload) % 4)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"glTF" + struct.pack("<II", 2, 12 + 8 + len(payload))
        + struct.pack("<II", len(payload), 0x4E4F534A) + payload
    )


def motion_asset(path: Path, **meta_overrides) -> dict:
    meta = {
        "source": "synthetic",
        "license": "CC0-1.0",
        "version": "1.0.0",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "joints": 2,
        "clip_count": 1,
        "clips": {"Idle_Loop": 2.5},
    }
    meta.update(meta_overrides)
    return {
        "schema_version": "1.0.0",
        "asset_id": "synthetic_motion",
        "kind": "motion",
        "uri": "assets/animations/synthetic.glb",
        "rig_id": "studio_humanoid_v1",
        "status": "candidate",
        "tags": ["animation"],
        "metadata": meta,
    }


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "store"
        self.file = self.root / "assets/animations/synthetic.glb"
        write_glb(self.file, clips={"Idle_Loop": 2.5})
        self.lib = Library(base / "test.db")
        self.addCleanup(self.lib.close)
        self.lib.init()

    def test_promotion_success_records_gates_and_pending(self):
        self.lib.put_asset(motion_asset(self.file))
        result = promote_asset(self.lib, "synthetic_motion", self.root)
        self.assertTrue(result["promoted"], result["gates"])
        self.assertEqual(self.lib.get_asset("synthetic_motion")["status"], "approved")
        self.assertIn("visual_review", result["pending"])
        self.assertIn("owner_hardware_visual", result["pending"])
        rows = self.lib.db.execute(
            "SELECT check_name, passed FROM validation_runs WHERE asset_id='synthetic_motion'"
        ).fetchall()
        self.assertIn(("promotion", 1), [(r["check_name"], r["passed"]) for r in rows])

    def test_promotion_refuses_hash_mismatch(self):
        self.lib.put_asset(motion_asset(self.file, sha256="0" * 64))
        result = promote_asset(self.lib, "synthetic_motion", self.root)
        self.assertFalse(result["promoted"])
        self.assertEqual(self.lib.get_asset("synthetic_motion")["status"], "candidate")
        failed = {g["gate"] for g in result["gates"] if not g["passed"]}
        self.assertIn("hash_match", failed)

    def test_promotion_refuses_missing_file(self):
        asset = motion_asset(self.file)
        self.lib.put_asset(asset)
        result = promote_asset(self.lib, "synthetic_motion", self.root / "elsewhere")
        self.assertFalse(result["promoted"])
        failed = {g["gate"] for g in result["gates"] if not g["passed"]}
        self.assertIn("source_present", failed)

    def test_promotion_refuses_clip_inventory_mismatch(self):
        self.lib.put_asset(motion_asset(self.file, clips={"Nope_Loop": 2.5}))
        result = promote_asset(self.lib, "synthetic_motion", self.root)
        self.assertFalse(result["promoted"])
        failed = {g["gate"] for g in result["gates"] if not g["passed"]}
        self.assertIn("clip_inventory", failed)

    def test_character_promotion_requires_approved_body(self):
        self.lib.put_asset(motion_asset(self.file))
        self.lib.put_character({
            "schema_version": "1.0.0",
            "character_id": "synthetic_char",
            "rig_id": "studio_humanoid_v1",
            "body_base": "synthetic_motion",
            "head": "synthetic_head",
            "hair": "synthetic_hair",
            "outfit": [],
            "colors": {},
            "status": "candidate",
        })
        refused = promote_character(self.lib, "synthetic_char")
        self.assertFalse(refused["promoted"])
        self.assertTrue(promote_asset(self.lib, "synthetic_motion", self.root)["promoted"])
        promoted = promote_character(self.lib, "synthetic_char")
        self.assertTrue(promoted["promoted"], promoted["gates"])
        self.assertEqual(self.lib.get_character("synthetic_char")["status"], "approved")


if __name__ == "__main__":
    unittest.main()
