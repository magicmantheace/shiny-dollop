"""End-to-end tests for the muse-pc-bridge agent.

Boots the real HTTP server on an ephemeral loopback port with a temp
config, temp file root, and temp audit log, then exercises it over real
HTTP with urllib. Hermetic: nothing touches the real config, the repo,
or the network beyond 127.0.0.1.

These tests prove protocol, auth, exec, file-safety, and audit behavior
on the machine running them. They do NOT prove Windows execution or a
Tailscale link — see docs/TEST_PLAN.md.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import bridge_agent  # noqa: E402

TOKEN = "test-token-for-suite-only"
ON_WINDOWS = sys.platform.startswith("win")
SHELL = "cmd" if ON_WINDOWS else "posix"


def cmd_echo() -> str:
    return "echo bridge-ok"


def cmd_exit(code: int) -> str:
    return f"exit /b {code}" if ON_WINDOWS else f"exit {code}"


def cmd_sleep() -> str:
    return "ping -n 3 127.0.0.1 >nul" if ON_WINDOWS else "sleep 2"


class BridgeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.file_root = root / "bridge-files"
        cls.audit_path = root / "logs" / "audit.jsonl"
        cfg = dict(bridge_agent.DEFAULT_CONFIG)
        cfg.update({
            "host": "127.0.0.1",
            "port": 0,
            "token": TOKEN,
            "allowed_file_root": str(cls.file_root),
            "audit_log": str(cls.audit_path),
            "default_timeout_s": 10,
            "max_timeout_s": 30,
        })
        cls.server = bridge_agent.create_server(cfg)
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.core.log_stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    # -- HTTP helpers ---------------------------------------------------------
    def request(self, method, path, payload=None, token=TOKEN, raw_headers=None):
        headers = {}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        if raw_headers:
            headers.update(raw_headers)
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data,
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"raw": body}

    # -- auth -------------------------------------------------------------------
    def test_status_without_token_is_401(self):
        status, _ = self.request("GET", "/v1/status", token=None)
        self.assertEqual(status, 401)

    def test_status_with_wrong_token_is_401(self):
        status, _ = self.request("GET", "/v1/status", token="wrong-token")
        self.assertEqual(status, 401)

    # -- status -------------------------------------------------------------------
    def test_status_with_token(self):
        status, obj = self.request("GET", "/v1/status")
        self.assertEqual(status, 200)
        self.assertEqual(obj["agent"], "muse-pc-bridge")
        self.assertEqual(obj["version"], bridge_agent.VERSION)
        for field in ("hostname", "platform", "python", "uptime_s",
                      "shell_default", "file_root"):
            self.assertIn(field, obj)

    # -- exec -------------------------------------------------------------------
    def test_exec_echo(self):
        # v1: wait_s asks the agent to block until the job finishes and
        # return the result inline (the v0 one-call shape, plus job_id).
        status, obj = self.request("POST", "/v1/exec",
                                   {"command": cmd_echo(), "shell": SHELL,
                                    "wait_s": 10})
        self.assertEqual(status, 200)
        self.assertEqual(obj["exit_code"], 0)
        self.assertIn("bridge-ok", obj["stdout"])
        self.assertFalse(obj["timed_out"])
        self.assertFalse(obj["truncated"])
        self.assertIn("job_id", obj)

    def test_exec_nonzero_exit(self):
        status, obj = self.request("POST", "/v1/exec",
                                   {"command": cmd_exit(3), "shell": SHELL,
                                    "wait_s": 10})
        self.assertEqual(status, 200)
        self.assertEqual(obj["exit_code"], 3)

    def test_exec_timeout(self):
        status, obj = self.request("POST", "/v1/exec",
                                   {"command": cmd_sleep(), "shell": SHELL,
                                    "timeout_s": 0.3, "wait_s": 10})
        self.assertEqual(status, 200)
        self.assertTrue(obj["timed_out"])
        self.assertIsNone(obj["exit_code"])

    def test_exec_missing_command_is_400(self):
        status, _ = self.request("POST", "/v1/exec", {"shell": SHELL})
        self.assertEqual(status, 400)

    # -- files -------------------------------------------------------------------
    def test_file_put_get_roundtrip(self):
        data = b"hello bridge\n" * 100
        b64 = base64.b64encode(data).decode("ascii")
        status, obj = self.request("POST", "/v1/file/put",
                                   {"path": "sub/dir/note.txt", "content_b64": b64})
        self.assertEqual(status, 200)
        self.assertEqual(obj["size"], len(data))
        self.assertEqual(obj["sha256"], hashlib.sha256(data).hexdigest())

        qs = urllib.parse.urlencode({"path": "sub/dir/note.txt"})
        status, obj = self.request("GET", f"/v1/file/get?{qs}")
        self.assertEqual(status, 200)
        self.assertEqual(base64.b64decode(obj["content_b64"]), data)
        self.assertEqual(obj["sha256"], hashlib.sha256(data).hexdigest())

        qs = urllib.parse.urlencode({"path": "sub/dir"})
        status, obj = self.request("GET", f"/v1/file/list?{qs}")
        self.assertEqual(status, 200)
        names = [e["name"] for e in obj["entries"]]
        self.assertIn("note.txt", names)

    def test_path_escape_is_rejected(self):
        outside = Path(self.tmp.name) / "evil.txt"
        b64 = base64.b64encode(b"evil").decode("ascii")
        status, _ = self.request("POST", "/v1/file/put",
                                 {"path": "../evil.txt", "content_b64": b64})
        self.assertIn(status, (400, 403, 404))
        self.assertFalse(outside.exists(),
                         "escape attempt must not create a file outside the root")

        qs = urllib.parse.urlencode({"path": "../.."})
        status, _ = self.request("GET", f"/v1/file/get?{qs}")
        self.assertIn(status, (400, 403, 404))

        qs = urllib.parse.urlencode({"path": "/etc/passwd"})
        status, _ = self.request("GET", f"/v1/file/get?{qs}")
        self.assertIn(status, (400, 403, 404))

    # -- audit -------------------------------------------------------------------
    def test_audit_log_records_and_never_leaks_token(self):
        # Generate the activity this test asserts on (audit writes are
        # synchronous, so the entries are on disk immediately).
        self.request("GET", "/v1/status", token="deliberately-wrong")
        self.request("POST", "/v1/exec", {"command": cmd_echo(), "shell": SHELL})
        self.assertTrue(self.audit_path.exists(), "audit log file must exist")
        raw = self.audit_path.read_text(encoding="utf-8")
        self.assertNotIn(TOKEN, raw, "audit log must never contain the token")
        entries = [json.loads(line) for line in raw.splitlines() if line.strip()]
        events = [e["event"] for e in entries]
        self.assertIn("server_start", events)
        self.assertIn("auth_failed", events)
        exec_entries = [e for e in entries
                        if (e.get("path") or "").startswith("/v1/exec")]
        self.assertTrue(exec_entries, "expected at least one audited exec request")
        for e in entries:
            self.assertIn("ts", e)
            self.assertIn("event", e)


if __name__ == "__main__":
    unittest.main()
