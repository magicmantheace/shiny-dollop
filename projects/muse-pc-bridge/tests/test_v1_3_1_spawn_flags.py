"""V1.3.1 regression: detached spawns must not use DETACHED_PROCESS.

Defect found at the 1.3.0 deploy smoke (2026-11-24, owner's PC):
every detached spawn with shell=powershell exited 0 immediately
without running its command — empty logs, no side effects — while
the same command through the job/exec path worked. A probe matrix
on the PC isolated the cause to the subprocess creation flag
DETACHED_PROCESS (0x8): Windows PowerShell 5.1 created with that
flag exits 0 without ever running its -Command. It alone
reproduces; CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW runs the
command and stays console-free. (This was also the true root
cause of the 2026-11-21 detached powershell no-run incident,
previously misattributed to command-line quoting.)

These tests pin the flag composition under a simulated Windows
branch, in the style of test_v1_2_1_no_window.py. That the spawn
actually executes on Windows is owner-PC verification, recorded
in docs/MUSE_HANDOFF.md.
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

import bridge_agent  # noqa: E402
import project_mode  # noqa: E402

FAKE_GROUP = 0x00000200        # CREATE_NEW_PROCESS_GROUP
FAKE_DETACHED = 0x00000008     # DETACHED_PROCESS
FAKE_NO_WINDOW = 0x08000000    # CREATE_NO_WINDOW
FAKE_BREAKAWAY = 0x01000000    # CREATE_BREAKAWAY_FROM_JOB


def _windows_sim(testcase: unittest.TestCase):
    """Simulate the Windows branch on a POSIX test host."""
    patchers = [mock.patch.object(bridge_agent, "IS_WINDOWS", True)]
    for name, value in (("CREATE_NEW_PROCESS_GROUP", FAKE_GROUP),
                        ("DETACHED_PROCESS", FAKE_DETACHED),
                        ("CREATE_NO_WINDOW", FAKE_NO_WINDOW),
                        ("CREATE_BREAKAWAY_FROM_JOB", FAKE_BREAKAWAY)):
        if not hasattr(subprocess, name):
            patchers.append(mock.patch.object(
                subprocess, name, value, create=True))
    for p in patchers:
        p.start()
        testcase.addCleanup(p.stop)
    return patchers


class _FakeCore:
    def __init__(self, state_dir: Path):
        self.cfg = dict(bridge_agent.DEFAULT_CONFIG)
        self.state_dir = state_dir
        self.processes: dict = {}
        self._processes_lock = threading.Lock()

    def _save_processes(self):
        pass


class SpawnDetachedFlagTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = _FakeCore(Path(self.tmp.name) / "state")

    def tearDown(self):
        self.tmp.cleanup()

    def _spawn_flags(self, payload, session_mode=False):
        _windows_sim(self)
        with mock.patch.object(bridge_agent.subprocess, "Popen") as popen:
            popen.return_value = mock.Mock(pid=4321)
            bridge_agent.spawn_detached(self.core, payload,
                                        session_mode=session_mode)
        _, kwargs = popen.call_args
        return kwargs.get("creationflags", 0)

    def test_powershell_spawn_has_no_detached_process_flag(self):
        flags = self._spawn_flags(
            {"command": "Start-Sleep -Seconds 20", "shell": "powershell"})
        self.assertFalse(flags & FAKE_DETACHED,
                         "DETACHED_PROCESS makes Windows PowerShell "
                         "exit 0 without running its -Command")
        self.assertTrue(flags & FAKE_GROUP)
        self.assertTrue(flags & FAKE_NO_WINDOW)

    def test_session_mode_spawn_has_no_detached_process_flag(self):
        flags = self._spawn_flags(
            {"command": "Start-Sleep -Seconds 20", "shell": "powershell"},
            session_mode=True)
        self.assertFalse(flags & FAKE_DETACHED)
        self.assertTrue(flags & FAKE_GROUP)
        self.assertTrue(flags & FAKE_NO_WINDOW)

    def test_cmd_spawn_has_no_detached_process_flag(self):
        flags = self._spawn_flags(
            {"command": "ping -n 21 127.0.0.1", "shell": "cmd"})
        self.assertFalse(flags & FAKE_DETACHED)
        self.assertTrue(flags & FAKE_GROUP)
        self.assertTrue(flags & FAKE_NO_WINDOW)


class ProjectModeLaunchFlagTests(unittest.TestCase):
    def test_relaunch_has_no_detached_process_flag(self):
        _windows_sim(self)
        ops = project_mode.WindowsOps.__new__(project_mode.WindowsOps)
        with mock.patch.object(project_mode.subprocess, "Popen") as popen:
            ok, _msg = ops.launch(r"C:\Apps\Lively\Lively.exe")
        self.assertTrue(ok)
        _, kwargs = popen.call_args
        flags = kwargs.get("creationflags", 0)
        self.assertFalse(flags & FAKE_DETACHED)
        self.assertTrue(flags & FAKE_GROUP)


if __name__ == "__main__":
    unittest.main()
