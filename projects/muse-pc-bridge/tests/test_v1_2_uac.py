"""V1.2 tests: UAC pre-flight surfacing (spec §1).

The static classifier is pure text heuristics — fully testable off
Windows, one positive and several negative cases per family. The
HTTP tests prove the wiring: the assessment is computed before
execution and rides on the response, and "require_no_uac": true
turns a likely assessment into a 409 that executes NOTHING (no job
is created). consent_pending comes from the v1.1 UAC monitor's
snapshot; here it is driven by a stub monitor on the core.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import bridge_agent  # noqa: E402

TOKEN = "dummy-token-for-v12-uac-tests"
ON_WINDOWS = sys.platform.startswith("win")
SHELL = "cmd" if ON_WINDOWS else "posix"


class ClassifierTests(unittest.TestCase):
    """Positive/negative cases per spec §1 heuristic family."""

    def assertLikely(self, text, family_part):
        likely, reasons = bridge_agent.uac_static_assessment(text)
        self.assertTrue(likely, f"expected likely for {text!r}: {reasons}")
        self.assertTrue(
            any(family_part in r for r in reasons),
            f"expected a reason mentioning {family_part!r} for {text!r}, "
            f"got {reasons}")

    def assertUnlikely(self, text):
        likely, reasons = bridge_agent.uac_static_assessment(text)
        self.assertFalse(likely, f"expected unlikely for {text!r}: {reasons}")
        self.assertEqual(reasons, [])

    # -- installers ------------------------------------------------------
    def test_msiexec(self):
        self.assertLikely(r"msiexec /i C:\dl\app.msi /quiet", "msiexec")
        self.assertLikely(r"msiexec.exe /x {GUID}", "msiexec")

    def test_setup_exe(self):
        self.assertLikely(r"C:\dl\setup.exe /S", "setup*.exe")
        self.assertLikely("setup64.exe", "setup*.exe")
        self.assertLikely("Setup-1.2.exe /quiet", "setup*.exe")

    def test_msi_package(self):
        self.assertLikely(r"Start-Process C:\dl\app.msi", ".msi")

    def test_installer_negatives(self):
        self.assertUnlikely("echo installing the app")
        self.assertUnlikely("notepad setup-notes.txt")
        self.assertUnlikely("copy setup.txt backup.txt")
        self.assertUnlikely("python install_deps.py")

    # -- elevation verbs ---------------------------------------------------
    def test_runas(self):
        self.assertLikely(
            "Start-Process powershell -Verb RunAs", "RunAs")
        self.assertLikely(
            'Start-Process "app.exe" -Verb "RunAs" -Wait', "RunAs")
        self.assertLikely("runas /user:Administrator cmd", "RunAs")

    def test_runas_negatives(self):
        self.assertUnlikely("Start-Process notepad.exe")
        self.assertUnlikely("Start-Process powershell -Verb Open")

    # -- protected locations -------------------------------------------------
    def test_hklm(self):
        self.assertLikely(
            r"reg add HKLM:\SOFTWARE\Acme /v X /d 1", "HKLM")
        self.assertLikely(
            r"New-ItemProperty -Path 'HKLM:\SOFTWARE\Acme'", "HKLM")
        self.assertLikely(
            r"reg add HKEY_LOCAL_MACHINE\SOFTWARE\Acme", "HKLM")

    def test_hkcu_is_not_flagged(self):
        self.assertUnlikely(r"reg add HKCU:\SOFTWARE\Acme /v X /d 1")

    def test_system_locations(self):
        self.assertLikely(
            r"copy app.exe " + '"C:\\Program Files\\Acme\\"', "Program Files")
        self.assertLikely(
            r"echo x > %SystemRoot%\Temp\marker.txt", "Program Files")
        self.assertLikely(r"dir %ProgramFiles%", "Program Files")

    def test_system_location_negatives(self):
        self.assertUnlikely(r"dir C:\Users\adamw\Downloads")
        self.assertUnlikely("echo x > %USERPROFILE%\\marker.txt")
        self.assertUnlikely("echo x > %TEMP%\\marker.txt")

    # -- services ------------------------------------------------------------
    def test_net_service_control(self):
        self.assertLikely("net stop Spooler", "net start/stop")
        self.assertLikely("net start MyService", "net start/stop")

    def test_sc_service_control(self):
        self.assertLikely("sc config MyService start= auto", "sc config")
        self.assertLikely("sc create MyService binPath= C:\\svc.exe",
                          "sc config")

    def test_service_negatives(self):
        self.assertUnlikely("net use Z: \\\\server\\share")
        self.assertUnlikely("net view")
        self.assertUnlikely("sc query Spooler")
        self.assertUnlikely("sc start Spooler")  # spec lists config/create

    # -- execution policy ------------------------------------------------------
    def test_execution_policy_machine_scope(self):
        self.assertLikely(
            "Set-ExecutionPolicy -Scope LocalMachine RemoteSigned",
            "Set-ExecutionPolicy")

    def test_execution_policy_negatives(self):
        self.assertUnlikely(
            "Set-ExecutionPolicy -Scope CurrentUser RemoteSigned")
        self.assertUnlikely("Set-ExecutionPolicy Bypass -Force")
        self.assertUnlikely("Get-ExecutionPolicy -Scope LocalMachine")

    # -- system servicing --------------------------------------------------------
    def test_servicing_tools(self):
        self.assertLikely("DISM /Online /Cleanup-Image /RestoreHealth",
                          "dism/sfc/bcdedit")
        self.assertLikely("sfc /scannow", "dism/sfc/bcdedit")
        self.assertLikely("bcdedit /set {current} nx AlwaysOn",
                          "dism/sfc/bcdedit")

    def test_servicing_negatives(self):
        self.assertUnlikely("echo disinfect the workspace")
        self.assertUnlikely("dir dism-notes")

    # -- scheduled tasks -----------------------------------------------------------
    def test_schtasks_system(self):
        self.assertLikely(
            'schtasks /create /tn "Job" /tr "C:\\job.cmd" /sc daily '
            '/RU SYSTEM', "SYSTEM")

    def test_schtasks_negatives(self):
        self.assertUnlikely(
            'schtasks /create /tn "Job" /tr "C:\\job.cmd" /sc daily')
        self.assertUnlikely('schtasks /run /tn "Job"')
        self.assertUnlikely('schtasks /create /tn "J" /ru adamw /tr x')

    # -- drivers ---------------------------------------------------------------------
    def test_pnputil_add_driver(self):
        self.assertLikely(r"pnputil /add-driver C:\drv\net.inf /install",
                          "pnputil")

    def test_pnputil_negatives(self):
        self.assertUnlikely("pnputil /enum-drivers")
        self.assertUnlikely("pnputil /delete-driver oem1.inf")

    # -- benign commands ----------------------------------------------------------------
    def test_benign(self):
        self.assertUnlikely("echo hello")
        self.assertUnlikely("Get-ChildItem -Recurse | Select-Object Name")
        self.assertUnlikely("git status")
        self.assertUnlikely("")

    def test_multiple_reasons_accumulate(self):
        likely, reasons = bridge_agent.uac_static_assessment(
            r"msiexec /i app.msi && net stop Spooler")
        self.assertTrue(likely)
        self.assertGreaterEqual(len(reasons), 3)  # msiexec, .msi, net stop


class AssessUacTests(unittest.TestCase):
    def test_consent_pending_comes_from_monitor(self):
        core = types.SimpleNamespace(
            uac=types.SimpleNamespace(
                snapshot=lambda: {"active": True, "since": None}))
        obj = bridge_agent.assess_uac(core, "echo hello")
        self.assertEqual(obj, {"likely": False, "reasons": [],
                               "consent_pending": True})

    def test_consent_inactive(self):
        core = types.SimpleNamespace(
            uac=types.SimpleNamespace(
                snapshot=lambda: {"active": False, "since": None}))
        obj = bridge_agent.assess_uac(core, "echo hello")
        self.assertFalse(obj["consent_pending"])
        self.assertFalse(obj["likely"])


class PreflightHttpTests(unittest.TestCase):
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
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

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

    def request(self, method, path, payload=None):
        headers = {"Authorization": f"Bearer {TOKEN}"}
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

    def job_count(self):
        status, obj = self.request("GET", "/v1/jobs")
        self.assertEqual(status, 200)
        return len(obj["jobs"])

    # A harmless command whose TEXT trips the classifier: an echo of
    # the words. If it runs, it exits 0 and prints them; if the
    # pre-flight refuses it, nothing runs at all.
    LIKELY_BUT_HARMLESS = "echo msiexec /i setup.msi"

    def test_assessment_rides_on_exec_response(self):
        status, obj = self.request("POST", "/v1/exec", {
            "command": "echo hello", "shell": SHELL})
        self.assertEqual(status, 202)
        self.assertEqual(obj["uac"], {"likely": False, "reasons": [],
                                      "consent_pending": False})

    def test_likely_executes_by_default_and_reports(self):
        status, obj = self.request("POST", "/v1/exec", {
            "command": self.LIKELY_BUT_HARMLESS, "shell": SHELL,
            "wait_s": 10})
        self.assertEqual(status, 200)
        self.assertEqual(obj["state"], "done")
        self.assertTrue(obj["uac"]["likely"])
        self.assertTrue(obj["uac"]["reasons"])

    def test_require_no_uac_refuses_and_executes_nothing(self):
        before = self.job_count()
        status, obj = self.request("POST", "/v1/exec", {
            "command": self.LIKELY_BUT_HARMLESS, "shell": SHELL,
            "require_no_uac": True, "wait_s": 10})
        self.assertEqual(status, 409)
        self.assertEqual(obj["error"], "uac_likely")
        self.assertTrue(obj["uac"]["likely"])
        self.assertIn("reasons", obj["uac"])
        self.assertIn("consent_pending", obj["uac"])
        # No job was created — nothing executed, nothing to poll.
        self.assertEqual(self.job_count(), before)
        # And the refusal is in the audit log as a 409 request.
        status, audit = self.request("GET", "/v1/audit?limit=1000")
        refusals = [e for e in audit["entries"]
                    if e.get("status") == 409
                    and "UAC likely" in str(e.get("summary", ""))]
        self.assertTrue(refusals)

    def test_require_no_uac_allows_benign(self):
        status, obj = self.request("POST", "/v1/exec", {
            "command": "echo hello", "shell": SHELL,
            "require_no_uac": True, "wait_s": 10})
        self.assertEqual(status, 200)
        self.assertEqual(obj["state"], "done")
        self.assertFalse(obj["uac"]["likely"])


if __name__ == "__main__":
    unittest.main()
