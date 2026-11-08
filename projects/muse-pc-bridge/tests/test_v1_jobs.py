"""V1-S1 tests: async jobs, detached processes, interactive sessions.

Same hermetic pattern as test_bridge.py: a real agent on an ephemeral
loopback port with temp dirs, driven over HTTP. Proves the job model
on the machine running the suite; Windows execution is owner-PC only
(see docs/TEST_PLAN.md).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import bridge_agent  # noqa: E402

TOKEN = "test-token-v1-jobs"
ON_WINDOWS = sys.platform.startswith("win")
SHELL = "cmd" if ON_WINDOWS else "posix"


def echo_cmd(text: str) -> str:
    return f"echo {text}"


def sleep_cmd(seconds: float) -> str:
    if ON_WINDOWS:
        return f"ping -n {int(seconds) + 1} 127.0.0.1 >nul"
    return f"sleep {seconds}"


def two_step_cmd() -> str:
    """Print, pause, print — for incremental-output polling."""
    if ON_WINDOWS:
        return "echo first & ping -n 2 127.0.0.1 >nul & echo second"
    return "echo first; sleep 1; echo second"


def two_step_slow_cmd() -> str:
    """Print, pause ~3s, print — wide margin for 'visible while
    still running' polling assertions."""
    if ON_WINDOWS:
        return "echo first & ping -n 4 127.0.0.1 >nul & echo second"
    return "echo first; sleep 3; echo second"


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


class JobsTestCase(unittest.TestCase):
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
        cls.http = HttpClient(f"http://127.0.0.1:{cls.server.server_address[1]}")
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        # Kill any detached processes the tests spawned BEFORE the
        # temp dir is removed: a live process holds its stdout/stderr
        # log files (state/processes/*.log) open, and Windows refuses
        # to delete open files (WinError 32). POSIX unlink semantics
        # hid this on Linux/macOS — the first Windows suite run failed
        # tearDownClass with exactly that PermissionError.
        _, listing = cls.http.request("GET", "/v1/processes")
        for proc in listing.get("processes", []):
            if proc.get("alive"):
                cls.http.request(
                    "POST", f"/v1/processes/{proc['process_id']}/kill")
        deadline = time.time() + 10
        while time.time() < deadline:
            _, listing = cls.http.request("GET", "/v1/processes")
            if not any(p.get("alive")
                       for p in listing.get("processes", [])):
                break
            time.sleep(0.1)
        cls.server.core.log_stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        # Retry with a generous window: a just-killed process (or a
        # virus scanner briefly holding a fresh log) can release its
        # handles well after it stops reporting alive — the full
        # Windows suite run flaked on exactly this race twice with a
        # 3 s window while the isolated module passed. Genuine
        # cleanup failures still surface after the retries.
        for attempt in range(40):
            try:
                cls.tmp.cleanup()
                break
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.5)

    def wait_job(self, job_id, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            status, obj = self.http.request("GET", f"/v1/jobs/{job_id}")
            self.assertEqual(status, 200)
            if obj["state"] in ("done", "failed", "killed"):
                return obj
            time.sleep(0.1)
        self.fail(f"job {job_id} did not finish in {timeout}s")

    # -- jobs ---------------------------------------------------------------
    def test_submit_returns_job_id_immediately(self):
        started = time.time()
        status, obj = self.http.request(
            "POST", "/v1/exec", {"command": sleep_cmd(2), "shell": SHELL})
        elapsed = time.time() - started
        self.assertEqual(status, 202)
        self.assertIn("job_id", obj)
        self.assertLess(elapsed, 1.5,
                        "submit must not block for the command's duration")
        final = self.wait_job(obj["job_id"])
        self.assertEqual(final["state"], "done")
        self.assertEqual(final["exit_code"], 0)

    def test_job_output_and_exit_code(self):
        status, obj = self.http.request(
            "POST", "/v1/exec", {"command": echo_cmd("job-ok"), "shell": SHELL})
        self.assertEqual(status, 202)
        final = self.wait_job(obj["job_id"])
        self.assertIn("job-ok", final["stdout"])
        self.assertEqual(final["exit_code"], 0)

    def test_job_incremental_output_offsets(self):
        status, obj = self.http.request(
            "POST", "/v1/exec", {"command": two_step_cmd(), "shell": SHELL})
        job_id = obj["job_id"]
        # Consume output incrementally with offsets, the way a real
        # client does. The contract: a read at offset N returns exactly
        # the bytes after N — head + tail must reconstruct the whole,
        # with no repeats — regardless of how output flushes batch up.
        boundary = None
        seen = ""
        deadline = time.time() + 10
        while time.time() < deadline:
            _, snap = self.http.request("GET", f"/v1/jobs/{job_id}")
            seen = snap["stdout"]
            if "first" in seen:
                boundary = snap["stdout_bytes"]
                break
            time.sleep(0.05)
        self.assertIsNotNone(boundary, "never saw the first line")
        final = self.wait_job(job_id)
        full = final["stdout"]
        self.assertIn("first", full)
        self.assertIn("second", full)
        _, head = self.http.request(
            "GET", f"/v1/jobs/{job_id}?max_bytes={boundary}")
        _, tail = self.http.request(
            "GET", f"/v1/jobs/{job_id}?stdout_offset={boundary}")
        self.assertEqual(head["stdout"] + tail["stdout"], full)
        self.assertIn("first", head["stdout"])
        self.assertNotIn("first", tail["stdout"])

    def test_job_output_visible_while_job_still_running(self):
        # Regression (first Windows suite run): the job pump read with
        # BufferedReader.read(65536), which blocks until the buffer
        # fills or EOF — so a running job's small early output stayed
        # invisible until the process exited, defeating incremental
        # polling. The first line must be observable via the API while
        # the job state is still "running".
        status, obj = self.http.request(
            "POST", "/v1/exec",
            {"command": two_step_slow_cmd(), "shell": SHELL})
        self.assertEqual(status, 202)
        job_id = obj["job_id"]
        saw_first_while_running = False
        deadline = time.time() + 10
        while time.time() < deadline:
            _, snap = self.http.request("GET", f"/v1/jobs/{job_id}")
            if snap["state"] != "running":
                break
            if "first" in snap["stdout"]:
                saw_first_while_running = True
                break
            time.sleep(0.05)
        self.assertTrue(
            saw_first_while_running,
            "first line never visible while the job was still running")
        final = self.wait_job(job_id)
        self.assertIn("second", final["stdout"])

    def test_job_cancel(self):
        status, obj = self.http.request(
            "POST", "/v1/exec", {"command": sleep_cmd(30), "shell": SHELL,
                                 "timeout_s": 25})
        job_id = obj["job_id"]
        time.sleep(0.3)
        status, obj = self.http.request("POST", f"/v1/jobs/{job_id}/cancel")
        self.assertEqual(status, 200)
        self.assertTrue(obj["cancelled"])
        final = self.wait_job(job_id)
        self.assertEqual(final["state"], "killed")

    def test_job_timeout_marks_failed(self):
        status, obj = self.http.request(
            "POST", "/v1/exec", {"command": sleep_cmd(10), "shell": SHELL,
                                 "timeout_s": 0.5})
        final = self.wait_job(obj["job_id"])
        self.assertEqual(final["state"], "failed")
        self.assertTrue(final["timed_out"])

    def test_jobs_list(self):
        self.http.request("POST", "/v1/exec",
                          {"command": echo_cmd("listed"), "shell": SHELL})
        status, obj = self.http.request("GET", "/v1/jobs")
        self.assertEqual(status, 200)
        self.assertTrue(any(j["command"].find("listed") >= 0
                            for j in obj["jobs"]))

    def test_job_missing_is_404(self):
        status, _ = self.http.request("GET", "/v1/jobs/deadbeefdead")
        self.assertEqual(status, 404)

    def test_job_finish_is_audited_with_hashes(self):
        status, obj = self.http.request(
            "POST", "/v1/exec", {"command": echo_cmd("hashed"), "shell": SHELL})
        job_id = obj["job_id"]
        self.wait_job(job_id)
        time.sleep(0.2)  # job_finish audit lands with completion
        status, tail = self.http.request("GET", "/v1/audit/tail?n=100")
        self.assertEqual(status, 200)
        finishes = [e for e in tail["entries"]
                    if e.get("event") == "job_finish"
                    and e.get("job_id") == job_id]
        self.assertTrue(finishes, "expected a job_finish audit entry")
        entry = finishes[-1]
        self.assertIn("stdout_sha256", entry)
        self.assertEqual(len(entry["stdout_sha256"]), 64)

    # -- detached processes ---------------------------------------------------
    def test_detached_process_lifecycle(self):
        status, obj = self.http.request(
            "POST", "/v1/processes",
            {"command": sleep_cmd(30), "shell": SHELL, "name": "sleeper"})
        self.assertEqual(status, 201)
        proc_id = obj["process_id"]
        self.assertTrue(obj["alive"])
        self.assertGreater(obj["pid"], 0)

        status, obj = self.http.request("GET", "/v1/processes")
        self.assertEqual(status, 200)
        self.assertTrue(any(p["process_id"] == proc_id
                            for p in obj["processes"]))

        status, obj = self.http.request(
            "POST", f"/v1/processes/{proc_id}/kill")
        self.assertEqual(status, 200)
        self.assertTrue(obj["killed"])
        deadline = time.time() + 10
        alive = True
        while time.time() < deadline:
            _, snap = self.http.request("GET", f"/v1/processes/{proc_id}")
            alive = snap["alive"]
            if not alive:
                break
            time.sleep(0.1)
        self.assertFalse(alive, "killed process must stop reporting alive")

    def test_detached_process_output_goes_to_logs(self):
        status, obj = self.http.request(
            "POST", "/v1/processes",
            {"command": echo_cmd("detached-hello"), "shell": SHELL})
        self.assertEqual(status, 201)
        proc_id = obj["process_id"]
        deadline = time.time() + 10
        tail = ""
        while time.time() < deadline:
            _, snap = self.http.request(
                "GET", f"/v1/processes/{proc_id}?tail_bytes=4096")
            tail = snap.get("stdout_tail", "")
            if "detached-hello" in tail and not snap["alive"]:
                break
            time.sleep(0.1)
        self.assertIn("detached-hello", tail)

    # -- sessions ---------------------------------------------------------------
    def test_session_roundtrip(self):
        status, obj = self.http.request("POST", "/v1/sessions",
                                        {"shell": SHELL})
        self.assertEqual(status, 201)
        session_id = obj["session_id"]
        marker = "session-marker-42"
        line = f"echo {marker}\n"
        if ON_WINDOWS:
            line = f"echo {marker}\r\n"
        status, _ = self.http.request(
            "POST", f"/v1/sessions/{session_id}/input", {"data": line})
        self.assertEqual(status, 200)
        deadline = time.time() + 10
        output = ""
        offset = 0
        while time.time() < deadline:
            _, snap = self.http.request(
                "GET", f"/v1/sessions/{session_id}?offset={offset}")
            output += snap["output"]
            offset = snap["output_bytes"]
            if marker in output:
                break
            time.sleep(0.1)
        self.assertIn(marker, output)
        status, obj = self.http.request(
            "POST", f"/v1/sessions/{session_id}/close")
        self.assertEqual(status, 200)

    def test_session_missing_is_400(self):
        status, _ = self.http.request("GET", "/v1/sessions/deadbeefdead")
        self.assertEqual(status, 400)


# A shell substitute for the pipe-pump regression: reads stdin lines
# and answers each one immediately, then keeps running (never EOFs).
ECHO_CHILD = (
    "import sys\n"
    "while True:\n"
    "    line = sys.stdin.readline()\n"
    "    if not line:\n"
    "        break\n"
    "    sys.stdout.write('reply:' + line)\n"
    "    sys.stdout.flush()\n"
)


class PipePumpRegressionTests(unittest.TestCase):
    """Regression for the pipe-pump output starvation found by the
    first Windows suite run (61 tests: test_session_roundtrip FAIL —
    session output empty forever, live-reproduced over the API for
    both powershell and cmd sessions).

    Session._pump_pipe read with BufferedReader.read(65536), which
    blocks until 65536 bytes arrive or EOF; an interactive shell
    never EOFs, so its output starved. On POSIX the suite only ever
    exercised the PTY path, which is why the VM stayed green.

    This test forces the pipe path on any platform (IS_WINDOWS
    patched, which is also what selects the branch on real Windows)
    around a line-echo child, and requires output in the buffer
    WHILE the child is still alive.
    """

    def test_session_pipe_output_streams_while_shell_alive(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = dict(bridge_agent.DEFAULT_CONFIG)
            cfg.update({
                "host": "127.0.0.1", "port": 0, "token": TOKEN,
                "allowed_file_root": str(root / "bridge-files"),
                "audit_log": str(root / "logs" / "audit.jsonl"),
                "state_dir": str(root / "state"),
                "default_timeout_s": 10, "max_timeout_s": 30,
            })
            core = bridge_agent.BridgeCore(cfg)
            argv = [sys.executable, "-u", "-c", ECHO_CHILD]
            with mock.patch.object(bridge_agent, "IS_WINDOWS", True), \
                    mock.patch.object(bridge_agent, "shell_argv",
                                      return_value=argv):
                session = bridge_agent.Session(core, "posix", str(root),
                                               dict(os.environ))
                try:
                    session.send(b"hello\n")
                    seen = ""
                    deadline = time.time() + 5
                    while time.time() < deadline:
                        seen, _ = session.buffer.text()
                        if "reply:hello" in seen:
                            break
                        time.sleep(0.05)
                    self.assertIn("reply:hello", seen)
                    self.assertIsNone(
                        session.proc.poll(),
                        "output must arrive while the shell is still "
                        "alive — not flushed by its exit/EOF")
                finally:
                    # close() inside the patch: kill_tree consults
                    # IS_WINDOWS, and the child shares this process's
                    # group (start_new_session was False under the
                    # patch), so the POSIX killpg path must not run.
                    session.close()


if __name__ == "__main__":
    unittest.main()
