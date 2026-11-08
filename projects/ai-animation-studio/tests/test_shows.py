"""F6 foundation: show manifests, world state, scene memory, continuity
application and show package export/verification (studio/shows.py).

The memory-capture numbers are hand-computed from ADR-009 timing and
the F4.2 interact windows: derived speak holds clamp to the 800 ms
minimum at these line lengths, pick_up occupies its full window, and a
move's arrival (dispatch + duration) feeds the makespan.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from studio.cli import main
from studio.ipc import read_ipc
from studio.library import Library
from studio.migrations import MIGRATIONS, applied_versions
from studio.schema import ValidationError
from studio.shows import (MAX_SCENES, SHOW_KEYS, SHOW_VERSION, ShowError,
                          apply_continuity, capture_scene_memory,
                          export_show_package, get_state, latest_memory,
                          record_scene_memory, set_state, snapshot_state,
                          validate_show, verify_show_package)

ROOT = Path(__file__).resolve().parents[1]


def _actor(actor_id: str) -> dict:
    return {"id": actor_id, "recipe_id": f"{actor_id}_01", "color": "#808080"}


def make_scene_one() -> dict:
    """pick_up -> move -> drink -> put_down, plus a bystander who only
    speaks and an actor who only spawns. Hand-computed memory:
    solo ends at [1.2, 0, 0.5] empty-handed, the mug rests at its
    put_down target [1.4, 0.78, 0.5], makespan 10800 (the final speak's
    clamped 800 ms window from 10000)."""
    return {
        "schema_version": "1.0.0",
        "scene_id": "show_scene_one",
        "environment_id": "preview_stage",
        "actors": [_actor("solo"), _actor("still"), _actor("leaver")],
        "props": [{"id": "mug", "asset_id": "mug_prop_asset",
                   "position": [0.2, 0.78, 0.3]}],
        "events": [
            {"at_ms": 0, "op": "spawn", "actor_id": "solo", "position": [0, 0, 0]},
            {"at_ms": 0, "op": "spawn", "actor_id": "still", "position": [2.0, 0, 1.0]},
            {"at_ms": 0, "op": "spawn", "actor_id": "leaver", "position": [-2.0, 0, 1.0]},
            {"at_ms": 100, "op": "interact", "actor_id": "solo",
             "action": "pick_up", "prop_id": "mug", "duration_ms": 2000},
            {"at_ms": 2000, "op": "speak", "actor_id": "still", "line": "Mind the step."},
            {"at_ms": 3000, "op": "move", "actor_id": "solo",
             "target": [1.2, 0, 0.5], "duration_ms": 2000},
            {"at_ms": 6000, "op": "interact", "actor_id": "solo",
             "action": "drink", "prop_id": "mug", "duration_ms": 1000},
            {"at_ms": 8000, "op": "interact", "actor_id": "solo",
             "action": "put_down", "prop_id": "mug", "duration_ms": 1500,
             "target": [1.4, 0.78, 0.5]},
            {"at_ms": 10000, "op": "speak", "actor_id": "solo", "line": "Done."},
        ],
    }


def make_held_scene() -> dict:
    """Ends while solo still holds the mug: the mug's end position is
    its holder's end position. Makespan 5000 (the move's arrival)."""
    return {
        "schema_version": "1.0.0",
        "scene_id": "show_scene_held",
        "environment_id": "preview_stage",
        "actors": [_actor("solo")],
        "props": [{"id": "mug", "asset_id": "mug_prop_asset",
                   "position": [0.2, 0.78, 0.3]}],
        "events": [
            {"at_ms": 0, "op": "spawn", "actor_id": "solo", "position": [0, 0, 0]},
            {"at_ms": 100, "op": "interact", "actor_id": "solo",
             "action": "pick_up", "prop_id": "mug", "duration_ms": 2000},
            {"at_ms": 3000, "op": "move", "actor_id": "solo",
             "target": [1.2, 0, 0.5], "duration_ms": 2000},
        ],
    }


def make_seated_scene() -> dict:
    """Sit at [0.5, 0, 1.0], then speak seated. Makespan 2800 (the
    clamped 800 ms speak window from 2000)."""
    return {
        "schema_version": "1.0.0",
        "scene_id": "show_scene_seated",
        "environment_id": "preview_stage",
        "actors": [_actor("solo")],
        "events": [
            {"at_ms": 0, "op": "spawn", "actor_id": "solo", "position": [0, 0, 0]},
            {"at_ms": 100, "op": "interact", "actor_id": "solo",
             "action": "sit", "target": [0.5, 0, 1.0], "duration_ms": 1000},
            {"at_ms": 2000, "op": "speak", "actor_id": "solo", "line": "Seated."},
        ],
    }


def make_scene_two() -> dict:
    """The next scene, authored naively: solo's spawn resets to the
    origin, a newcomer joins, leaver is gone, the mug is back at its
    original declared spot."""
    return {
        "schema_version": "1.0.0",
        "scene_id": "show_scene_two",
        "environment_id": "preview_stage",
        "actors": [_actor("solo"), _actor("still"), _actor("newcomer")],
        "props": [{"id": "mug", "asset_id": "mug_prop_asset",
                   "position": [0.2, 0.78, 0.3]}],
        "events": [
            {"at_ms": 0, "op": "spawn", "actor_id": "solo", "position": [0, 0, 0]},
            {"at_ms": 0, "op": "spawn", "actor_id": "still", "position": [2.0, 0, 1.0]},
            {"at_ms": 0, "op": "spawn", "actor_id": "newcomer", "position": [3.0, 0, 0]},
            {"at_ms": 200, "op": "speak", "actor_id": "solo", "line": "Back again."},
            {"at_ms": 2000, "op": "speak", "actor_id": "newcomer", "line": "Hello."},
        ],
    }


def make_show() -> dict:
    return {
        "schema_version": SHOW_VERSION,
        "show_id": "test_show",
        "title": "Test Show",
        "scenes": [
            {"scene_id": "show_scene_one", "scene": make_scene_one()},
            {"scene_id": "show_scene_two", "scene": make_scene_two()},
        ],
    }


def _spawn_position(scene: dict, actor_id: str) -> list:
    for event in scene["events"]:
        if event["op"] == "spawn" and event["actor_id"] == actor_id:
            return event["position"]
    raise AssertionError(f"no spawn for {actor_id}")


class ShowValidationTests(unittest.TestCase):
    def test_valid_show_accepted(self):
        show = make_show()
        self.assertIs(validate_show(show), show)

    def test_example_show_accepted(self):
        show = json.loads(
            (ROOT / "examples" / "show_tavern_evening.json").read_text(encoding="utf-8"))
        self.assertIs(validate_show(show), show)
        self.assertEqual(show["show_id"], "tavern_evening")

    def test_unknown_top_level_key_refused(self):
        show = make_show()
        show["poster"] = "x"
        with self.assertRaises(ValidationError):
            validate_show(show)

    def test_wrong_version_refused(self):
        show = make_show()
        show["schema_version"] = "2.0.0"
        with self.assertRaises(ValidationError):
            validate_show(show)

    def test_bad_show_id_refused(self):
        show = make_show()
        show["show_id"] = "Test Show"
        with self.assertRaises(ValidationError):
            validate_show(show)

    def test_missing_title_refused(self):
        show = make_show()
        del show["title"]
        with self.assertRaises(ValidationError):
            validate_show(show)

    def test_no_scenes_refused(self):
        show = make_show()
        show["scenes"] = []
        with self.assertRaises(ValidationError):
            validate_show(show)

    def test_duplicate_scene_ids_refused(self):
        show = make_show()
        show["scenes"][1] = {"scene_id": "show_scene_one", "scene": make_scene_one()}
        with self.assertRaises(ValidationError):
            validate_show(show)

    def test_entry_scene_id_mismatch_refused(self):
        show = make_show()
        show["scenes"][1]["scene_id"] = "show_scene_other"
        with self.assertRaises(ValidationError):
            validate_show(show)

    def test_invalid_inline_scene_refused(self):
        show = make_show()
        broken = make_scene_two()
        broken["events"].append(
            {"at_ms": 3000, "op": "speak", "actor_id": "ghost", "line": "Boo."})
        show["scenes"][1] = {"scene_id": "show_scene_two", "scene": broken}
        with self.assertRaises(ShowError):
            validate_show(show)

    def test_entry_unknown_key_refused(self):
        show = make_show()
        show["scenes"][0]["notes"] = "hi"
        with self.assertRaises(ValidationError):
            validate_show(show)

    def test_json_schema_parity(self):
        doc = json.loads(
            (ROOT / "schemas" / "show.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["properties"]["schema_version"]["const"], SHOW_VERSION)
        self.assertEqual(set(doc["required"]), set(SHOW_KEYS))
        scenes = doc["properties"]["scenes"]
        self.assertEqual(scenes["minItems"], 1)
        self.assertEqual(scenes["maxItems"], MAX_SCENES)
        self.assertEqual(set(scenes["items"]["required"]), {"scene_id", "scene"})
        self.assertEqual(doc["properties"]["title"]["minLength"], 1)
        self.assertEqual(doc["properties"]["title"]["maxLength"], 256)


class MemoryCaptureTests(unittest.TestCase):
    def test_memory_math_move_pickup_putdown(self):
        memory = capture_scene_memory(make_scene_one())
        self.assertEqual(memory["scene_id"], "show_scene_one")
        self.assertEqual(memory["makespan_ms"], 10800)
        self.assertEqual(memory["actors"]["solo"],
                         {"position": [1.2, 0, 0.5], "holding": None, "seated": False})
        self.assertEqual(memory["actors"]["still"],
                         {"position": [2.0, 0, 1.0], "holding": None, "seated": False})
        self.assertEqual(memory["actors"]["leaver"],
                         {"position": [-2.0, 0, 1.0], "holding": None, "seated": False})
        self.assertEqual(memory["props"]["mug"],
                         {"position": [1.4, 0.78, 0.5], "held_by": None})

    def test_held_prop_ends_at_holder_position(self):
        memory = capture_scene_memory(make_held_scene())
        self.assertEqual(memory["makespan_ms"], 5000)
        self.assertEqual(memory["actors"]["solo"]["holding"], "mug")
        self.assertEqual(memory["props"]["mug"],
                         {"position": [1.2, 0, 0.5], "held_by": "solo"})

    def test_seated_state_and_sit_target(self):
        memory = capture_scene_memory(make_seated_scene())
        self.assertEqual(memory["makespan_ms"], 2800)
        self.assertEqual(memory["actors"]["solo"],
                         {"position": [0.5, 0, 1.0], "holding": None, "seated": True})

    def test_put_down_without_target_releases_at_holder(self):
        scene = make_held_scene()
        scene["events"].append(
            {"at_ms": 6000, "op": "interact", "actor_id": "solo",
             "action": "put_down", "prop_id": "mug", "duration_ms": 1000})
        memory = capture_scene_memory(scene)
        self.assertEqual(memory["actors"]["solo"]["holding"], None)
        self.assertEqual(memory["props"]["mug"],
                         {"position": [1.2, 0, 0.5], "held_by": None})

    def test_capture_is_pure(self):
        scene = make_scene_one()
        before = copy.deepcopy(scene)
        capture_scene_memory(scene)
        self.assertEqual(scene, before)


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.memory = capture_scene_memory(make_scene_one())
        self.scene_two = make_scene_two()

    def test_spawn_and_prop_positions_replaced(self):
        applied, _notes = apply_continuity(self.scene_two, self.memory)
        self.assertEqual(_spawn_position(applied, "solo"), [1.2, 0, 0.5])
        self.assertEqual(_spawn_position(applied, "still"), [2.0, 0, 1.0])
        self.assertEqual(_spawn_position(applied, "newcomer"), [3.0, 0, 0])
        prop = applied["props"][0]
        self.assertEqual(prop["position"], [1.4, 0.78, 0.5])

    def test_input_scene_never_mutated(self):
        before = copy.deepcopy(self.scene_two)
        applied, _notes = apply_continuity(self.scene_two, self.memory)
        self.assertEqual(self.scene_two, before)
        self.assertIsNot(applied, self.scene_two)
        # The copy must not alias the memory's position lists either.
        applied["events"][0]["position"][0] = 99
        self.assertEqual(self.memory["actors"]["solo"]["position"], [1.2, 0, 0.5])

    def test_notes_cover_changes_and_misses(self):
        _applied, notes = apply_continuity(self.scene_two, self.memory)
        joined = "\n".join(notes)
        self.assertIn("actor solo: spawn position [0, 0, 0] -> [1.2, 0, 0.5]", joined)
        self.assertIn("actor still: spawn already at memory position", joined)
        self.assertIn("actor newcomer: no memory", joined)
        self.assertIn("actor leaver: in memory but not in this scene", joined)
        self.assertIn("prop mug: declared position [0.2, 0.78, 0.3] -> [1.4, 0.78, 0.5]",
                      joined)

    def test_second_application_is_stable(self):
        applied, _notes = apply_continuity(self.scene_two, self.memory)
        again, notes = apply_continuity(applied, self.memory)
        self.assertEqual(again, applied)
        self.assertIn("already at memory position", "\n".join(notes))

    def test_no_memory_applies_nothing(self):
        applied, notes = apply_continuity(self.scene_two, None)
        self.assertEqual(applied, self.scene_two)
        self.assertIsNot(applied, self.scene_two)
        self.assertEqual(notes, ["no prior scene memory: no continuity applied"])

    def test_held_prop_note_names_holder(self):
        memory = capture_scene_memory(make_held_scene())
        _applied, notes = apply_continuity(self.scene_two, memory)
        joined = "\n".join(notes)
        self.assertIn("prop mug: declared position [0.2, 0.78, 0.3] -> [1.2, 0, 0.5]",
                      joined)
        self.assertIn("held by solo", joined)

    def test_holdings_are_not_forced_into_the_document(self):
        memory = capture_scene_memory(make_held_scene())
        applied, _notes = apply_continuity(self.scene_two, memory)
        # No holding state appears anywhere in the applied scene document.
        self.assertNotIn("holding", json.dumps(applied))


class ShowDbTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.lib = Library(self.base / "test.db")
        self.addCleanup(self.lib.close)
        self.lib.init()


class WorldStateTests(ShowDbTestCase):
    def test_round_trip_and_overwrite(self):
        set_state(self.lib, "inn_name", "The Prancing Pony")
        set_state(self.lib, "rooms_free", 3)
        set_state(self.lib, "ledger", {"owed": [1, 2], "paid": True})
        self.assertEqual(get_state(self.lib, "inn_name"), "The Prancing Pony")
        self.assertEqual(get_state(self.lib, "rooms_free"), 3)
        self.assertEqual(get_state(self.lib, "ledger"), {"owed": [1, 2], "paid": True})
        set_state(self.lib, "rooms_free", 2)
        self.assertEqual(get_state(self.lib, "rooms_free"), 2)

    def test_missing_key_returns_default(self):
        self.assertIsNone(get_state(self.lib, "absent"))
        self.assertEqual(get_state(self.lib, "absent", "fallback"), "fallback")

    def test_snapshot_returns_everything(self):
        set_state(self.lib, "b_key", [1])
        set_state(self.lib, "a_key", {"x": None})
        self.assertEqual(snapshot_state(self.lib),
                         {"a_key": {"x": None}, "b_key": [1]})

    def test_non_serializable_value_refused(self):
        with self.assertRaises(ShowError):
            set_state(self.lib, "bad", object())
        self.assertIsNone(get_state(self.lib, "bad"))

    def test_scene_memory_records_and_latest(self):
        first = capture_scene_memory(make_scene_one())
        second = capture_scene_memory(make_scene_two())
        id1 = record_scene_memory(self.lib, "test_show", first)
        id2 = record_scene_memory(self.lib, "test_show", second)
        self.assertLess(id1, id2)
        self.assertEqual(latest_memory(self.lib, "test_show"), second)
        self.assertEqual(
            latest_memory(self.lib, "test_show", scene_id="show_scene_one"), first)
        self.assertIsNone(latest_memory(self.lib, "unknown_show"))
        self.assertIsNone(
            latest_memory(self.lib, "test_show", scene_id="show_scene_held"))


class MigrationFiveTests(ShowDbTestCase):
    def test_fresh_db_has_world_state_tables(self):
        self.assertEqual(applied_versions(self.lib.db), [1, 2, 3, 4, 5])
        world_cols = {r[1] for r in self.lib.db.execute("PRAGMA table_info(world_state)")}
        self.assertEqual(world_cols, {"key", "value_json", "updated_at"})
        memory_cols = {r[1] for r in self.lib.db.execute("PRAGMA table_info(scene_memory)")}
        self.assertEqual(memory_cols,
                         {"memory_id", "show_id", "scene_id", "memory_json", "recorded_at"})

    def test_v4_shaped_db_upgrades_with_rows_intact(self):
        path = self.base / "v4.db"
        raw = sqlite3.connect(str(path))
        raw.execute(
            "CREATE TABLE schema_migrations ("
            "version INTEGER PRIMARY KEY, name TEXT NOT NULL, "
            "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        for version, name, sql in MIGRATIONS[:4]:
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
            "INSERT INTO reviews(asset_id, reviewer, decision) VALUES(?,?,?)",
            ("kept_asset", "unit", "approve"))
        raw.commit()
        raw.close()
        lib = Library(path)
        self.addCleanup(lib.close)
        lib.init()
        self.assertEqual(applied_versions(lib.db), [1, 2, 3, 4, 5])
        self.assertEqual(lib.get_asset("kept_asset")["source"], "unit test")
        self.assertEqual(
            lib.db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0], 1)
        # The new store is usable on the upgraded database.
        set_state(lib, "post_upgrade", True)
        self.assertEqual(get_state(lib, "post_upgrade"), True)
        record_scene_memory(lib, "test_show", capture_scene_memory(make_scene_one()))
        self.assertEqual(
            latest_memory(lib, "test_show")["scene_id"], "show_scene_one")


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.show = make_show()
        self.out = self.base / "pkg"
        self.package = export_show_package(self.show, self.out)

    def test_export_layout_and_hashes(self):
        self.assertTrue((self.out / "show.json").is_file())
        self.assertTrue((self.out / "package.json").is_file())
        self.assertEqual(set(self.package["exported_files"]),
                         {"show.json", "scenes/show_scene_one.json",
                          "scenes/show_scene_two.json"})
        self.assertEqual(self.package["show_id"], "test_show")
        for rel, recorded in self.package["exported_files"].items():
            actual = hashlib.sha256((self.out / rel).read_bytes()).hexdigest()
            self.assertEqual(actual, recorded)
        # Each scene file is a readable IPC envelope carrying its scene.
        scene = read_ipc(self.out / "scenes" / "show_scene_one.json")
        self.assertEqual(scene["scene_id"], "show_scene_one")

    def test_verify_passes(self):
        summary = verify_show_package(self.out)
        self.assertEqual(summary, {"show_id": "test_show", "scene_count": 2,
                                   "files_checked": 3})

    def test_tampered_scene_fails_naming_the_file(self):
        path = self.out / "scenes" / "show_scene_two.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ShowError) as ctx:
            verify_show_package(self.out)
        self.assertIn("scenes/show_scene_two.json", str(ctx.exception))

    def test_tampered_manifest_fails_naming_the_file(self):
        path = self.out / "show.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["title"] = "Forged Title"
        path.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(ShowError) as ctx:
            verify_show_package(self.out)
        self.assertIn("show.json", str(ctx.exception))

    def test_missing_scene_file_fails_naming_the_file(self):
        (self.out / "scenes" / "show_scene_one.json").unlink()
        with self.assertRaises(ShowError) as ctx:
            verify_show_package(self.out)
        self.assertIn("scenes/show_scene_one.json", str(ctx.exception))

    def test_unlisted_scene_file_fails_naming_the_file(self):
        (self.out / "scenes" / "sneaked_in.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ShowError) as ctx:
            verify_show_package(self.out)
        self.assertIn("scenes/sneaked_in.json", str(ctx.exception))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.show_path = self.base / "show.json"
        self.show_path.write_text(json.dumps(make_show()), encoding="utf-8")
        self.db = str(self.base / "cli.db")

    def run_cli(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main(argv)
        return rc, out.getvalue()

    def test_continuity_records_chain_and_prints_notes(self):
        rc, _ = self.run_cli(["init-db", "--db", self.db])
        self.assertEqual(rc, 0)
        rc, out = self.run_cli(["continuity", "--show", str(self.show_path),
                                "--scene-index", "1", "--db", self.db])
        self.assertEqual(rc, 0)
        self.assertIn("Memory show_scene_one: makespan 10800 ms", out)
        self.assertIn("Continuity into show_scene_two (from show_scene_one)", out)
        self.assertIn("actor solo: spawn position [0, 0, 0] -> [1.2, 0, 0.5]", out)
        lib = Library(Path(self.db))
        self.addCleanup(lib.close)
        lib.init()
        latest = latest_memory(lib, "test_show")
        self.assertEqual(latest["scene_id"], "show_scene_two")
        first = latest_memory(lib, "test_show", scene_id="show_scene_one")
        self.assertEqual(first["actors"]["solo"]["position"], [1.2, 0, 0.5])

    def test_continuity_first_scene_has_no_prior_memory(self):
        rc, out = self.run_cli(["continuity", "--show", str(self.show_path),
                                "--scene-index", "0", "--db", self.db])
        self.assertEqual(rc, 0)
        self.assertIn("first scene; no prior memory to apply", out)
        # The DB did not exist, so nothing was recorded and none created.
        self.assertIn("memories were not recorded", out)
        self.assertFalse(Path(self.db).exists())

    def test_continuity_requires_scene_index(self):
        with self.assertRaises(SystemExit):
            self.run_cli(["continuity", "--show", str(self.show_path)])

    def test_export_and_verify_show_cli(self):
        pkg = self.base / "pkg"
        rc, out = self.run_cli(["export-show", "--show", str(self.show_path),
                                "--out", str(pkg)])
        self.assertEqual(rc, 0)
        self.assertIn("Exported show test_show", out)
        rc, out = self.run_cli(["verify-show", "--out", str(pkg)])
        self.assertEqual(rc, 0)
        self.assertIn("Package OK: show test_show, 2 scene(s)", out)


if __name__ == "__main__":
    unittest.main()
