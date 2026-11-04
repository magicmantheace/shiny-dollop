"""F5.2 missing-action reports, provenance review flow and the
quarantined candidate store: the report math against the clip-need
mapping the Godot preview's dispatch actually uses (godot/main.gd),
the report_missing_actions job handler, migration 4 (append-only
reviews), the review API (records only — status and ADR-008
promotion untouched), and the candidates view + CLI verbs."""
import copy
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from studio import reviews
from studio.cli import load, main
from studio.jobs import enqueue, get_job, run_worker
from studio.library import Library
from studio.migrations import MIGRATIONS, applied_versions
from studio.reports import (clip_keys_from_manifest, missing_action_report)
from studio.reviews import (ReviewError, latest_review, list_candidates,
                            record_review, review_history)
from studio.schema import validate_scene

ALL_CLIP_KEYS = set(load("asset_manifest.json")["clips"])


def make_asset(asset_id, *, status="candidate", source=None, license_=None):
    asset = {
        "schema_version": "1.0.0",
        "asset_id": asset_id,
        "kind": "prop",
        "uri": f"assets/props/{asset_id}.glb",
        "status": status,
        "tags": ["probe"],
        "rig_id": None,
        "metadata": {"version": "1.0.0"},
    }
    if source is not None:
        asset["source"] = source
    if license_ is not None:
        asset["license"] = license_
    return asset


def simple_scene(events, props=None):
    scene = {
        "schema_version": "1.0.0",
        "scene_id": "report_probe",
        "environment_id": "preview_stage",
        "actors": [{"id": "anna", "recipe_id": "anna_01",
                    "color": "#aa3333"}],
        "events": events,
    }
    if props is not None:
        scene["props"] = props
    return validate_scene(scene)


SPAWN = {"at_ms": 0, "op": "spawn", "actor_id": "anna",
         "position": [0, 0, 0]}


class MissingActionReportTests(unittest.TestCase):
    def test_speak_gap_yields_exactly_one_record(self):
        scene = simple_scene([
            SPAWN,
            {"at_ms": 500, "op": "speak", "actor_id": "anna",
             "line": "Hello."},
        ])
        records = missing_action_report(scene, ALL_CLIP_KEYS - {"speak"})
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["scene_id"], "report_probe")
        self.assertEqual(record["event_index"], 1)
        self.assertEqual(record["op"], "speak")
        self.assertEqual(record["actor_id"], "anna")
        self.assertEqual(record["needed"], "speak")
        self.assertIn("'speak'", record["reason"])

    def test_fully_covered_demo_scene_returns_empty(self):
        scene = validate_scene(load("scene_demo.json"))
        manifest = load("asset_manifest.json")
        self.assertEqual(
            missing_action_report(scene, manifest["clips"]), [])
        self.assertEqual(
            missing_action_report(scene, clip_keys_from_manifest(manifest)),
            [])

    def test_emote_and_camera_consume_no_clip(self):
        # The real mapping (godot/main.gd _dispatch): emote only logs
        # the emotion and camera only frames a shot — neither looks a
        # clip up. With only 'idle' provided (the spawn's need), both
        # events must produce no records even though the manifest's
        # emote_* keys are absent from the provided set.
        scene = simple_scene([
            SPAWN,
            {"at_ms": 50, "op": "camera", "shot": "wide"},
            {"at_ms": 100, "op": "emote", "actor_id": "anna",
             "emotion": "happy", "intensity": 0.5},
        ])
        self.assertEqual(missing_action_report(scene, {"idle"}), [])

    def test_spawn_and_move_gaps(self):
        scene = simple_scene([
            SPAWN,
            {"at_ms": 100, "op": "move", "actor_id": "anna",
             "target": [1, 0, 0], "duration_ms": 1000},
        ])
        records = missing_action_report(scene, ALL_CLIP_KEYS - {"idle"})
        self.assertEqual([(r["event_index"], r["needed"]) for r in records],
                         [(0, "idle")])
        records = missing_action_report(
            scene, ALL_CLIP_KEYS - {"idle", "walk"})
        self.assertEqual([(r["event_index"], r["needed"]) for r in records],
                         [(0, "idle"), (1, "walk")])

    def test_interact_gaps_follow_the_action_mapping(self):
        props = [{"id": "mug", "asset_id": "mug_wood_01",
                  "position": [0.5, 0, 0]}]
        scene = simple_scene([
            SPAWN,
            {"at_ms": 100, "op": "interact", "actor_id": "anna",
             "action": "pick_up", "prop_id": "mug", "duration_ms": 2000},
            {"at_ms": 3000, "op": "interact", "actor_id": "anna",
             "action": "drink", "prop_id": "mug", "duration_ms": 1500},
            {"at_ms": 5000, "op": "interact", "actor_id": "anna",
             "action": "put_down", "prop_id": "mug", "duration_ms": 1500},
            {"at_ms": 7000, "op": "interact", "actor_id": "anna",
             "action": "sit", "target": [1, 0, 0], "duration_ms": 2000},
        ], props=props)
        keys = ALL_CLIP_KEYS - {"consume", "sit_idle"}
        records = missing_action_report(scene, keys)
        self.assertEqual(
            [(r["event_index"], r["op"], r["needed"]) for r in records],
            [(2, "interact", "consume"), (4, "interact", "sit_idle")])
        # Every interact key missing -> one record per consumed key,
        # in event order (pick_up, drink, put_down, sit x2).
        keys = ALL_CLIP_KEYS - {"pickup", "consume", "interact",
                                "sit_enter", "sit_idle"}
        records = missing_action_report(scene, keys)
        self.assertEqual([r["needed"] for r in records],
                         ["pickup", "consume", "interact",
                          "sit_enter", "sit_idle"])

    def test_report_is_pure_and_deterministic(self):
        scene = simple_scene([
            SPAWN,
            {"at_ms": 500, "op": "speak", "actor_id": "anna",
             "line": "Hello."},
        ])
        before = copy.deepcopy(scene)
        first = missing_action_report(scene, {"idle"})
        second = missing_action_report(scene, {"idle"})
        self.assertEqual(first, second)
        self.assertEqual(scene, before)


class ReportJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lib = Library(Path(self.temp.name) / "test.db")
        self.addCleanup(self.lib.close)
        self.lib.init()
        self.scene = simple_scene([
            SPAWN,
            {"at_ms": 500, "op": "speak", "actor_id": "anna",
             "line": "Hello."},
        ])

    def run_one(self, payload):
        job_id = enqueue(self.lib, "report_missing_actions", payload)
        summaries = run_worker(self.lib, "tester")
        self.assertEqual(len(summaries), 1)
        return get_job(self.lib, job_id)

    def test_handler_completes_with_report(self):
        job = self.run_one({"scene": self.scene,
                            "clip_keys": sorted(ALL_CLIP_KEYS - {"speak"})})
        self.assertEqual(job["state"], "done")
        self.assertEqual(job["result"]["missing_count"], 1)
        self.assertEqual(job["result"]["missing"][0]["needed"], "speak")
        self.assertEqual(job["result"]["missing"][0]["event_index"], 1)

    def test_handler_accepts_a_manifest_document(self):
        manifest = {"clips": {k: {} for k in ALL_CLIP_KEYS}}
        job = self.run_one({"scene": self.scene, "manifest": manifest})
        self.assertEqual(job["state"], "done")
        self.assertEqual(job["result"], {"missing_count": 0, "missing": []})

    def test_invalid_scene_completes_with_validation_error(self):
        job = self.run_one({"scene": {"schema_version": "9.9.9"},
                            "clip_keys": []})
        self.assertEqual(job["state"], "done")
        self.assertEqual(job["result"]["valid"], False)
        self.assertIn("error", job["result"])

    def test_payload_without_keys_or_manifest_fails(self):
        job = self.run_one({"scene": self.scene})
        self.assertEqual(job["state"], "failed")
        self.assertIn("clip_keys", job["error"])

    def test_payload_without_scene_fails(self):
        job = self.run_one({"clip_keys": []})
        self.assertEqual(job["state"], "failed")


class ReviewTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.lib = Library(self.base / "test.db")
        self.addCleanup(self.lib.close)
        self.lib.init()


class MigrationFourTests(ReviewTestCase):
    def test_fresh_db_has_reviews_table(self):
        self.assertEqual(applied_versions(self.lib.db), [1, 2, 3, 4, 5])
        cols = {r[1] for r in self.lib.db.execute("PRAGMA table_info(reviews)")}
        self.assertEqual(cols, {"review_id", "asset_id", "reviewer",
                                "decision", "note", "created_at"})

    def test_v3_shaped_db_upgrades_with_rows_intact(self):
        path = self.base / "v3.db"
        raw = sqlite3.connect(str(path))
        raw.execute(
            "CREATE TABLE schema_migrations ("
            "version INTEGER PRIMARY KEY, name TEXT NOT NULL, "
            "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        for version, name, sql in MIGRATIONS[:3]:
            raw.executescript(sql() if callable(sql) else sql)
            raw.execute(
                "INSERT INTO schema_migrations(version, name) VALUES(?,?)",
                (version, name))
        raw.execute(
            "INSERT INTO assets(asset_id,kind,uri,rig_id,status,tags_json,"
            "metadata_json,source,license) VALUES(?,?,?,?,?,?,?,?,?)",
            ("kept_asset", "prop", "assets/props/kept_asset.glb", None,
             "candidate", "[]", "{}", "unit test", "CC0-1.0"))
        raw.execute(
            "INSERT INTO jobs(kind, payload_json) VALUES(?,?)",
            ("validate_scene", "{}"))
        raw.commit()
        raw.close()
        lib = Library(path)
        self.addCleanup(lib.close)
        lib.init()
        self.assertEqual(applied_versions(lib.db), [1, 2, 3, 4, 5])
        asset = lib.get_asset("kept_asset")
        self.assertEqual(asset["source"], "unit test")
        self.assertEqual(asset["license"], "CC0-1.0")
        jobs = lib.db.execute("SELECT kind FROM jobs").fetchall()
        self.assertEqual([r["kind"] for r in jobs], ["validate_scene"])
        self.assertEqual(
            lib.db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0], 0)


class ReviewApiTests(ReviewTestCase):
    def setUp(self):
        super().setUp()
        self.lib.put_asset(make_asset("mug_wood_01", source="Example pack",
                                      license_="CC0-1.0"))

    def test_record_latest_and_history(self):
        first = record_review(self.lib, "mug_wood_01", "nyx", "needs_info",
                              note="check the license file")
        self.assertEqual(first["asset_id"], "mug_wood_01")
        self.assertEqual(first["decision"], "needs_info")
        self.assertEqual(first["note"], "check the license file")
        self.assertIsNotNone(first["created_at"])
        self.assertEqual(latest_review(self.lib, "mug_wood_01"), first)
        second = record_review(self.lib, "mug_wood_01", "owner", "approve")
        self.assertIsNone(second["note"])
        self.assertEqual(latest_review(self.lib, "mug_wood_01"), second)
        self.assertEqual(review_history(self.lib, "mug_wood_01"),
                         [first, second])

    def test_unreviewed_asset_has_no_latest_or_history(self):
        self.assertIsNone(latest_review(self.lib, "mug_wood_01"))
        self.assertEqual(review_history(self.lib, "mug_wood_01"), [])

    def test_unknown_asset_refused(self):
        with self.assertRaises(ReviewError):
            record_review(self.lib, "no_such_asset", "nyx", "approve")

    def test_bad_decision_refused(self):
        with self.assertRaises(ReviewError):
            record_review(self.lib, "mug_wood_01", "nyx", "shrug")

    def test_blank_reviewer_refused(self):
        with self.assertRaises(ReviewError):
            record_review(self.lib, "mug_wood_01", "  ", "approve")

    def test_review_does_not_change_asset_status(self):
        record_review(self.lib, "mug_wood_01", "owner", "approve")
        self.assertEqual(
            self.lib.get_asset("mug_wood_01")["status"], "candidate")


class CandidateStoreTests(ReviewTestCase):
    def setUp(self):
        super().setUp()
        self.lib.put_asset(make_asset("zeta_prop", source="Zeta pack",
                                      license_="MIT"))
        self.lib.put_asset(make_asset("alpha_prop"))
        self.lib.put_asset(make_asset("done_prop", status="approved",
                                      source="Done pack", license_="CC0-1.0"))

    def test_lists_only_candidates_sorted_with_provenance(self):
        entries = list_candidates(self.lib)
        self.assertEqual([e["asset_id"] for e in entries],
                         ["alpha_prop", "zeta_prop"])
        zeta = entries[1]
        self.assertEqual(zeta["source"], "Zeta pack")
        self.assertEqual(zeta["license"], "MIT")
        self.assertEqual(zeta["review"], reviews.UNREVIEWED)
        alpha = entries[0]
        self.assertIsNone(alpha["source"])
        self.assertIsNone(alpha["license"])

    def test_latest_review_decision_is_shown(self):
        record_review(self.lib, "alpha_prop", "nyx", "reject",
                      note="wrong rig")
        record_review(self.lib, "alpha_prop", "owner", "needs_info")
        entries = {e["asset_id"]: e for e in list_candidates(self.lib)}
        self.assertEqual(entries["alpha_prop"]["review"], "needs_info")
        self.assertEqual(entries["zeta_prop"]["review"], reviews.UNREVIEWED)

    def test_asset_leaves_the_view_when_its_status_changes(self):
        self.assertEqual(len(list_candidates(self.lib)), 2)
        self.lib.set_asset_status("alpha_prop", "approved")
        self.assertEqual([e["asset_id"] for e in list_candidates(self.lib)],
                         ["zeta_prop"])


class CandidateCliTests(ReviewTestCase):
    def run_cli(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main(argv)
        return rc, out.getvalue()

    def test_candidates_and_review_cli_round_trip(self):
        db = str(self.base / "cli.db")
        rc, _ = self.run_cli(["seed", "--db", db])
        self.assertEqual(rc, 0)
        rc, out = self.run_cli(["candidates", "--db", db])
        self.assertEqual(rc, 0)
        self.assertIn("mug_wood_01", out)
        self.assertIn("review=unreviewed", out)
        rc, out = self.run_cli(["review", "--db", db, "--asset",
                                "mug_wood_01", "--reviewer", "owner",
                                "--decision", "approve",
                                "--note", "license checked"])
        self.assertEqual(rc, 0)
        self.assertIn("Recorded review", out)
        rc, out = self.run_cli(["candidates", "--db", db])
        self.assertIn("review=approve", out)


class ReportMissingCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def write(self, name, doc):
        path = self.base / name
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path

    def run_cli(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main(argv)
        return rc, out.getvalue()

    def test_report_missing_cli(self):
        scene = simple_scene([
            SPAWN,
            {"at_ms": 500, "op": "speak", "actor_id": "anna",
             "line": "Hello."},
        ])
        scene_path = self.write("scene.json", scene)
        manifest = {"clips": {k: {} for k in ALL_CLIP_KEYS - {"speak"}}}
        manifest_path = self.write("manifest.json", manifest)
        rc, out = self.run_cli(["report-missing", "--scene",
                                str(scene_path), "--manifest",
                                str(manifest_path)])
        self.assertEqual(rc, 0)
        self.assertIn("1 missing action", out)
        self.assertIn("needs clip 'speak'", out)

    def test_report_missing_cli_all_covered(self):
        scene = validate_scene(load("scene_demo.json"))
        scene_path = self.write("scene.json", scene)
        manifest_path = self.write(
            "manifest.json", {"clips": {k: {} for k in ALL_CLIP_KEYS}})
        rc, out = self.run_cli(["report-missing", "--scene",
                                str(scene_path), "--manifest",
                                str(manifest_path)])
        self.assertEqual(rc, 0)
        self.assertIn("0 missing action", out)


if __name__ == "__main__":
    unittest.main()
