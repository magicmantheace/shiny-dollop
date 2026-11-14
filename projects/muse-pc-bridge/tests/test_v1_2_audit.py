"""V1.2 tests: audit log read access (spec §2).

GET /v1/audit returns entries at/after a unix timestamp, oldest
first, paged via next_since, reading ONLY the agent's own configured
audit file. The regression at the heart of the item: the token is
never written to the log, so seeding the token string into a command
must leave it in NEITHER the audit file NOR the endpoint output —
command summaries are audit content, so the agent scrubs the exact
token value from audit lines at write time (see BridgeCore.audit).

All tests boot the real agent on loopback with a dummy token.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))
sys.path.insert(0, str(PROJECT_DIR / "client"))

import bridge_agent  # noqa: E402
import bridge_client  # noqa: E402

TOKEN = "dummy-token-for-v12-audit-tests"
ON_WINDOWS = sys.platform.startswith("win")
SHELL = "cmd" if ON_WINDOWS else "posix"


def ts_of(epoch_ms: int) -> str:
    """ISO audit timestamp for a whole-millisecond epoch value."""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch_ms / 1000, timezone.utc).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")


class AuditReadTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.file_root = root / "bridge-files"
        cls.audit_path = root / "logs" / "audit.jsonl"
        cfg = dict(bridge_agent.DEFAULT_CONFIG)
        cfg.update({
            "host": "127.0.0.1", "port": 0, "token": TOKEN,
            "allowed_file_root": str(cls.file_root),
            "audit_log": str(cls.audit_path),
            "state_dir": str(root / "state"),
            "default_timeout_s": 10, "max_timeout_s": 30,
        })
        cls.server = bridge_agent.create_server(cfg)
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.client = bridge_client.BridgeClient(cls.base, TOKEN)

    @classmethod
    def tearDownClass(cls):
        runner = getattr(cls.server.core, "queue_runner", None)
        if runner is not None:
            runner.stop()
        cls.server.core.log_stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    # -- HTTP helpers ------------------------------------------------------
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
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, json.loads(raw), raw
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(raw), raw
            except json.JSONDecodeError:
                return exc.code, {"raw": raw}, raw

    def seed_entries(self, base_ms: int, count: int, step_ms: int = 1000):
        """Append crafted entries with known timestamps directly to
        the log file (the endpoint reads the file, so this is the
        same surface production entries arrive through)."""
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.audit_path, "a", encoding="utf-8") as fh:
            for i in range(count):
                fh.write(json.dumps({
                    "ts": ts_of(base_ms + i * step_ms),
                    "event": "seeded", "seq": i,
                    "summary": f"seeded entry {i}",
                }) + "\n")

    def seeded(self, obj):
        return [e for e in obj["entries"] if e.get("event") == "seeded"]

    # -- auth ----------------------------------------------------------------
    def test_audit_requires_auth(self):
        status, _, _ = self.request("GET", "/v1/audit", token=None)
        self.assertEqual(status, 401)
        status, _, _ = self.request("GET", "/v1/audit", token="wrong")
        self.assertEqual(status, 401)

    # -- basic read ----------------------------------------------------------
    def test_reads_own_log_oldest_first(self):
        status, obj, _ = self.request("GET", "/v1/audit?limit=1000")
        self.assertEqual(status, 200)
        self.assertIn("entries", obj)
        self.assertIn("next_since", obj)
        events = [e.get("event") for e in obj["entries"]]
        self.assertIn("server_start", events)
        epochs = [bridge_agent._audit_entry_epoch(e) for e in obj["entries"]]
        epochs = [t for t in epochs if t is not None]
        self.assertEqual(epochs, sorted(epochs))

    def test_since_filter_is_at_or_after(self):
        base_ms = 1_700_000_000_000
        self.seed_entries(base_ms, 4)
        since = (base_ms + 2000) / 1000  # exactly entry 2's timestamp
        status, obj, _ = self.request("GET", f"/v1/audit?since={since}")
        self.assertEqual(status, 200)
        seqs = [e["seq"] for e in self.seeded(obj)]
        self.assertEqual(seqs, [2, 3])

    def test_paging_with_next_since_covers_all_without_duplicates(self):
        # Dedicated core: the file holds exactly the seeded entries,
        # so paging is deterministic (the shared server's log mixes
        # in real request entries with unrelated timestamps).
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        cfg = dict(bridge_agent.DEFAULT_CONFIG)
        cfg.update({
            "host": "127.0.0.1", "port": 0, "token": TOKEN,
            "allowed_file_root": str(root / "bridge-files"),
            "audit_log": str(root / "logs" / "audit.jsonl"),
            "state_dir": str(root / "state"),
        })
        core = bridge_agent.BridgeCore(cfg)
        core.audit_path.parent.mkdir(parents=True, exist_ok=True)
        base_ms = 1_600_000_000_000
        with open(core.audit_path, "a", encoding="utf-8") as fh:
            for i in range(5):
                fh.write(json.dumps({
                    "ts": ts_of(base_ms + i * 1000),
                    "event": "seeded", "seq": i}) + "\n")
        seen = []
        since = None
        for _ in range(10):
            page = core.audit_read(since, 2)
            seen += [e["seq"] for e in page["entries"]]
            since = page["next_since"]
            if since is None:
                break
        self.assertIsNone(since)
        self.assertEqual(seen, [0, 1, 2, 3, 4])
        # A since past the last entry returns nothing, no cursor.
        page = core.audit_read((base_ms + 4000) / 1000 + 1, 2)
        self.assertEqual(page["entries"], [])
        self.assertIsNone(page["next_since"])
        # At-or-after: a since equal to an entry's ts includes it.
        page = core.audit_read((base_ms + 2000) / 1000, 10)
        self.assertEqual([e["seq"] for e in page["entries"]], [2, 3, 4])

    def test_limit_defaults_and_cap(self):
        status, obj, _ = self.request("GET", "/v1/audit?limit=99999")
        self.assertEqual(status, 200)
        self.assertLessEqual(obj["count"], 1000)

    def test_bad_params_are_400(self):
        status, _, _ = self.request("GET", "/v1/audit?since=banana")
        self.assertEqual(status, 400)
        status, _, _ = self.request("GET", "/v1/audit?limit=banana")
        self.assertEqual(status, 400)

    # -- the read cannot escape the configured file -------------------------
    def test_request_cannot_point_at_another_file(self):
        marker = "DO-NOT-LEAK-THIS-FILE"
        other = Path(self.tmp.name) / "other.jsonl"
        other.write_text(json.dumps(
            {"ts": ts_of(1_700_000_000_000), "event": "seeded",
             "summary": marker}) + "\n", encoding="utf-8")
        for path in ("/v1/audit?path=other.jsonl",
                     "/v1/audit?file=../other.jsonl",
                     "/v1/audit?path=/etc/passwd"):
            status, obj, raw = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertNotIn(marker, raw)
            events = [e.get("event") for e in obj["entries"]]
            self.assertIn("server_start", events)

    def test_tail_behavior_preserved(self):
        status, obj, _ = self.request("GET", "/v1/audit/tail?n=5")
        self.assertEqual(status, 200)
        self.assertIn("entries", obj)
        self.assertLessEqual(obj["count"], 5)

    # -- the read itself is audited ------------------------------------------
    def test_audit_read_is_itself_audited(self):
        status, _, _ = self.request("GET", "/v1/audit?limit=1")
        self.assertEqual(status, 200)
        lines = self.audit_path.read_text(encoding="utf-8").splitlines()
        entries = [json.loads(ln) for ln in lines if ln.strip()]
        reads = [e for e in entries
                 if str(e.get("path", "")).startswith("/v1/audit?")]
        self.assertTrue(reads, "the audit read must appear in the log")
        self.assertTrue(any("audit read" in str(e.get("summary", ""))
                            for e in reads))

    # -- token-absence regression (spec §2) -----------------------------------
    def test_token_seeded_in_command_appears_nowhere(self):
        command = (f"echo {TOKEN}" if not ON_WINDOWS
                   else f"echo {TOKEN}")
        status, obj, _ = self.request("POST", "/v1/exec", {
            "command": command, "shell": SHELL, "wait_s": 10})
        self.assertEqual(status, 200)
        self.assertEqual(obj["state"], "done")
        # The command really ran and produced the token as OUTPUT —
        # job output is not audit content and is not scrubbed.
        self.assertIn(TOKEN, obj["stdout"])
        log_text = self.audit_path.read_text(encoding="utf-8")
        self.assertNotIn(TOKEN, log_text)
        status, obj, raw = self.request("GET", "/v1/audit?limit=1000")
        self.assertEqual(status, 200)
        self.assertNotIn(TOKEN, raw)
        # The exec itself IS still audited (the entry exists; only
        # the credential string inside its summary is masked).
        summaries = [str(e.get("summary", "")) for e in obj["entries"]]
        self.assertTrue(any("echo ***" in s for s in summaries),
                        "exec entry must be present with token masked")

    # -- client library + CLI ---------------------------------------------------
    def test_client_audit_method(self):
        page = self.client.audit(limit=3)
        self.assertIn("entries", page)
        self.assertLessEqual(len(page["entries"]), 3)
        page2 = self.client.audit(since=1_700_000_000.0, limit=5)
        self.assertIn("entries", page2)

    def test_client_cli_audit_prints_one_json_per_line(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = bridge_client.main(
                ["--base", self.base, "--token", TOKEN,
                 "audit", "--limit", "2"])
        self.assertEqual(rc, 0)
        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        self.assertTrue(lines)
        for ln in lines:
            parsed = json.loads(ln)
            self.assertIn("ts", parsed)


if __name__ == "__main__":
    unittest.main()
