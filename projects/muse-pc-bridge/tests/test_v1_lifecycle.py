"""V1-S3 tests: self-update mechanics and the supervisor.

Update staging/apply/rollback are file operations — fully exercised
here in temp dirs. The supervisor is tested with fake agent scripts
(a tiny stdlib HTTP server standing in for bridge_agent.py) to prove
crash-restart and update health-check/rollback behavior. No Windows
service is installed by these tests; the service-form scripts
(start-bridge-service.cmd / bridge-service.ps1) are owner-run.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import bridge_update  # noqa: E402
import supervisor as supervisor_mod  # noqa: E402

GOOD_AGENT = '''
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
cfg_path = sys.argv[sys.argv.index("--config") + 1]
cfg = json.loads(open(cfg_path, encoding="utf-8").read())
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"{\\"ok\\": true}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass
HTTPServer(("127.0.0.1", int(cfg["port"])), H).serve_forever()
'''

BAD_AGENT = "import sys; sys.exit(3)\n"

CRASH_TWICE_AGENT = '''
import json, os, sys
counter_path = os.environ["FAKE_AGENT_COUNTER"]
count = 0
if os.path.exists(counter_path):
    count = int(open(counter_path).read().strip() or "0")
count += 1
open(counter_path, "w").write(str(count))
if count <= 2:
    sys.exit(1)
''' + GOOD_AGENT


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_bundle(directory: Path, version: str,
                files: dict[str, str]) -> tuple[Path, str]:
    bundle = directory / f"bundle-{version}.zip"
    manifest = {"version": version, "files": sorted(files)}
    with zipfile.ZipFile(bundle, "w") as zf:
        zf.writestr("bridge-release.json", json.dumps(manifest))
        for rel, content in files.items():
            zf.writestr(rel, content)
    return bundle, hashlib.sha256(bundle.read_bytes()).hexdigest()


class UpdateMechanicsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.install = root / "install"
        (self.install / "agent").mkdir(parents=True)
        self.agent_file = self.install / "agent" / "bridge_agent.py"
        self.agent_file.write_text("VERSION-1", encoding="utf-8")
        self.state = root / "state"
        self.state.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_stage_apply_rollback_cycle(self):
        bundle, sha = make_bundle(Path(self.tmp.name), "1.0.1",
                                  {"agent/bridge_agent.py": "VERSION-2"})
        pending = bridge_update.stage_update(
            str(bundle), sha, "1.0.1", self.install, self.state)
        self.assertEqual(pending["version"], "1.0.1")
        status = bridge_update.update_status(self.state)
        self.assertEqual(status["staged"]["version"], "1.0.1")

        record = bridge_update.apply_staged(self.state, self.install)
        self.assertEqual(self.agent_file.read_text(encoding="utf-8"),
                         "VERSION-2")
        self.assertIn("agent/bridge_agent.py", record["backed_up"])
        self.assertIsNone(bridge_update.update_status(self.state)["staged"])

        result = bridge_update.rollback(self.state, self.install,
                                        reason="test")
        self.assertEqual(result["rolled_back_version"], "1.0.1")
        self.assertEqual(self.agent_file.read_text(encoding="utf-8"),
                         "VERSION-1")

    def test_stage_rejects_wrong_sha(self):
        bundle, _ = make_bundle(Path(self.tmp.name), "1.0.1",
                                {"agent/bridge_agent.py": "V2"})
        with self.assertRaises(ValueError):
            bridge_update.stage_update(str(bundle), "0" * 64, "1.0.1",
                                       self.install, self.state)

    def test_stage_rejects_version_mismatch(self):
        bundle, sha = make_bundle(Path(self.tmp.name), "9.9.9",
                                  {"agent/bridge_agent.py": "V2"})
        with self.assertRaises(ValueError):
            bridge_update.stage_update(str(bundle), sha, "1.0.1",
                                       self.install, self.state)

    def test_stage_rejects_zip_slip(self):
        bundle = Path(self.tmp.name) / "evil.zip"
        manifest = {"version": "1.0.1", "files": ["../evil.py"]}
        with zipfile.ZipFile(bundle, "w") as zf:
            zf.writestr("bridge-release.json", json.dumps(manifest))
            zf.writestr("../evil.py", "pwned")
        sha = hashlib.sha256(bundle.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            bridge_update.stage_update(str(bundle), sha, "1.0.1",
                                       self.install, self.state)
        self.assertFalse((Path(self.tmp.name) / "evil.py").exists())

    def test_apply_without_pending_raises(self):
        with self.assertRaises(ValueError):
            bridge_update.apply_staged(self.state, self.install)

    def test_stage_rejects_absolute_version(self):
        # Codex PR #27: stage_update() rmtree()s staging/<version>
        # before the bundle is fetched or verified; an absolute
        # `version` made the join select the victim directory itself.
        bundle, sha = make_bundle(Path(self.tmp.name), "1.0.1",
                                  {"agent/bridge_agent.py": "V2"})
        victim = Path(self.tmp.name) / "victim-abs"
        victim.mkdir()
        (victim / "keep.txt").write_text("precious", encoding="utf-8")
        with self.assertRaises(ValueError):
            bridge_update.stage_update(str(bundle), sha, str(victim),
                                       self.install, self.state)
        self.assertEqual((victim / "keep.txt").read_text(encoding="utf-8"),
                         "precious")
        self.assertIsNone(bridge_update.update_status(self.state)["staged"])

    def test_stage_rejects_traversal_version(self):
        # Same finding, traversal form: "../victim" relative to the
        # staging root lands on state/victim.
        bundle, sha = make_bundle(Path(self.tmp.name), "1.0.1",
                                  {"agent/bridge_agent.py": "V2"})
        victim = self.state / "victim"
        victim.mkdir()
        (victim / "keep.txt").write_text("precious", encoding="utf-8")
        with self.assertRaises(ValueError):
            bridge_update.stage_update(str(bundle), sha, "../victim",
                                       self.install, self.state)
        self.assertEqual((victim / "keep.txt").read_text(encoding="utf-8"),
                         "precious")
        self.assertIsNone(bridge_update.update_status(self.state)["staged"])

    def test_stage_rejects_noncomponent_version(self):
        # A version must be exactly one safe path component. The
        # marker proves rejection happens BEFORE any rmtree: pre-fix,
        # "." resolved to the staging root itself and ".." to the
        # whole state dir, and both were deleted before the manifest
        # check got a chance to reject the request.
        bundle, sha = make_bundle(Path(self.tmp.name), "1.0.1",
                                  {"agent/bridge_agent.py": "V2"})
        staging_root = self.state / "staging"
        staging_root.mkdir()
        marker = staging_root / "marker.txt"
        marker.write_text("keep", encoding="utf-8")
        for bad in ("", " ", ".", "..", "a/b", "a\\b", "1.0.1/x"):
            with self.assertRaises(ValueError, msg=f"version={bad!r}"):
                bridge_update.stage_update(str(bundle), sha, bad,
                                           self.install, self.state)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
        self.assertIsNone(bridge_update.update_status(self.state)["staged"])


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.install = root / "install"
        (self.install / "agent").mkdir(parents=True)
        self.agent_file = self.install / "agent" / "bridge_agent.py"
        self.state = root / "state"
        self.state.mkdir()
        self.port = free_port()
        self.config = root / "config.json"
        self.config.write_text(json.dumps({
            "host": "127.0.0.1", "port": self.port, "token": "x",
            "state_dir": str(self.state)}), encoding="utf-8")
        self.sup: supervisor_mod.Supervisor | None = None
        self.thread: threading.Thread | None = None

    def tearDown(self):
        if self.sup is not None:
            self.sup.stop()
        if self.thread is not None:
            self.thread.join(timeout=15)
        self.tmp.cleanup()

    def start_supervisor(self, **kwargs):
        params = dict(restart_base_delay=0.2, restart_max_delay=1.0,
                      health_timeout_s=4.0, health_interval_s=0.2)
        params.update(kwargs)
        self.sup = supervisor_mod.Supervisor(
            self.install, self.config, self.state, **params)
        self.thread = threading.Thread(target=self.sup.run, daemon=True)
        self.thread.start()

    def wait_for(self, predicate, timeout=20.0, what="condition"):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return
            time.sleep(0.1)
        self.fail(f"timed out waiting for {what}")

    def read_state_json(self, name):
        path = self.state / name
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def test_crash_restart(self):
        counter = Path(self.tmp.name) / "counter.txt"
        os.environ["FAKE_AGENT_COUNTER"] = str(counter)
        try:
            self.agent_file.write_text(CRASH_TWICE_AGENT, encoding="utf-8")
            self.start_supervisor()
            self.wait_for(
                lambda: counter.exists()
                and counter.read_text().strip() == "3",
                what="third agent start after two crashes")
            status = self.read_state_json("supervisor-status.json")
            self.assertIsNotNone(status)
            self.assertEqual(status["state"], "running")
            self.assertGreaterEqual(status["restarts"], 2)
            self.assertIsNotNone(status["agent_pid"])
        finally:
            os.environ.pop("FAKE_AGENT_COUNTER", None)

    def test_unhealthy_update_rolls_back(self):
        self.agent_file.write_text(GOOD_AGENT, encoding="utf-8")
        bundle, sha = make_bundle(Path(self.tmp.name), "1.0.1",
                                  {"agent/bridge_agent.py": BAD_AGENT})
        bridge_update.stage_update(str(bundle), sha, "1.0.1",
                                   self.install, self.state)
        self.start_supervisor()
        self.wait_for(
            lambda: (self.read_state_json("update-result.json") or {})
            .get("rolled_back_version") == "1.0.1",
            what="automatic rollback after failed health check")
        self.assertEqual(self.agent_file.read_text(encoding="utf-8"),
                         GOOD_AGENT)

    def test_healthy_update_stays(self):
        self.agent_file.write_text(GOOD_AGENT, encoding="utf-8")
        v2 = GOOD_AGENT + "\n# v2 marker\n"
        bundle, sha = make_bundle(Path(self.tmp.name), "1.0.2",
                                  {"agent/bridge_agent.py": v2})
        bridge_update.stage_update(str(bundle), sha, "1.0.2",
                                   self.install, self.state)
        self.start_supervisor()
        self.wait_for(
            lambda: (self.read_state_json("update-result.json") or {})
            .get("outcome") == "applied_ok",
            what="healthy update confirmation")
        self.assertEqual(self.agent_file.read_text(encoding="utf-8"), v2)


def wait_for_audit(audit_path: Path, event: str, timeout: float = 15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if audit_path.exists():
            try:
                lines = audit_path.read_text(encoding="utf-8").splitlines()
            except OSError:
                lines = []
            for line in lines:
                try:
                    if json.loads(line).get("event") == event:
                        return True
                except json.JSONDecodeError:
                    pass
        time.sleep(0.1)
    return False


@unittest.skipIf(os.name == "nt",
                 "SIGTERM semantics are POSIX; the Windows graceful "
                 "path (CTRL_BREAK_EVENT) is owner-PC verification")
class GracefulShutdownTests(unittest.TestCase):
    """Codex PR #27: a normal stop must let the agent run its audited
    shutdown (AGENTS.md: server start/stop are audited). Previously
    Supervisor._stop_child() terminated the agent and the audit log
    was left holding only server_start."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.audit = root / "logs" / "audit.jsonl"
        self.config = root / "config.json"
        self.config.write_text(json.dumps({
            "host": "127.0.0.1", "port": free_port(),
            "token": "test-token-graceful",
            "allowed_file_root": str(root / "bridge-files"),
            "audit_log": str(self.audit),
            "state_dir": str(root / "state"),
        }), encoding="utf-8")
        self.state = root / "state"

    def tearDown(self):
        self.tmp.cleanup()

    def test_agent_sigterm_writes_server_stop(self):
        agent = PROJECT_DIR / "agent" / "bridge_agent.py"
        proc = subprocess.Popen(
            [sys.executable, str(agent), "--config", str(self.config)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            self.assertTrue(wait_for_audit(self.audit, "server_start"),
                            "agent did not start / audit server_start")
            proc.terminate()      # exactly what _stop_child() sends
            proc.wait(timeout=15)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            if proc.stdout is not None:
                proc.stdout.close()
        self.assertTrue(wait_for_audit(self.audit, "server_stop"),
                        "no audited server_stop after SIGTERM")

    def test_supervisor_stop_child_writes_server_stop(self):
        sup = supervisor_mod.Supervisor(PROJECT_DIR, self.config,
                                        self.state)
        child = sup._start_child()
        try:
            self.assertTrue(wait_for_audit(self.audit, "server_start"),
                            "agent did not start / audit server_start")
            sup._stop_child(timeout=15)
            self.assertIsNotNone(child.poll())
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
        self.assertTrue(wait_for_audit(self.audit, "server_stop"),
                        "supervisor stop left no audited server_stop")


if __name__ == "__main__":
    unittest.main()
