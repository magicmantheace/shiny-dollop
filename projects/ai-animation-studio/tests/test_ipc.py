"""Structured director-to-engine IPC contract (F2.4, studio/ipc.py).

The envelope and result shapes are the wire contract between the director
side (CLI) and the engine (Godot preview). These tests pin: round-trips,
refusal of unknown ipc_version / kind / malformed payloads with named
reasons, result-document validation, the demo command writing an
enveloped runtime scene, and IPC_VERSION parity with godot/main.gd.
The Godot-side behavior (envelope playback + scene_result.json) is
covered by recorded headless evidence in docs/IMPLEMENTATION_STATUS.md,
not by unit tests.
"""
import copy
import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from studio import cli
from studio.ipc import (
    IPC_VERSION,
    IpcError,
    make_result,
    read_ipc,
    read_result,
    unwrap_scene,
    validate_result,
    wrap_scene,
    write_ipc,
    write_result,
)
from studio.cli import load as load_example

ROOT = Path(__file__).resolve().parents[1]
SCENE = load_example("scene_demo.json")


def enveloped(**changes):
    env = wrap_scene(copy.deepcopy(SCENE), issued_at="2026-11-03T00:00:00Z")
    env.update(changes)
    return env


class WrapUnwrapTests(unittest.TestCase):
    def test_round_trip(self):
        env = wrap_scene(copy.deepcopy(SCENE), issued_at="2026-11-03T00:00:00Z")
        self.assertEqual(env["ipc_version"], IPC_VERSION)
        self.assertEqual(env["kind"], "scene")
        self.assertEqual(env["issued_at"], "2026-11-03T00:00:00Z")
        self.assertEqual(unwrap_scene(env), SCENE)

    def test_wrap_stamps_issued_at_by_default(self):
        env = wrap_scene(copy.deepcopy(SCENE))
        self.assertIsInstance(env["issued_at"], str)
        self.assertTrue(env["issued_at"].endswith("Z"))

    def test_wrap_validates_scene_first(self):
        bad = copy.deepcopy(SCENE)
        bad["events"] = []
        with self.assertRaises(ValueError):
            wrap_scene(bad)

    def test_unknown_ipc_version_refused(self):
        with self.assertRaises(IpcError) as ctx:
            unwrap_scene(enveloped(ipc_version="9.9.9"))
        self.assertIn("ipc_version", str(ctx.exception))
        self.assertIn("9.9.9", str(ctx.exception))

    def test_non_string_ipc_version_refused(self):
        with self.assertRaises(IpcError):
            unwrap_scene(enveloped(ipc_version=1))

    def test_unknown_kind_refused(self):
        with self.assertRaises(IpcError) as ctx:
            unwrap_scene(enveloped(kind="result"))
        self.assertIn("kind", str(ctx.exception))

    def test_missing_payload_refused(self):
        env = enveloped()
        del env["payload"]
        with self.assertRaises(IpcError) as ctx:
            unwrap_scene(env)
        self.assertIn("payload", str(ctx.exception))

    def test_non_object_payload_refused(self):
        with self.assertRaises(IpcError):
            unwrap_scene(enveloped(payload=["not", "a", "scene"]))

    def test_invalid_scene_payload_refused(self):
        bad = copy.deepcopy(SCENE)
        bad["events"].append(
            {"at_ms": 99999, "op": "explode", "actor_id": "traveler"})
        with self.assertRaises(IpcError) as ctx:
            unwrap_scene(enveloped(payload=bad))
        self.assertIn("payload failed scene validation", str(ctx.exception))

    def test_envelope_must_be_object(self):
        with self.assertRaises(IpcError):
            unwrap_scene(["ipc_version", IPC_VERSION])

    def test_unknown_envelope_key_refused(self):
        with self.assertRaises(IpcError) as ctx:
            unwrap_scene(enveloped(surprise=True))
        self.assertIn("unknown keys", str(ctx.exception))

    def test_bad_issued_at_refused(self):
        with self.assertRaises(IpcError):
            unwrap_scene(enveloped(issued_at=42))


class IpcFileTests(unittest.TestCase):
    def test_write_read_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "nested" / "scene_runtime.json"
            env = write_ipc(path, copy.deepcopy(SCENE),
                            issued_at="2026-11-03T00:00:00Z")
            self.assertEqual(env["kind"], "scene")
            self.assertEqual(read_ipc(path), SCENE)

    def test_read_ipc_refuses_bare_scene(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "scene_runtime.json"
            path.write_text(json.dumps(SCENE), encoding="utf-8")
            with self.assertRaises(IpcError):
                read_ipc(path)

    def test_read_ipc_refuses_malformed_json(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "scene_runtime.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(IpcError):
                read_ipc(path)

    def test_read_ipc_missing_file_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(IpcError):
                read_ipc(Path(temp) / "absent.json")


class ResultTests(unittest.TestCase):
    def test_make_and_validate(self):
        doc = make_result("tavern_meeting_demo", True, "scene accepted")
        self.assertEqual(doc["ipc_version"], IPC_VERSION)
        self.assertEqual(doc["kind"], "result")
        self.assertIs(doc["accepted"], True)
        self.assertIs(validate_result(doc), doc)

    def test_write_read_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "scene_result.json"
            write_result(path, "tavern_meeting_demo", False, "bad version")
            doc = read_result(path)
            self.assertEqual(doc["scene_id"], "tavern_meeting_demo")
            self.assertIs(doc["accepted"], False)
            self.assertEqual(doc["detail"], "bad version")

    def test_result_refusals(self):
        good = make_result("tavern_meeting_demo", True, "ok")
        cases = []
        for change in (
            {"ipc_version": "2.0.0"},
            {"kind": "scene"},
            {"scene_id": "Bad ID!"},
            {"scene_id": ""},
            {"accepted": "yes"},
            {"accepted": 1},
            {"detail": 42},
            {"extra": True},
        ):
            bad = dict(good)
            bad.update(change)
            cases.append(bad)
        missing = dict(good)
        del missing["detail"]
        cases.append(missing)
        for bad in cases:
            with self.subTest(bad=bad):
                with self.assertRaises(IpcError):
                    validate_result(bad)

    def test_read_result_refuses_garbage(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "scene_result.json"
            path.write_text(json.dumps({"kind": "result"}), encoding="utf-8")
            with self.assertRaises(IpcError):
                read_result(path)


class DemoCliTests(unittest.TestCase):
    def test_demo_writes_enveloped_runtime_scene(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "scene_runtime.json"
            db = Path(temp) / "absent.db"  # no DB -> base manifest copy
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = cli.main(["demo", "--db", str(db), "--out", str(out)])
            self.assertEqual(code, 0)
            self.assertIn("IPC envelope", stdout.getvalue())
            raw = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(raw["ipc_version"], IPC_VERSION)
            self.assertEqual(raw["kind"], "scene")
            scene = read_ipc(out)
            self.assertEqual(scene["scene_id"], SCENE["scene_id"])
            self.assertEqual(scene, SCENE)


class GodotParityTests(unittest.TestCase):
    def test_main_gd_ipc_version_matches(self):
        gd = (ROOT / "godot" / "main.gd").read_text(encoding="utf-8")
        match = re.search(r'const IPC_VERSION := "([^"]+)"', gd)
        self.assertIsNotNone(match, "main.gd must define IPC_VERSION")
        self.assertEqual(match.group(1), IPC_VERSION)
        self.assertIn("scene_result.json", gd)


if __name__ == "__main__":
    unittest.main()
