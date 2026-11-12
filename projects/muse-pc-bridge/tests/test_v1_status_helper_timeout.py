"""V1.1 tests: /v1/status must stay inside its readers' deadlines
when the session helper is alive but hung (Codex PR #47 finding).

The avatar's status readers time out at 1.5 s and the supervisor's
update health check at 3 s (its failure can roll back a healthy
update). _status_obj() used to merge helper-owned processes through
the listing's 5 s fetch synchronously, so a helper that accepted
connections but never answered made a healthy core look dead to
both readers for a full 5 s. These tests stand up exactly that
helper — a TCP listener that accepts and stays silent while a
heartbeat thread keeps its registration fresh, which is the real
failure shape (the helper's heartbeat is a separate thread from its
request handlers) — and assert /v1/status answers well inside the
3 s deadline, twice in a row, with local counts intact.

Windows behaviour is identical code (pure socket timeouts); the
owner-PC suite run is recorded in docs/TEST_PLAN.md.
"""

from __future__ import annotations

import json
import socket
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

TOKEN = "test-token-status-timeout"
SLEEPER = "import time; time.sleep(60)"
# The supervisor health check gives up at 3 s; status must answer
# well inside that even in the worst (cache-cold) case.
STATUS_BOUND_S = 2.0


def call(method, port, path, payload=None, token=TOKEN, timeout=20):
    data = json.dumps(payload).encode("utf-8") \
        if payload is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}


class HungHelper:
    """Accepts TCP connections and never answers, while keeping a
    session-helper registration fresh — a live-but-hung helper."""

    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        self._conns: list[socket.socket] = []
        self._stop = threading.Event()
        self._threads = [
            threading.Thread(target=self._accept, daemon=True),
            threading.Thread(target=self._heartbeat, daemon=True),
        ]
        self._write_registration()
        for thread in self._threads:
            thread.start()

    def _write_registration(self):
        import os
        (self.state_dir / bridge_agent.HELPER_REGISTRY_NAME).write_text(
            json.dumps({
                "port": self.port, "pid": os.getpid(),
                "session_id": 1, "started_at": time.time(),
                "updated_at": time.time(),
            }), encoding="utf-8")

    def _heartbeat(self):
        # The real helper heartbeats from its own thread, so a hung
        # request handler does NOT make the registration stale.
        while not self._stop.wait(1.0):
            self._write_registration()

    def _accept(self):
        self.sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _addr = self.sock.accept()
                self._conns.append(conn)   # held open, never served
            except socket.timeout:
                continue
            except OSError:
                break

    def close(self):
        self._stop.set()
        for conn in self._conns:
            try:
                conn.close()
            except OSError:
                pass
        try:
            self.sock.close()
        except OSError:
            pass


class StatusDeadlineFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.state_dir = root / "state"
        self.state_dir.mkdir()
        self.audit_path = root / "logs" / "audit.jsonl"
        cfg = dict(bridge_agent.DEFAULT_CONFIG)
        cfg.update({
            "host": "127.0.0.1", "port": 0, "token": TOKEN,
            "allowed_file_root": str(root / "bridge-files"),
            "audit_log": str(self.audit_path),
            "state_dir": str(self.state_dir),
        })
        self.server = bridge_agent.create_server(cfg)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.spawned = []
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for proc_id in self.spawned:
            try:
                call("POST", self.port, f"/v1/processes/{proc_id}/kill")
            except Exception:
                pass
        stopper = threading.Thread(target=self.server.shutdown,
                                   daemon=True)
        stopper.start()
        stopper.join(timeout=5)
        self.server.server_close()

    def spawn_local_sleeper(self):
        status, obj = call("POST", self.port, "/v1/processes", {
            "gui": True, "executable": sys.executable,
            "args": ["-c", SLEEPER]})
        self.assertEqual(status, 201, obj)
        self.spawned.append(obj["process_id"])
        return obj

    def timed_status(self):
        started = time.monotonic()
        status, obj = call("GET", self.port, "/v1/status")
        return time.monotonic() - started, status, obj


class HungHelperStatusTests(StatusDeadlineFixture):
    def test_status_answers_inside_deadlines_with_hung_helper(self):
        local = self.spawn_local_sleeper()   # served locally (no helper)
        hung = HungHelper(self.state_dir)
        self.addCleanup(hung.close)

        elapsed, status, obj = self.timed_status()
        self.assertEqual(status, 200, obj)
        self.assertLess(
            elapsed, STATUS_BOUND_S,
            f"/v1/status took {elapsed:.2f}s with a hung helper; "
            f"the supervisor health check gives up at 3 s")
        # Degradation is local-only: the local registry still counts
        # even though the helper merge cannot answer.
        self.assertGreaterEqual(obj["processes_tracked"], 1)
        self.assertEqual(obj["processes_alive"], 1)
        self.assertIn(local["process_id"], self.spawned)

        # A second probe right behind it must also stay inside the
        # deadline (no repeated 5 s stalls for the avatar's polls).
        elapsed, status, obj = self.timed_status()
        self.assertEqual(status, 200, obj)
        self.assertLess(
            elapsed, STATUS_BOUND_S,
            f"second /v1/status took {elapsed:.2f}s with a hung "
            f"helper")

    def test_processes_listing_still_answers_with_hung_helper(self):
        # The listing may keep its longer fetch budget, but it must
        # still return the local truth rather than fail.
        self.spawn_local_sleeper()
        hung = HungHelper(self.state_dir)
        self.addCleanup(hung.close)
        status, obj = call("GET", self.port, "/v1/processes",
                           timeout=30)
        self.assertEqual(status, 200, obj)
        self.assertEqual(len(obj["processes"]), 1)
        self.assertTrue(obj["processes"][0]["alive"])


if __name__ == "__main__":
    unittest.main()
