"""V1.1 tests: boot-surviving core topology.

Three pieces, all exercised without a PC:
- the supervisor core publishes display-state.json itself (so the
  file stays fresh with no avatar window open — the headless boot
  form), from the same signals and mapping the window uses;
- the GUI's mode choice (attach / foreign / own) as a pure function
  with the probe injected;
- the headless supervisor entry: --headless runs, and the stdio
  guard gives a pythonw-style None stdout a log file instead.

The Windows activation itself — a SYSTEM boot task actually
starting the core before logon, the avatar attaching on the real
desktop — is owner-PC verification, listed in docs/TEST_PLAN.md.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import supervisor as supervisor_mod  # noqa: E402
import supervisor_gui  # noqa: E402

GOOD_AGENT = '''
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
cfg_path = sys.argv[sys.argv.index("--config") + 1]
cfg = json.loads(open(cfg_path, encoding="utf-8").read())
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"{\\"agent\\": \\"muse-pc-bridge\\", \\"jobs_running\\": 0, \\"sessions_open\\": 0, \\"processes_alive\\": 0}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass
HTTPServer(("127.0.0.1", int(cfg["port"])), H).serve_forever()
'''


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class FakeProjectMixin:
    def make_project(self, agent_source=GOOD_AGENT):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        install = root / "install"
        (install / "agent").mkdir(parents=True)
        (install / "agent" / "bridge_agent.py").write_text(
            agent_source, encoding="utf-8")
        state = root / "state"
        state.mkdir()
        config = root / "config.json"
        config.write_text(json.dumps({
            "host": "127.0.0.1", "port": free_port(), "token": "x",
            "state_dir": str(state)}), encoding="utf-8")
        return tmp, install, config, state


class DisplayPublishingTests(FakeProjectMixin, unittest.TestCase):
    def make_supervisor(self):
        tmp, install, config, state = self.make_project()
        self.addCleanup(tmp.cleanup)
        sup = supervisor_mod.Supervisor(install, config, state)
        sup._last_status = {"state": "running"}
        return sup, state

    def test_publishes_working_state(self):
        sup, state = self.make_supervisor()
        sup._fetch_agent_status = lambda: {
            "jobs_running": 2, "sessions_open": 0, "processes_alive": 0}
        sup._publish_display_state()
        obj = json.loads((state / "display-state.json").read_text(
            encoding="utf-8"))
        self.assertEqual(obj["state"], "working")
        self.assertEqual(obj["art"], "working")
        self.assertIn("since", obj)

    def test_publishes_idle_and_alert_states(self):
        sup, state = self.make_supervisor()
        sup._fetch_agent_status = lambda: {
            "jobs_running": 0, "sessions_open": 0, "processes_alive": 0}
        sup._publish_display_state()
        obj = json.loads((state / "display-state.json").read_text(
            encoding="utf-8"))
        self.assertEqual(obj["state"], "idle")
        # Agent vanishes and stays gone past the alert window.
        sup._fetch_agent_status = lambda: None
        sup._agent_down_since = time.time() - 100
        sup._publish_display_state()
        obj = json.loads((state / "display-state.json").read_text(
            encoding="utf-8"))
        self.assertEqual(obj["state"], "alert")
        self.assertEqual(obj["label"], "Agent not responding")

    def test_writes_only_on_state_change(self):
        sup, state = self.make_supervisor()
        sup._fetch_agent_status = lambda: {
            "jobs_running": 0, "sessions_open": 0, "processes_alive": 0}
        sup._publish_display_state()
        first = (state / "display-state.json").read_text(encoding="utf-8")
        sup._publish_display_state()
        second = (state / "display-state.json").read_text(encoding="utf-8")
        self.assertEqual(first, second)  # same content incl. "since"

    def test_run_loop_publishes_with_fake_agent(self):
        tmp, install, config, state = self.make_project()
        self.addCleanup(tmp.cleanup)
        sup = supervisor_mod.Supervisor(
            install, config, state, restart_base_delay=0.2,
            restart_max_delay=1.0, health_timeout_s=4.0,
            health_interval_s=0.2)
        thread = threading.Thread(target=sup.run, daemon=True)
        thread.start()
        try:
            deadline = time.time() + 20
            obj = None
            while time.time() < deadline:
                path = state / "display-state.json"
                if path.exists():
                    try:
                        obj = json.loads(path.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        obj = None
                    # The first publish legitimately lands as
                    # "connecting" (agent not up yet); wait for the
                    # state to settle to idle.
                    if obj and obj.get("state") == "idle":
                        break
                time.sleep(0.1)
            self.assertIsNotNone(obj, "display-state.json never appeared")
            self.assertEqual(obj["state"], "idle")
        finally:
            sup.stop()
            thread.join(timeout=15)


class ChooseGuiModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"
        self.state.mkdir()
        self.config = Path(self.tmp.name) / "config.json"
        self.config.write_text("{}", encoding="utf-8")
        self.sleeps = []

    def write_supervisor_status(self, state):
        (self.state / "supervisor-status.json").write_text(
            json.dumps({"state": state}), encoding="utf-8")

    def choose(self, fetch):
        return supervisor_gui.choose_gui_mode(
            self.config, self.state, fetch=fetch, attempts=3,
            interval_s=0.01, sleep=self.sleeps.append)

    def test_attach_when_our_agent_answers(self):
        mode, found = self.choose(lambda _p: {"agent": "muse-pc-bridge"})
        self.assertEqual(mode, "attach")
        self.assertEqual(found["agent"], "muse-pc-bridge")
        self.assertEqual(self.sleeps, [])

    def test_foreign_when_something_else_answers(self):
        mode, _found = self.choose(lambda _p: {"agent": "something-else"})
        self.assertEqual(mode, "foreign")

    def test_own_when_nothing_answers_and_no_core(self):
        mode, found = self.choose(lambda _p: None)
        self.assertEqual((mode, found), ("own", None))
        self.assertEqual(self.sleeps, [])  # no pointless waiting

    def test_own_immediately_when_core_reports_running(self):
        # "running" is steady state, not a start in progress: if the
        # agent does not answer, the core is gone — no retry window.
        self.write_supervisor_status("running")
        mode, _ = self.choose(lambda _p: None)
        self.assertEqual(mode, "own")
        self.assertEqual(self.sleeps, [])

    def test_attach_after_retry_while_core_is_starting(self):
        self.write_supervisor_status("starting")
        answers = [None, None, {"agent": "muse-pc-bridge"}]
        mode, _ = self.choose(lambda _p: answers.pop(0))
        self.assertEqual(mode, "attach")
        self.assertEqual(len(self.sleeps), 2)

    def test_own_after_retries_when_core_never_answers(self):
        self.write_supervisor_status("restarting")
        mode, _ = self.choose(lambda _p: None)
        self.assertEqual(mode, "own")
        self.assertEqual(len(self.sleeps), 3)


class HeadlessEntryTests(FakeProjectMixin, unittest.TestCase):
    def test_headless_stdio_redirects_none_streams(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = Path(tmp.name) / "state"
        real_out, real_err = sys.stdout, sys.stderr
        try:
            sys.stdout = None
            sys.stderr = None
            supervisor_mod._headless_stdio(state)
            self.assertIsNotNone(sys.stdout)
            print("hello core", flush=True)
        finally:
            out = sys.stdout
            sys.stdout, sys.stderr = real_out, real_err
        if out is not None and out is not real_out:
            out.close()
        log = (state / "supervisor-core.log").read_text(encoding="utf-8")
        self.assertIn("hello core", log)

    def test_headless_supervisor_process_runs(self):
        tmp, install, config, state = self.make_project()
        self.addCleanup(tmp.cleanup)
        proc = subprocess.Popen(
            [sys.executable,
             str(PROJECT_DIR / "agent" / "supervisor.py"),
             "--headless", "--config", str(config),
             "--install-root", str(install)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            deadline = time.time() + 20
            status = None
            while time.time() < deadline:
                path = state / "supervisor-status.json"
                if path.exists():
                    try:
                        status = json.loads(path.read_text(
                            encoding="utf-8"))
                    except json.JSONDecodeError:
                        status = None
                    if status and status.get("state") == "running":
                        break
                if proc.poll() is not None:
                    self.fail(f"headless supervisor exited early: "
                              f"{proc.stdout.read() if proc.stdout else ''}")
                time.sleep(0.1)
            self.assertIsNotNone(status)
            self.assertEqual(status["state"], "running")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    unittest.main()
