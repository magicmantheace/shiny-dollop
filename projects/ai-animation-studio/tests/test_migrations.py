"""F2.1 data foundation: versioned SQLite migrations + source/license records.

Covers the migration framework (fresh, legacy v1, idempotent, newer-than-code)
and the first-class optional `source`/`license` asset fields end to end:
validator, JSON Schema parity, library round-trip and the F1 catalog fixture.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from studio.cli import load
from studio.library import Library
from studio.migrations import DDL, LATEST_VERSION, MigrationError, applied_versions
from studio.schema import LICENSES, ValidationError, validate_asset, validate_catalog

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


def bare_asset(**overrides) -> dict:
    asset = {
        "schema_version": "1.0.0",
        "asset_id": "widget_01",
        "kind": "prop",
        "uri": "assets/props/widget_01.glb",
        "rig_id": None,
        "status": "candidate",
        "tags": ["widget"],
        "metadata": {},
    }
    asset.update(overrides)
    return asset


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def open_lib(self, name="test.db") -> Library:
        lib = Library(self.base / name)
        self.addCleanup(lib.close)
        return lib

    def test_fresh_db_migrates_to_latest(self):
        lib = self.open_lib()
        lib.init()
        self.assertEqual(applied_versions(lib.db), [1, 2, 3, 4])
        self.assertEqual(LATEST_VERSION, 4)
        cols = [r[1] for r in lib.db.execute("PRAGMA table_info(assets)")]
        self.assertIn("source", cols)
        self.assertIn("license", cols)
        rows = lib.db.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ).fetchall()
        self.assertEqual([r[0] for r in rows], [1, 2, 3, 4])
        self.assertTrue(all(r[1] for r in rows))

    def test_v1_shaped_db_upgrades_with_rows_intact(self):
        path = self.base / "legacy.db"
        raw = sqlite3.connect(str(path))
        raw.executescript(DDL.read_text(encoding="utf-8"))
        raw.execute(
            "INSERT INTO assets(asset_id,kind,uri,rig_id,status,tags_json,metadata_json) "
            "VALUES(?,?,?,?,?,?,?)",
            ("legacy_prop", "prop", "assets/props/legacy.glb", None,
             "approved", '["old"]', '{"version": "0.9.0"}'),
        )
        raw.execute(
            "INSERT INTO characters(character_id,rig_id,status,recipe_json) "
            "VALUES('legacy_char','studio_humanoid_v1','candidate','{}')")
        raw.commit()
        raw.close()
        lib = self.open_lib("legacy.db")
        lib.init()
        self.assertEqual(applied_versions(lib.db), [1, 2, 3, 4])
        asset = lib.get_asset("legacy_prop")
        self.assertIsNotNone(asset)
        self.assertEqual(asset["status"], "approved")
        self.assertEqual(asset["tags"], ["old"])
        self.assertEqual(asset["metadata"], {"version": "0.9.0"})
        self.assertIsNone(asset["source"])
        self.assertIsNone(asset["license"])
        rows = lib.db.execute("SELECT COUNT(*) FROM characters").fetchone()[0]
        self.assertEqual(rows, 1)

    def test_init_twice_is_noop(self):
        lib = self.open_lib()
        lib.init()
        lib.put_asset(bare_asset())
        before = lib.db.execute(
            "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
        ).fetchall()
        lib.init()
        after = lib.db.execute(
            "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
        ).fetchall()
        self.assertEqual(before, after)
        self.assertEqual(len(lib.list_assets()), 1)

    def test_newer_than_code_db_raises(self):
        lib = self.open_lib()
        lib.init()
        lib.db.execute(
            "INSERT INTO schema_migrations(version, name) VALUES(?,?)",
            (LATEST_VERSION + 1, "from_the_future"))
        lib.db.commit()
        lib.close()
        reopened = Library(self.base / "test.db")
        try:
            with self.assertRaises(MigrationError):
                reopened.init()
        finally:
            reopened.close()


class SourceLicenseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lib = Library(Path(self.temp.name) / "test.db")
        self.addCleanup(self.lib.close)
        self.lib.init()

    def test_round_trip_with_source_and_license(self):
        self.lib.put_asset(bare_asset(
            source="Quaternius UAL1 [Standard]", license="CC0-1.0"))
        got = self.lib.get_asset("widget_01")
        self.assertEqual(got["source"], "Quaternius UAL1 [Standard]")
        self.assertEqual(got["license"], "CC0-1.0")

    def test_round_trip_without_source_and_license(self):
        self.lib.put_asset(bare_asset())
        got = self.lib.get_asset("widget_01")
        self.assertIsNone(got["source"])
        self.assertIsNone(got["license"])

    def test_upsert_updates_source_and_license(self):
        self.lib.put_asset(bare_asset(license="unknown"))
        self.lib.put_asset(bare_asset(source="In-house", license="proprietary"))
        got = self.lib.get_asset("widget_01")
        self.assertEqual(got["source"], "In-house")
        self.assertEqual(got["license"], "proprietary")

    def test_invalid_license_rejected_by_validator_and_library(self):
        for bad in ("GPL-3.0", "cc0", "", None, 42):
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    validate_asset(bare_asset(license=bad))
                with self.assertRaises(ValidationError):
                    self.lib.put_asset(bare_asset(license=bad))

    def test_every_known_license_accepted(self):
        for lic in sorted(LICENSES):
            with self.subTest(license=lic):
                self.assertIs(validate_asset(bare_asset(license=lic))["license"], lic)

    def test_source_validation_bounds(self):
        self.assertEqual(validate_asset(bare_asset(source="x" * 256))["source"], "x" * 256)
        for bad in ("", "x" * 257, None, 7):
            with self.subTest(bad=repr(bad)[:20]):
                with self.assertRaises(ValidationError):
                    validate_asset(bare_asset(source=bad))

    def test_license_enum_matches_json_schema(self):
        doc = json.loads((SCHEMAS / "asset.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(doc["properties"]["license"]["enum"]), set(LICENSES))
        source = doc["properties"]["source"]
        self.assertEqual(source["minLength"], 1)
        self.assertEqual(source["maxLength"], 256)

    def test_catalog_fixture_carries_source_and_license(self):
        catalog = validate_catalog(load("quaternius_f1_catalog.json"))
        self.assertEqual(len(catalog["assets"]), 9)
        for asset in catalog["assets"]:
            self.assertTrue(asset["source"], asset["asset_id"])
            self.assertEqual(asset["license"], "CC0-1.0", asset["asset_id"])
        by_id = {a["asset_id"]: a for a in catalog["assets"]}
        self.assertEqual(by_id["superhero_male_fullbody"]["source"],
                         "Quaternius Universal Base Characters [Standard]")
        self.assertEqual(by_id["ual1_standard"]["source"], "Quaternius UAL1 [Standard]")
        self.assertEqual(by_id["ual2_standard_rm"]["source"], "Quaternius UAL2 [Standard]")
        self.assertEqual(by_id["kenney_furniture_kit"]["source"], "Kenney Furniture Kit")
        # And the records survive registration into the library.
        for asset in catalog["assets"]:
            self.lib.put_asset(asset)
        stored = self.lib.get_asset("kenney_furniture_kit")
        self.assertEqual(stored["source"], "Kenney Furniture Kit")
        self.assertEqual(stored["license"], "CC0-1.0")


if __name__ == "__main__":
    unittest.main()
