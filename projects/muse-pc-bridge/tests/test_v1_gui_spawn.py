"""V1.1 tests: first-class detached GUI launch (POST /v1/processes
with "gui": true).

The defect this fixes: a shell-wrapped spawn of a GUI application
reported the *wrapper shell* as the tracked process, and the wrapper
exits as soon as it hands off to the GUI exe — so the app showed up
dead instantly (hit during the Milky Way Godot launches, 2026-11-06).
GUI mode spawns the executable directly so the tracked pid IS the
application.

Hermetic pattern as the rest of the suite: a real agent on an
ephemeral loopback port with temp dirs. The "GUI app" here is the
test interpreter itself running a sleep — on this platform that
proves the direct-spawn mechanics (real pid tracked, survives the
request, kill works). The Windows GUI case (real .exe, breakaway
flags, window actually opening) is owner-PC verification, listed in
docs/TEST_PLAN.md.
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
sys.path.insert(0, str(PROJECT_DIR / "client"))

import bridge_agent  # noqa: E402
import bridge_client  # noqa: E402

TOKEN = "test-token-v11-gui"
ON_WINDOWS = sys.platform.startswith("win")
SHELL = "cmd" if ON_WINDOWS else "posix"
SLEEPER = ["-c", "import time; time.sleep(60)"]


class HttpClient:
    def __init__(self, base: str):
        self.base = base

    def request(self, method, path, payload=None, token=TOKEN):
        headers = {}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data,
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"raw": body}


class GuiSpawnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cfg = dict(bridge_agent.DEFAULT_CONFIG)
        cfg.update({
            "host": "127.0.0.1", "port": 0, "token": TOKEN,
            "allowed_file_root": str(root / "bridge-files"),
            "audit_log": str(root / "logs" / "audit.jsonl"),
            "state_dir": str(root / "state"),
            "default_timeout_s": 10, "max_timeout_s": 30,
        })
        cls.server = bridge_agent.create_server(cfg)
        cls.core = cls.server.core
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.http = HttpClient(f"http://127.0.0.1:{cls.port}")
        cls.root = root

    @classmethod
    def tearDownClass(cls):
        # Kill spawned processes BEFORE the temp dir goes away (their
        # log files live under state/ and are held open) — same
        # pattern as test_v1_jobs.
        _, listing = cls.http.request("GET", "/v1/processes")
        for item in listing.get("processes", []):
            if item.get("alive"):
                cls.http.request(
                    "POST", f"/v1/processes/{item['process_id']}/kill", {})
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def spawn_gui_sleeper(self):
        status, obj = self.http.request("POST", "/v1/processes", {
            "gui": True, "executable": sys.executable, "args": SLEEPER,
            "name": "gui-sleeper"})
        self.assertEqual(status, 201, obj)
        return obj

    def test_gui_spawn_tracks_a_live_real_pid(self):
        obj = self.spawn_gui_sleeper()
        self.assertTrue(obj["gui"])
        self.assertEqual(obj["shell"], "")
        self.assertEqual(obj["name"], "gui-sleeper")
        self.assertIn("time.sleep(60)", obj["command"])
        self.assertTrue(obj["alive"])
        pid = obj["pid"]
        self.assertGreater(pid, 0)
        if not ON_WINDOWS and Path(f"/proc/{pid}").exists():
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
            # The tracked pid runs the sleeper itself — not a wrapper
            # shell that would have exited already.
            self.assertIn(b"time.sleep(60)", cmdline)
        # Still alive after the request has fully returned.
        status, got = self.http.request(
            "GET", f"/v1/processes/{obj['process_id']}")
        self.assertEqual(status, 200)
        self.assertTrue(got["alive"])
        self.assertTrue(got["gui"])
        # And it can be killed through the registry (house pattern:
        # assert the kill landed, then poll — a just-signalled
        # process may not have exited at the instant of the reply).
        status, killed = self.http.request(
            "POST", f"/v1/processes/{obj['process_id']}/kill", {})
        self.assertEqual(status, 200)
        self.assertTrue(killed["killed"])
        deadline = time.time() + 10
        alive = True
        while time.time() < deadline:
            _, snap = self.http.request(
                "GET", f"/v1/processes/{obj['process_id']}")
            alive = snap["alive"]
            if not alive:
                break
            time.sleep(0.1)
        self.assertFalse(alive, "killed GUI process must stop reporting alive")

    def test_gui_spawn_via_client_library(self):
        client = bridge_client.BridgeClient(
            f"http://127.0.0.1:{self.port}", TOKEN)
        obj = client.process_spawn(gui=True, executable=sys.executable,
                                   args=SLEEPER)
        self.assertTrue(obj["gui"])
        self.assertTrue(obj["alive"])
        client.process_kill(obj["process_id"])

    def test_gui_spawn_requires_executable(self):
        status, obj = self.http.request("POST", "/v1/processes",
                                        {"gui": True})
        self.assertEqual(status, 400)
        self.assertIn("executable", obj["error"])

    def test_gui_spawn_rejects_missing_executable(self):
        status, obj = self.http.request("POST", "/v1/processes", {
            "gui": True,
            "executable": str(self.root / "no-such-app.exe")})
        self.assertEqual(status, 400)
        self.assertIn("does not exist", obj["error"])

    def test_gui_spawn_rejects_bad_args(self):
        for bad in ("-c pass", [1, 2], {"a": 1}):
            status, obj = self.http.request("POST", "/v1/processes", {
                "gui": True, "executable": sys.executable, "args": bad})
            self.assertEqual(status, 400, (bad, obj))
            self.assertIn("args", obj["error"])

    def test_gui_spawn_rejects_bad_cwd(self):
        status, obj = self.http.request("POST", "/v1/processes", {
            "gui": True, "executable": sys.executable, "args": SLEEPER,
            "cwd": str(self.root / "no-such-dir")})
        self.assertEqual(status, 400)

    def test_gui_flag_persists_in_registry_file(self):
        obj = self.spawn_gui_sleeper()
        state_file = self.root / "state" / "processes.json"
        records = json.loads(state_file.read_text(encoding="utf-8"))
        mine = [r for r in records if r["id"] == obj["process_id"]]
        self.assertEqual(len(mine), 1)
        self.assertTrue(mine[0]["gui"])
        restored = bridge_agent.DetachedProcess.from_record(
            self.core, mine[0])
        self.assertTrue(restored.gui)
        self.assertEqual(restored.pid, obj["pid"])
        self.http.request("POST",
                          f"/v1/processes/{obj['process_id']}/kill", {})

    def test_shell_spawn_still_works_and_reports_gui_false(self):
        cmd = "ping -n 3 127.0.0.1 >nul" if ON_WINDOWS else "sleep 2"
        status, obj = self.http.request("POST", "/v1/processes", {
            "command": cmd, "shell": SHELL})
        self.assertEqual(status, 201, obj)
        self.assertFalse(obj["gui"])
        self.assertEqual(obj["shell"], SHELL)
        self.assertTrue(obj["alive"])
        self.http.request("POST",
                          f"/v1/processes/{obj['process_id']}/kill", {})

    def test_gui_record_survives_agent_restart_shape(self):
        # A restored record (no Popen handle) must report liveness by
        # OS pid, exactly like shell-spawned records do today.
        obj = self.spawn_gui_sleeper()
        record = self.core.processes[obj["process_id"]]
        real_proc = record.proc
        record.proc = None  # simulate a restart: handle is gone
        try:
            self.assertTrue(record.alive())  # via pid_alive, not poll()
            status, killed = self.http.request(
                "POST", f"/v1/processes/{obj['process_id']}/kill", {})
            self.assertEqual(status, 200)
            self.assertTrue(killed["killed"])
            # In a real restart the orphan is reparented and reaped
            # by init; here the test process is the parent, so reap
            # through the saved handle to reach the same end state.
            real_proc.wait(timeout=10)
            self.assertFalse(record.alive())
        finally:
            record.proc = real_proc


if __name__ == "__main__":
    unittest.main()
