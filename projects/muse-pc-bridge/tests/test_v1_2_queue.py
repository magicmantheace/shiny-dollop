"""V1.2 tests: resident queue runner (spec §3).

End-to-end over HTTP against the real agent (whose create_server
starts the real runner thread), plus direct-runner unit tests for
restart recovery and the mid-run UAC grace. Everything runs on
loopback with dummy tokens and temp dirs; the commands used are
platform shell one-liners ("posix" off Windows, "cmd" on Windows).

Proof style: execution is proven by marker files the commands
create; non-execution is proven by their absence.
"""

from __future__ import annotations

import hashlib
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
import queue_runner  # noqa: E402

TOKEN = "dummy-token-for-v12-queue-tests"
ON_WINDOWS = sys.platform.startswith("win")
SHELL = "cmd" if ON_WINDOWS else "posix"


def wait_for(predicate, timeout=15.0, interval=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def make_cfg(root: Path, **overrides) -> dict:
    cfg = dict(bridge_agent.DEFAULT_CONFIG)
    cfg.update({
        "host": "127.0.0.1", "port": 0, "token": TOKEN,
        "allowed_file_root": str(root / "bridge-files"),
        "audit_log": str(root / "logs" / "audit.jsonl"),
        "state_dir": str(root / "state"),
        "default_timeout_s": 10, "max_timeout_s": 30,
    })
    cfg.update(overrides)
    return cfg


class QueueHttpTestCase(unittest.TestCase):
    """Base: boots the real server (runner included) per class."""

    extra_cfg: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.server = bridge_agent.create_server(
            make_cfg(cls.root, **cls.extra_cfg))
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.client = bridge_client.BridgeClient(cls.base, TOKEN)
        cls.runner = cls.server.core.queue_runner
        cls.file_root = cls.root / "bridge-files"

    @classmethod
    def tearDownClass(cls):
        if cls.runner is not None:
            cls.runner.stop()
        cls.server.core.log_stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

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
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"raw": body}

    def counts(self):
        status, obj = self.request("GET", "/v1/queue")
        self.assertEqual(status, 200)
        return obj["counts"]

    def job_in(self, state, qid):
        status, obj = self.request("GET", "/v1/queue")
        self.assertEqual(status, 200)
        for summary in obj["jobs"][state]:
            if summary["id"] == qid:
                return summary
        return None

    def marker_cmd(self, marker: Path, text="ran") -> str:
        if ON_WINDOWS:
            return f"echo {text} > \"{marker}\""
        return f"echo {text} > '{marker}'"

    def sleep_cmd(self, seconds: float) -> str:
        if ON_WINDOWS:
            return f"ping -n {int(seconds) + 1} 127.0.0.1 >nul"
        return f"sleep {seconds}"

    def audit_events(self):
        lines = (self.root / "logs" / "audit.jsonl").read_text(
            encoding="utf-8").splitlines()
        return [json.loads(ln) for ln in lines if ln.strip()]


class QueueLifecycleTests(QueueHttpTestCase):
    def test_submit_run_done_with_audit_trail(self):
        status, rec = self.request("POST", "/v1/queue", {
            "kind": "exec", "command": "echo queue-ok", "shell": SHELL,
            "on_failure": "continue", "note": "lifecycle probe"})
        self.assertEqual(status, 202)
        qid = rec["id"]
        self.assertEqual(rec["state"], "pending")
        # The §1 pre-flight assessment is stored in the record.
        self.assertIn("uac", rec)
        self.assertFalse(rec["uac"]["likely"])
        self.assertTrue(wait_for(
            lambda: self.job_in("done", qid) is not None))
        done = self.job_in("done", qid)
        self.assertEqual(done["exit_code"], 0)
        self.assertIn("exec_job_id", done)
        # The executor job itself finished with the right output:
        # queue execution IS the /v1/exec executor.
        status, job = self.request("GET", f"/v1/jobs/{done['exec_job_id']}")
        self.assertEqual(status, 200)
        self.assertIn("queue-ok", job["stdout"])
        events = [e for e in self.audit_events()
                  if e.get("queue_job_id") == qid]
        kinds = [e["event"] for e in events]
        self.assertIn("queue_submitted", kinds)
        self.assertIn("queue_started", kinds)
        finished = [e for e in events if e["event"] == "queue_finished"]
        self.assertTrue(finished)
        self.assertEqual(finished[0]["exit_code"], 0)

    def test_sequential_execution(self):
        ids = []
        for _ in range(2):
            status, rec = self.request("POST", "/v1/queue", {
                "kind": "exec", "command": self.sleep_cmd(1),
                "shell": SHELL, "on_failure": "continue"})
            self.assertEqual(status, 202)
            ids.append(rec["id"])
        self.assertTrue(wait_for(
            lambda: all(self.job_in("done", q) for q in ids),
            timeout=20))
        records = []
        for qid in ids:
            raw = json.loads((self.runner.dirs["done"] / f"{qid}.json")
                             .read_text(encoding="utf-8"))
            records.append(raw)
        # Whichever ran first, its successor started only after it
        # finished: execution windows never overlap (strictly serial).
        records.sort(key=lambda r: r["started_at"])
        self.assertGreaterEqual(records[1]["started_at"],
                                records[0]["finished_at"])

    def test_script_job_runs_when_hash_matches(self):
        script = self.file_root / "job1.sh"
        marker = self.root / "script-ran.txt"
        body = self.marker_cmd(marker, "from-script") + "\n"
        script.write_text(body, encoding="utf-8")
        digest = hashlib.sha256(script.read_bytes()).hexdigest()
        status, rec = self.request("POST", "/v1/queue", {
            "kind": "script", "script": "job1.sh",
            "script_sha256": digest, "shell": SHELL,
            "on_failure": "continue"})
        self.assertEqual(status, 202)
        self.assertTrue(wait_for(
            lambda: self.job_in("done", rec["id"]) is not None))
        self.assertTrue(marker.exists())

    def test_validation_errors(self):
        before = self.counts()
        for payload in ({"kind": "exec"},
                        {"kind": "script", "script": "x.sh"},
                        {"kind": "script", "script": "x.sh",
                         "script_sha256": "not-hex"},
                        {"kind": "bogus", "command": "echo hi"},
                        {"kind": "exec", "command": "echo hi",
                         "uac_policy": "bogus"},
                        {"kind": "exec", "command": "echo hi",
                         "on_failure": "bogus"},
                        {"kind": "script", "script": "../escape.sh",
                         "script_sha256": "a" * 64}):
            status, _ = self.request("POST", "/v1/queue", payload)
            self.assertEqual(status, 400, f"payload {payload!r}")
        # Nothing was stored for any of them.
        self.assertEqual(self.counts(), before)

    def test_queue_requires_auth(self):
        status, _ = self.request("GET", "/v1/queue", token=None)
        self.assertEqual(status, 401)
        status, _ = self.request("POST", "/v1/queue",
                                 {"kind": "exec", "command": "echo hi"},
                                 token=None)
        self.assertEqual(status, 401)

    def test_client_library_round_trip(self):
        rec = self.client.queue_submit_exec(
            "echo via-client", shell=SHELL, on_failure="continue")
        self.assertIn("id", rec)
        self.assertTrue(wait_for(
            lambda: self.job_in("done", rec["id"]) is not None))
        listing = self.client.queue_list()
        self.assertGreaterEqual(listing["counts"]["done"], 1)


class QueuePolicyTests(QueueHttpTestCase):
    def test_hash_mismatch_refuses_and_never_executes(self):
        script = self.file_root / "pinned.sh"
        marker = self.root / "must-not-exist.txt"
        script.write_text(self.marker_cmd(marker) + "\n",
                          encoding="utf-8")
        status, rec = self.request("POST", "/v1/queue", {
            "kind": "script", "script": "pinned.sh",
            "script_sha256": "0" * 64, "shell": SHELL,
            "on_failure": "continue"})
        self.assertEqual(status, 202)
        self.assertTrue(wait_for(
            lambda: self.job_in("failed", rec["id"]) is not None))
        failed = self.job_in("failed", rec["id"])
        self.assertEqual(failed["reason"], "script_hash_mismatch")
        self.assertFalse(marker.exists())

    def test_edited_script_no_longer_matches_its_pin(self):
        script = self.file_root / "edited.sh"
        marker = self.root / "edited-must-not-run.txt"
        script.write_text("echo v1\n", encoding="utf-8")
        digest = hashlib.sha256(script.read_bytes()).hexdigest()
        # Pause so the edit lands before the runner picks it up.
        self.client.queue_pause()
        try:
            status, rec = self.request("POST", "/v1/queue", {
                "kind": "script", "script": "edited.sh",
                "script_sha256": digest, "shell": SHELL,
                "on_failure": "continue"})
            self.assertEqual(status, 202)
            script.write_text(self.marker_cmd(marker) + "\n",
                              encoding="utf-8")
        finally:
            self.client.queue_resume()
        self.assertTrue(wait_for(
            lambda: self.job_in("failed", rec["id"]) is not None))
        self.assertEqual(self.job_in("failed", rec["id"])["reason"],
                         "script_hash_mismatch")
        self.assertFalse(marker.exists())

    def test_skip_if_likely_never_executes(self):
        marker = self.root / "skip-marker.txt"
        cmd = (f"echo msiexec /i setup.msi > \"{marker}\"" if ON_WINDOWS
               else f"echo msiexec /i setup.msi > '{marker}'")
        status, rec = self.request("POST", "/v1/queue", {
            "kind": "exec", "command": cmd, "shell": SHELL,
            "on_failure": "continue"})
        self.assertEqual(status, 202)
        self.assertTrue(rec["uac"]["likely"])  # stored assessment
        self.assertTrue(wait_for(
            lambda: self.job_in("failed", rec["id"]) is not None))
        self.assertEqual(self.job_in("failed", rec["id"])["reason"],
                         "uac_likely")
        self.assertFalse(marker.exists())

    def test_run_anyway_executes_despite_likely(self):
        marker = self.root / "anyway-marker.txt"
        cmd = (f"echo msiexec /i setup.msi > \"{marker}\"" if ON_WINDOWS
               else f"echo msiexec /i setup.msi > '{marker}'")
        status, rec = self.request("POST", "/v1/queue", {
            "kind": "exec", "command": cmd, "shell": SHELL,
            "uac_policy": "run-anyway", "on_failure": "continue"})
        self.assertEqual(status, 202)
        self.assertTrue(wait_for(
            lambda: self.job_in("done", rec["id"]) is not None))
        self.assertTrue(marker.exists())

    def test_require_no_uac_stores_nothing(self):
        before = self.counts()
        files_before = {s: sorted(p.name for p in
                                  self.runner.dirs[s].glob("*.json"))
                        for s in ("pending", "running", "done", "failed")}
        status, obj = self.request("POST", "/v1/queue", {
            "kind": "exec", "command": "echo msiexec /i setup.msi",
            "shell": SHELL, "require_no_uac": True})
        self.assertEqual(status, 409)
        self.assertEqual(obj["error"], "uac_likely")
        self.assertTrue(obj["uac"]["likely"])
        self.assertEqual(self.counts(), before)
        files_after = {s: sorted(p.name for p in
                                 self.runner.dirs[s].glob("*.json"))
                       for s in ("pending", "running", "done", "failed")}
        self.assertEqual(files_after, files_before)


class QueueFailureModeTests(QueueHttpTestCase):
    def exit_cmd(self, code: int) -> str:
        return f"exit /b {code}" if ON_WINDOWS else f"exit {code}"

    def test_on_failure_stop_halts_until_resume(self):
        status, a = self.request("POST", "/v1/queue", {
            "kind": "exec", "command": self.exit_cmd(3), "shell": SHELL,
            "on_failure": "stop"})
        self.assertEqual(status, 202)
        status, b = self.request("POST", "/v1/queue", {
            "kind": "exec", "command": "echo second", "shell": SHELL,
            "on_failure": "stop"})
        self.assertEqual(status, 202)
        self.assertTrue(wait_for(
            lambda: self.job_in("failed", a["id"]) is not None))
        failed = self.job_in("failed", a["id"])
        self.assertEqual(failed["reason"], "exit_code")
        self.assertEqual(failed["exit_code"], 3)
        # The runner halted: job B does not start on its own.
        time.sleep(1.0)
        self.assertIsNotNone(self.job_in("pending", b["id"]))
        status, obj = self.request("GET", "/v1/queue")
        self.assertTrue(obj["halted"])
        # Resume clears the halt and B runs.
        status, _ = self.request("POST", "/v1/queue/resume", {})
        self.assertEqual(status, 200)
        self.assertTrue(wait_for(
            lambda: self.job_in("done", b["id"]) is not None))

    def test_on_failure_continue_proceeds(self):
        status, a = self.request("POST", "/v1/queue", {
            "kind": "exec", "command": self.exit_cmd(5), "shell": SHELL,
            "on_failure": "continue"})
        status, b = self.request("POST", "/v1/queue", {
            "kind": "exec", "command": "echo after-failure",
            "shell": SHELL, "on_failure": "continue"})
        self.assertEqual(status, 202)
        self.assertTrue(wait_for(
            lambda: self.job_in("failed", a["id"]) is not None
            and self.job_in("done", b["id"]) is not None))


class QueuePauseCancelTests(QueueHttpTestCase):
    def test_pause_blocks_starts_and_resume_releases(self):
        status, obj = self.request("POST", "/v1/queue/pause", {})
        self.assertEqual(status, 200)
        self.assertTrue(obj["paused"])
        self.assertTrue(self.runner.pause_file.exists())
        status, rec = self.request("POST", "/v1/queue", {
            "kind": "exec", "command": "echo paused-job", "shell": SHELL,
            "on_failure": "continue"})
        self.assertEqual(status, 202)
        time.sleep(1.0)
        self.assertIsNotNone(self.job_in("pending", rec["id"]))
        self.assertEqual(self.counts()["running"], 0)
        status, obj = self.request("POST", "/v1/queue/resume", {})
        self.assertEqual(status, 200)
        self.assertFalse(obj["paused"])
        self.assertTrue(wait_for(
            lambda: self.job_in("done", rec["id"]) is not None))
        events = [e["event"] for e in self.audit_events()]
        self.assertIn("queue_paused", events)
        self.assertIn("queue_resumed", events)

    def test_pause_file_dropped_directly_also_pauses(self):
        # The owner's local kill switch: no API, no token.
        self.runner.pause_file.write_text("manual\n", encoding="utf-8")
        try:
            status, rec = self.request("POST", "/v1/queue", {
                "kind": "exec", "command": "echo direct-pause",
                "shell": SHELL, "on_failure": "continue"})
            self.assertEqual(status, 202)
            time.sleep(1.0)
            self.assertIsNotNone(self.job_in("pending", rec["id"]))
        finally:
            self.runner.pause_file.unlink()
        self.assertTrue(wait_for(
            lambda: self.job_in("done", rec["id"]) is not None))

    def test_cancel_pending(self):
        self.client.queue_pause()
        try:
            status, a = self.request("POST", "/v1/queue", {
                "kind": "exec", "command": "echo a", "shell": SHELL})
            status, b = self.request("POST", "/v1/queue", {
                "kind": "exec", "command": "echo b", "shell": SHELL})
            status, obj = self.request("DELETE", f"/v1/queue/{a['id']}")
            self.assertEqual(status, 200)
            self.assertTrue(obj["cancelled"])
            failed = self.job_in("failed", a["id"])
            self.assertEqual(failed["reason"], "cancelled")
            self.assertIsNotNone(self.job_in("pending", b["id"]))
            # Cancelling again: no longer pending -> 409; unknown -> 404.
            status, _ = self.request("DELETE", f"/v1/queue/{a['id']}")
            self.assertEqual(status, 409)
            status, _ = self.request("DELETE", "/v1/queue/deadbeef")
            self.assertEqual(status, 404)
        finally:
            self.client.queue_resume()

    def test_cancel_running_is_refused_here_but_job_cancel_works(self):
        status, rec = self.request("POST", "/v1/queue", {
            "kind": "exec", "command": self.sleep_cmd(30),
            "shell": SHELL, "timeout_s": 30, "on_failure": "continue"})
        self.assertEqual(status, 202)
        self.assertTrue(wait_for(
            lambda: self.job_in("running", rec["id"]) is not None))
        status, _ = self.request("DELETE", f"/v1/queue/{rec['id']}")
        self.assertEqual(status, 409)
        running = self.job_in("running", rec["id"])
        exec_id = running["exec_job_id"]
        status, obj = self.request("POST", f"/v1/jobs/{exec_id}/cancel", {})
        self.assertEqual(status, 200)
        self.assertTrue(obj["cancelled"])
        self.assertTrue(wait_for(
            lambda: self.job_in("failed", rec["id"]) is not None))
        self.assertEqual(self.job_in("failed", rec["id"])["reason"],
                         "killed")


class QueueRunnerUnitTests(unittest.TestCase):
    """Direct-runner tests: restart recovery, UAC grace, lifecycle."""

    def make_core(self, root: Path, **overrides):
        return bridge_agent.BridgeCore(make_cfg(root, **overrides))

    def test_restart_recovery_fails_interrupted_job(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        core = self.make_core(root)
        runner = queue_runner.QueueRunner(core, poll_interval_s=0.05)
        # Plant a job in running/ as a crashed core would leave it.
        runner.dirs["running"].mkdir(parents=True, exist_ok=True)
        record = {"id": "a" * 32, "kind": "exec", "command": "echo x",
                  "shell": SHELL, "timeout_s": 5,
                  "uac_policy": "run-anyway", "on_failure": "continue",
                  "note": "", "submitted_at": int(time.time()),
                  "state": "running"}
        (runner.dirs["running"] / f"{record['id']}.json").write_text(
            json.dumps(record), encoding="utf-8")
        runner.start()
        try:
            moved = runner._read_record("failed", record["id"])
            self.assertIsNotNone(moved)
            self.assertEqual(moved["reason"], "core_restarted")
            self.assertIsNone(runner._read_record("running",
                                                  record["id"]))
            events = [json.loads(ln)["event"] for ln in
                      core.audit_path.read_text(
                          encoding="utf-8").splitlines() if ln.strip()]
            self.assertIn("queue_failed", events)
        finally:
            runner.stop()
        self.assertIsNone(runner._thread)

    def test_waiting_uac_grace_expiry(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        core = self.make_core(root, queue_uac_grace_s=0.5)
        # A consent prompt is "on screen" for the whole run.
        core.uac = type("StubUac", (), {
            "snapshot": lambda self: {"active": True, "since": None},
        })()
        runner = queue_runner.QueueRunner(core, poll_interval_s=0.05)
        runner.start()
        try:
            record = queue_runner.validate_queue_payload(core, {
                "kind": "exec",
                "command": "sleep 30" if not ON_WINDOWS
                           else "ping -n 30 127.0.0.1 >nul",
                "shell": SHELL, "timeout_s": 30,
                "uac_policy": "run-anyway", "on_failure": "continue"})
            runner.submit(record)
            self.assertTrue(wait_for(
                lambda: runner._read_record("failed", record["id"])
                is not None, timeout=10))
            failed = runner._read_record("failed", record["id"])
            self.assertEqual(failed["reason"], "uac_timeout")
            events = [json.loads(ln)["event"] for ln in
                      core.audit_path.read_text(
                          encoding="utf-8").splitlines() if ln.strip()]
            self.assertIn("queue_waiting_uac", events)
            self.assertIn("queue_failed", events)
        finally:
            runner.stop()

    def test_runner_thread_stops_cleanly(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        core = self.make_core(Path(tmp.name))
        runner = queue_runner.QueueRunner(core, poll_interval_s=0.05)
        runner.start()
        thread = runner._thread
        self.assertTrue(thread.is_alive())
        runner.stop()
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
