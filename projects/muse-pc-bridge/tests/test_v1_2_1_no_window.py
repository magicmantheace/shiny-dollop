"""V1.2.1 tests: console-free spawns by default (no window popups).

The defect this fixes (owner report, 2026-11-21): the production
agent runs under pythonw with no console of its own, so every
console child it spawned — powershell/cmd for jobs and sessions,
taskkill, the UIA helper — had Windows create a brand-new console
window for it on the owner's desktop, flashing a terminal over
whatever he was doing (including mid-game). The fix passes
CREATE_NO_WINDOW at every agent spawn site unless the caller
explicitly opts into visibility with "visible": true, and the
supervisor hides its agent child when it has no console itself
(console service form unchanged: its shared console is the kill
switch).

Hermetic pattern as the rest of the suite: a real agent on an
ephemeral loopback port with temp dirs. The flag logic is unit
tested by simulating the Windows branch (IS_WINDOWS +
CREATE_NO_WINDOW stubbed in); POSIX behaviour (unchanged spawn
semantics, output capture, the visible opt-in accepted end to
end) is exercised live. That no window actually appears is
owner-PC verification, listed in docs/TEST_PLAN.md.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))
sys.path.insert(0, str(PROJECT_DIR / "client"))

import bridge_agent  # noqa: E402
import bridge_client  # noqa: E402
import supervisor  # noqa: E402

TOKEN = "test-token-v121-nowindow"
ON_WINDOWS = sys.platform.startswith("win")
SHELL = "cmd" if ON_WINDOWS else "posix"
FAKE_NO_WINDOW = 0x08000000


class SpawnKwargsTests(unittest.TestCase):
    def test_posix_kwargs_unchanged(self):
        if ON_WINDOWS:
            self.skipTest("POSIX expectations")
        self.assertEqual(bridge_agent.hidden_spawn_kwargs(), {})
        self.assertEqual(bridge_agent.hidden_spawn_kwargs(True), {})
        self.assertEqual(bridge_agent.spawn_kwargs(),
                         {"start_new_session": True})
        self.assertEqual(bridge_agent.spawn_kwargs(True),
                         {"start_new_session": True})

    def _windows_sim(self):
        """Simulate the Windows branch on a POSIX test host."""
        import os
        patchers = [mock.patch.object(bridge_agent, "IS_WINDOWS", True),
                    mock.patch.object(os, "name", "nt")]
        if not hasattr(subprocess, "CREATE_NO_WINDOW"):
            patchers.append(mock.patch.object(
                subprocess, "CREATE_NO_WINDOW", FAKE_NO_WINDOW,
                create=True))
        for p in patchers:
            p.start()
        return patchers

    def test_windows_default_is_console_free(self):
        patchers = self._windows_sim()
        try:
            self.assertEqual(
                bridge_agent.hidden_spawn_kwargs(),
                {"creationflags": subprocess.CREATE_NO_WINDOW})
            self.assertEqual(
                bridge_agent.spawn_kwargs(),
                {"creationflags": subprocess.CREATE_NO_WINDOW})
        finally:
            for p in patchers:
                p.stop()

    def test_windows_visible_opts_back_in(self):
        patchers = self._windows_sim()
        try:
            self.assertEqual(bridge_agent.hidden_spawn_kwargs(True), {})
            self.assertEqual(bridge_agent.spawn_kwargs(True), {})
        finally:
            for p in patchers:
                p.stop()

    def test_job_records_visible_flag(self):
        class FakeCore:
            cfg = {"job_output_cap_bytes": 65536}

        def make(payload):
            return bridge_agent.Job(FakeCore(), payload, ["/bin/sh"],
                                    "/tmp", {}, None)

        self.assertFalse(make({"command": "true"}).visible)
        self.assertTrue(make({"command": "true",
                              "visible": True}).visible)
        # Only a literal true opts in — truthy strings do not.
        self.assertFalse(make({"command": "true",
                               "visible": "yes"}).visible)


class SupervisorSpawnTests(unittest.TestCase):
    def test_has_console_true_off_windows(self):
        if ON_WINDOWS:
            self.skipTest("ctypes console probe is Windows-only")
        self.assertTrue(supervisor._has_console())

    def test_start_child_passes_no_creationflags_on_posix(self):
        if ON_WINDOWS:
            self.skipTest("POSIX spawn shape")
        sup = supervisor.Supervisor(Path("/nonexistent"),
                                    Path("/nonexistent/config.json"),
                                    Path("/nonexistent/state"))
        with mock.patch.object(supervisor.subprocess, "Popen") as popen:
            popen.return_value = mock.Mock(pid=4242)
            sup._start_child()
        _, kwargs = popen.call_args
        self.assertNotIn("creationflags", kwargs)


class VisibleEndToEndTests(unittest.TestCase):
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
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.client = bridge_client.BridgeClient(
            f"http://127.0.0.1:{cls.port}", TOKEN)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def test_exec_default_and_visible_both_run(self):
        cmd = "echo nw-default" if ON_WINDOWS else "echo nw-default"
        job = self.client.exec_run(cmd, shell=SHELL)
        self.assertEqual(job["state"], "done", job)
        self.assertIn("nw-default", job["stdout"])
        job = self.client.exec_run(cmd, shell=SHELL, visible=True)
        self.assertEqual(job["state"], "done", job)
        self.assertIn("nw-default", job["stdout"])

    def test_process_spawn_visible_accepted(self):
        cmd = "ping -n 3 127.0.0.1 >nul" if ON_WINDOWS else "sleep 2"
        obj = self.client.process_spawn(command=cmd, shell=SHELL,
                                        visible=True)
        self.assertTrue(obj["alive"])
        self.assertFalse(obj["gui"])
        self.client.process_kill(obj["process_id"])


if __name__ == "__main__":
    unittest.main()
