"""Regression tests: Windows shell-executable resolution.

Defect found live at the v1.1 boot-core activation (2026-11-08):
under the session-0 core running as SYSTEM, every PowerShell job
failed at spawn -- ``[WinError 1920] The file cannot be accessed by
the system`` -- while cmd jobs under the same core worked. The
agent resolved the PowerShell executable with a bare-name
``shutil.which()`` over the process PATH, and in the boot-task
environment that search returns the per-user WindowsApps execution
alias for powershell.exe: a reparse stub inside the interactive
user's profile that no other account (SYSTEM included) can execute.
cmd survived only because it was passed bare and Windows' own
CreateProcess search order found System32\\cmd.exe.

The SYSTEM/session-0 context cannot be reproduced in this suite, so
these tests pin the resolution seam's contract with injected
env/which/exists: the resolver returns absolute paths that exist,
prefers the fixed System32 locations, and can never return a
WindowsApps alias or a path inside a user profile.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import bridge_agent  # noqa: E402

SYSTEM_ROOT = r"C:\Windows"
PS_SYSTEM32 = SYSTEM_ROOT + r"\System32\WindowsPowerShell\v1.0\powershell.exe"
CMD_SYSTEM32 = SYSTEM_ROOT + r"\System32\cmd.exe"
ALIAS_PS = r"C:\Users\Adam\AppData\Local\Microsoft\WindowsApps\powershell.exe"
ALIAS_PWSH = r"C:\Users\Adam\AppData\Local\Microsoft\WindowsApps\pwsh.exe"
REAL_PWSH = r"C:\Program Files\PowerShell\7\pwsh.exe"

ENV = {
    "SystemRoot": SYSTEM_ROOT,
    "USERPROFILE": r"C:\Users\Adam",
    "LOCALAPPDATA": r"C:\Users\Adam\AppData\Local",
    "APPDATA": r"C:\Users\Adam\AppData\Roaming",
}


def resolve(shell, which_map, existing):
    """Run the Windows resolver seam with fully fake inputs."""
    return bridge_agent._resolve_windows_shell_exe(
        shell, ENV, lambda name: which_map.get(name),
        lambda path: path in existing)


class WindowsShellResolutionTests(unittest.TestCase):
    """Contract of _resolve_windows_shell_exe (pure seam)."""

    def test_path_alias_loses_to_system32_powershell(self):
        # The activation defect itself: PATH resolution hands back
        # the WindowsApps alias; System32 powershell.exe exists and
        # must win.
        got = resolve("powershell",
                      {"powershell": ALIAS_PS},
                      {PS_SYSTEM32})
        self.assertEqual(got, PS_SYSTEM32)

    def test_alias_is_never_returned_even_when_system32_missing(self):
        # Nothing "exists": the fallback is still the canonical
        # System32 path, never the alias and never a bare name.
        got = resolve("powershell",
                      {"powershell": ALIAS_PS, "pwsh": ALIAS_PWSH},
                      set())
        self.assertEqual(got, PS_SYSTEM32)

    def test_real_pwsh_install_keeps_its_preference(self):
        # Behaviour in a normal user session is unchanged: a real
        # pwsh install (Program Files) still beats powershell.
        got = resolve("powershell",
                      {"pwsh": REAL_PWSH, "powershell": PS_SYSTEM32},
                      {REAL_PWSH, PS_SYSTEM32})
        self.assertEqual(got, REAL_PWSH)

    def test_profile_pwsh_is_rejected(self):
        profile_pwsh = r"C:\Users\Adam\AppData\Local\Programs\pwsh.exe"
        got = resolve("powershell",
                      {"pwsh": profile_pwsh},
                      {profile_pwsh, PS_SYSTEM32})
        self.assertEqual(got, PS_SYSTEM32)

    def test_cmd_resolves_to_system32(self):
        got = resolve("cmd", {"cmd": ALIAS_PS}, {CMD_SYSTEM32})
        self.assertEqual(got, CMD_SYSTEM32)

    def test_cmd_missing_everywhere_still_absolute_system32(self):
        got = resolve("cmd", {}, set())
        self.assertEqual(got, CMD_SYSTEM32)
        self.assertTrue(got[1:3] == ":\\")

    def test_pwsh_returns_none_when_only_an_alias_exists(self):
        got = resolve("pwsh", {"pwsh": ALIAS_PWSH}, {ALIAS_PWSH})
        self.assertIsNone(got)

    def test_bare_or_relative_which_results_are_rejected(self):
        got = resolve("powershell",
                      {"powershell": "powershell.exe"},
                      {"powershell.exe", PS_SYSTEM32})
        self.assertEqual(got, PS_SYSTEM32)

    def test_results_are_never_under_windowsapps_or_a_profile(self):
        scenarios = [
            ({"powershell": ALIAS_PS, "pwsh": ALIAS_PWSH}, set()),
            ({"powershell": ALIAS_PS}, {ALIAS_PS, PS_SYSTEM32}),
            ({"pwsh": ALIAS_PWSH}, {ALIAS_PWSH}),
            ({"cmd": ALIAS_PS}, {ALIAS_PS}),
        ]
        for which_map, existing in scenarios:
            for shell in ("powershell", "cmd"):
                got = resolve(shell, which_map, existing)
                self.assertIsNotNone(got)
                norm = got.replace("/", "\\").lower()
                self.assertNotIn("\\windowsapps\\", norm)
                self.assertFalse(
                    norm.startswith(r"c:\users\adam\\".replace("\\\\", "\\")),
                    f"{shell} resolved inside the user profile: {got}")


class BuildCommandSeamTests(unittest.TestCase):
    """build_command under a simulated Windows/SYSTEM environment.

    This is the behavioural regression for the activation defect:
    with PATH lookup returning the WindowsApps alias, the argv the
    agent builds for a PowerShell job must still start with the
    System32 executable.
    """

    def _patched_argv(self, builder, *args):
        def fake_which(name):
            return {"powershell": ALIAS_PS, "pwsh": ALIAS_PWSH}.get(name)

        def fake_exists(path):
            return path in (PS_SYSTEM32, CMD_SYSTEM32)

        with mock.patch.object(bridge_agent, "IS_WINDOWS", True), \
                mock.patch.object(bridge_agent.shutil, "which", fake_which), \
                mock.patch.object(os.path, "exists", fake_exists), \
                mock.patch.dict(os.environ, ENV):
            return builder(*args)

    def test_powershell_job_argv_uses_system32_not_the_alias(self):
        argv = self._patched_argv(bridge_agent.build_command,
                                  "powershell", "Get-Date")
        self.assertEqual(argv[0], PS_SYSTEM32)
        self.assertEqual(argv[1:], ["-NoProfile", "-NonInteractive",
                                    "-Command", "Get-Date"])

    def test_interactive_powershell_argv_uses_system32(self):
        argv = self._patched_argv(bridge_agent.shell_argv, "powershell")
        self.assertEqual(argv[0], PS_SYSTEM32)

    def test_cmd_job_argv_uses_system32(self):
        argv = self._patched_argv(bridge_agent.build_command,
                                  "cmd", "ver")
        self.assertEqual(argv[0], CMD_SYSTEM32)
        self.assertEqual(argv[1:], ["/d", "/s", "/c", "ver"])


@unittest.skipIf(bridge_agent.IS_WINDOWS, "POSIX dev-machine behaviour")
class PosixBehaviourUnchangedTests(unittest.TestCase):
    def test_posix_shell_still_bin_sh(self):
        self.assertEqual(bridge_agent.build_command("posix", "true"),
                         ["/bin/sh", "-c", "true"])
        self.assertEqual(bridge_agent.resolve_shell_exe("posix"), "/bin/sh")


if __name__ == "__main__":
    unittest.main()
