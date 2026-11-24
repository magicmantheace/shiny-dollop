"""Bridge additions tests (durable job runner release):
GET /v1/presence, POST /v1/window/raise, session-aware spawn
with proof of life, and the Project Mode routes — end-to-end
over HTTP against the real agent on loopback with a dummy
token and temp dirs.

Platform honesty: this suite runs on POSIX. Presence answers
with null idle/foreground (Windows-only probes) rather than
fabricating; window raise answers 501; session spawns are
served locally (the POSIX session id never blocks). The
Windows behaviour of all four is verified on the owner's PC
at deploy time — see docs/JOB_RUNNER.md.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import bridge_agent  # noqa: E402

TOKEN = "dummy-token-for-v13-additions-tests"
ON_WINDOWS = sys.platform.startswith("win")


class HttpClient:
    def __init__(self, base: str):
        self.base = base

    def request(self, method: str, path: str,
                payload: dict | None = None):
        data = None
        headers = {"Authorization": f"Bearer {TOKEN}"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data,
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.loads(
                    resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"raw": body}


def make_cfg(root: Path) -> dict:
    cfg = dict(bridge_agent.DEFAULT_CONFIG)
    cfg.update({
        "host": "127.0.0.1", "port": 0, "token": TOKEN,
        "allowed_file_root": str(root / "bridge-files"),
        "audit_log": str(root / "logs" / "audit.jsonl"),
        "state_dir": str(root / "state"),
        "default_timeout_s": 10, "max_timeout_s": 30,
    })
    return cfg


class BridgeAdditionsHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.server = bridge_agent.create_server(make_cfg(cls.root))
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.http = HttpClient(f"http://127.0.0.1:{cls.port}")

    @classmethod
    def tearDownClass(cls):
        _, listing = cls.http.request("GET", "/v1/processes")
        for item in listing.get("processes", []):
            if item.get("alive"):
                cls.http.request(
                    "POST",
                    f"/v1/processes/{item['process_id']}/kill", {})
        deadline = time.time() + 10
        while time.time() < deadline:
            _, listing = cls.http.request("GET", "/v1/processes")
            if not any(i.get("alive")
                       for i in listing.get("processes", [])):
                break
            time.sleep(0.2)
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    # -- presence ----------------------------------------------------

    def test_presence_shape(self):
        status, obj = self.http.request("GET", "/v1/presence")
        self.assertEqual(status, 200, obj)
        for key in ("observed_at", "input_idle_s", "foreground",
                    "gaming", "games", "gpu", "processes_seen",
                    "notes"):
            self.assertIn(key, obj)
        self.assertIsInstance(obj["gaming"], bool)
        self.assertIsInstance(obj["games"], list)
        if not ON_WINDOWS:
            # Honest nulls off Windows — never fabricated.
            self.assertIsNone(obj["input_idle_s"])
            self.assertIsNone(obj["foreground"])

    # -- window raise --------------------------------------------------

    @unittest.skipIf(ON_WINDOWS, "501 refusal is the off-Windows path")
    def test_window_raise_unavailable_off_windows(self):
        status, obj = self.http.request(
            "POST", "/v1/window/raise", {"title": "anything"})
        self.assertEqual(status, 501, obj)
        self.assertTrue(obj.get("platform_limited"))

    def test_window_raise_validation(self):
        status, _ = self.http.request("POST", "/v1/window/raise", {})
        self.assertEqual(status, 400)
        status, _ = self.http.request(
            "POST", "/v1/window/raise", {"pid": 12, "title": "x"})
        self.assertEqual(status, 400)
        status, _ = self.http.request(
            "POST", "/v1/window/raise", {"pid": -3})
        self.assertEqual(status, 400)

    # -- session spawn + proof of life ---------------------------------

    SLEEPER = ({"shell": "cmd", "command": "ping -n 30 127.0.0.1 > NUL"}
               if ON_WINDOWS else
               {"shell": "posix", "command": "sleep 30"})
    INSTANT = ({"shell": "cmd", "command": "exit 0"}
               if ON_WINDOWS else
               {"shell": "posix", "command": "true"})

    def test_spawn_proof_alive(self):
        status, obj = self.http.request("POST", "/v1/processes", {
            **self.SLEEPER, "proof_delay_s": 0.5})
        self.assertEqual(status, 201, obj)
        self.assertIn("proof", obj)
        self.assertTrue(obj["proof"]["alive"])
        self.assertTrue(obj["proof"]["ok"])
        self.assertIsNone(obj["proof"]["exit_code"])
        self.http.request(
            "POST", f"/v1/processes/{obj['process_id']}/kill", {})

    def test_spawn_proof_reports_instant_exit_honestly(self):
        status, obj = self.http.request("POST", "/v1/processes", {
            **self.INSTANT, "proof_delay_s": 1.0})
        self.assertEqual(status, 201, obj)
        self.assertFalse(obj["proof"]["alive"])
        self.assertFalse(obj["proof"]["ok"])
        self.assertEqual(obj["proof"]["exit_code"], 0)

    def test_spawn_session_mode(self):
        status, obj = self.http.request("POST", "/v1/processes", {
            "session": "interactive", **self.SLEEPER,
            "proof_delay_s": 0.5})
        self.assertEqual(status, 201, obj)
        self.assertEqual(obj.get("session"), "interactive")
        self.assertTrue(obj["proof"]["alive"])
        self.http.request(
            "POST", f"/v1/processes/{obj['process_id']}/kill", {})

    def test_spawn_bad_session_value_is_400(self):
        status, _ = self.http.request("POST", "/v1/processes", {
            "session": "bogus", **self.INSTANT})
        self.assertEqual(status, 400)

    def test_spawn_proof_delay_range_validated(self):
        status, _ = self.http.request("POST", "/v1/processes", {
            **self.INSTANT, "proof_delay_s": 99})
        self.assertEqual(status, 400)

    # -- project mode ----------------------------------------------------

    def test_project_mode_routes(self):
        status, obj = self.http.request("GET", "/v1/project-mode")
        self.assertEqual(status, 200, obj)
        self.assertFalse(obj["engaged"])
        status, obj = self.http.request(
            "POST", "/v1/project-mode/engage", {})
        self.assertEqual(status, 200, obj)
        self.assertTrue(obj["engaged"])
        step_status = {s["step"]: s["status"]
                       for s in obj["engage_steps"]}
        if not ON_WINDOWS:
            # Every machine step honestly not-applied/skipped.
            self.assertEqual(step_status["power_plan"], "skipped")
            self.assertEqual(step_status["lively"], "not_applicable")
            self.assertEqual(step_status["search_indexing"],
                             "skipped")
        status, obj = self.http.request(
            "POST", "/v1/project-mode/disengage", {})
        self.assertEqual(status, 200, obj)
        self.assertFalse(obj["engaged"])
        status, obj = self.http.request("GET", "/v1/project-mode")
        self.assertFalse(obj["engaged"])


if __name__ == "__main__":
    unittest.main()
