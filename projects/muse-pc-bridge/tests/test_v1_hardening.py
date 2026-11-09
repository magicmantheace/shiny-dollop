"""V1-S5 tests: audit rotation, audit tail, auth-failure rate
limiting, and the update staging API (§5 hardening)."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import bridge_agent  # noqa: E402

TOKEN = "test-token-v1-hardening"


class Http:
    def __init__(self, base: str):
        self.base = base

    def request(self, method, path, token=TOKEN, payload=None):
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
                body = resp.read()
                return resp.status, (json.loads(body.decode("utf-8"))
                                     if body else {})
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"raw": body}


def start_server(tmp_root: Path, **overrides):
    cfg = dict(bridge_agent.DEFAULT_CONFIG)
    cfg.update({
        "host": "127.0.0.1", "port": 0, "token": TOKEN,
        "allowed_file_root": str(tmp_root / "bridge-files"),
        "audit_log": str(tmp_root / "logs" / "audit.jsonl"),
        "state_dir": str(tmp_root / "state"),
    })
    cfg.update(overrides)
    server = bridge_agent.create_server(cfg)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, Http(f"http://127.0.0.1:{server.server_address[1]}")


class AuditRotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.server, cls.thread, cls.http = start_server(
            cls.root, audit_max_bytes=800, audit_keep=3)

    @classmethod
    def tearDownClass(cls):
        cls.server.core.log_stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def test_rotation_bounds_the_log(self):
        for _ in range(40):
            status, _ = self.http.request("GET", "/v1/status")
            self.assertEqual(status, 200)
        audit = self.root / "logs" / "audit.jsonl"
        self.assertTrue(audit.exists())
        self.assertTrue((self.root / "logs" / "audit.jsonl.1").exists(),
                        "rotation never produced a .1 file")
        self.assertFalse((self.root / "logs" / "audit.jsonl.4").exists(),
                         "rotation kept more files than audit_keep=3")
        # Current file stays near the cap (one in-flight line of slack).
        self.assertLess(audit.stat().st_size, 800 + 600)

    def test_audit_tail_endpoint(self):
        for _ in range(6):   # ensure enough audited traffic exists
            self.http.request("GET", "/v1/status")
        # The tail reads the CURRENT audit file only; with this class's
        # 800-byte rotation cap that file holds just a few entries, so
        # ask for 2 (always satisfiable) rather than a fixed depth.
        status, obj = self.http.request("GET", "/v1/audit/tail?n=2")
        self.assertEqual(status, 200)
        self.assertEqual(obj["count"], 2)
        self.assertEqual(len(obj["entries"]), 2)
        for entry in obj["entries"]:
            self.assertIn("ts", entry)
            self.assertIn("event", entry)
            self.assertNotIn(TOKEN, json.dumps(entry))

    def test_audit_tail_clamps_n(self):
        status, obj = self.http.request("GET", "/v1/audit/tail?n=99999")
        self.assertEqual(status, 200)
        self.assertLessEqual(obj["count"], 1000)


class RateLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.server, cls.thread, cls.http = start_server(
            cls.root, auth_fail_limit=3, auth_fail_window_s=60,
            auth_block_s=30)

    @classmethod
    def tearDownClass(cls):
        cls.server.core.log_stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def test_auth_failure_rate_limiting_flow(self):
        # One deterministic flow (the limiter's state is per-server, so
        # splitting this across test methods would be order-dependent):
        # failures start as 401, the limiter trips to 429 with a
        # retry_after_s, the real token still works, and the blocked
        # attempts are still written to the audit log.
        responses = []
        for _ in range(6):
            responses.append(self.http.request("GET", "/v1/status",
                                               token="wrong-token"))
        statuses = [s for s, _ in responses]
        self.assertEqual(statuses[0], 401)
        self.assertIn(429, statuses)
        bodies_429 = [obj for s, obj in responses if s == 429]
        self.assertIsNotNone(bodies_429[0].get("retry_after_s"))
        # The limiter targets guessing: the real token still works.
        status, _ = self.http.request("GET", "/v1/status")
        self.assertEqual(status, 200)
        # Blocked attempts remain audited, flagged rate_limited.
        audit = self.root / "logs" / "audit.jsonl"
        text = audit.read_text(encoding="utf-8")
        lines = [json.loads(line) for line in text.splitlines() if line]
        flagged = [e for e in lines if e.get("rate_limited")]
        self.assertTrue(flagged,
                        "no rate_limited auth_failed entries in audit log")
        for entry in flagged:
            self.assertEqual(entry["event"], "auth_failed")
            self.assertNotIn(TOKEN, json.dumps(entry))


class UpdateApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.server, cls.thread, cls.http = start_server(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.server.core.log_stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def test_update_status_empty_then_stage(self):
        status, obj = self.http.request("GET", "/v1/update/status")
        self.assertEqual(status, 200)
        self.assertIsNone(obj["staged"])
        bundle = self.root / "rel.zip"
        manifest = {"version": "1.0.1", "files": ["agent/bridge_agent.py"]}
        with zipfile.ZipFile(bundle, "w") as zf:
            zf.writestr("bridge-release.json", json.dumps(manifest))
            zf.writestr("agent/bridge_agent.py", "# v1.0.1\n")
        sha = hashlib.sha256(bundle.read_bytes()).hexdigest()
        status, obj = self.http.request("POST", "/v1/update/stage", payload={
            "source": str(bundle), "sha256": sha, "version": "1.0.1"})
        self.assertEqual(status, 201)
        self.assertEqual(obj["version"], "1.0.1")
        status, obj = self.http.request("GET", "/v1/update/status")
        self.assertEqual(obj["staged"]["version"], "1.0.1")
        # Staging must NOT touch the running agent's files.
        self.assertEqual(obj["current_version"], bridge_agent.VERSION)


if __name__ == "__main__":
    unittest.main()
