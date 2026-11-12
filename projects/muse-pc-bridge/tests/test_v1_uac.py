"""V1.1 tests: UAC consent-prompt detection and signalling.

The Windows probe (Toolhelp32 scan for consent.exe) cannot run on
this machine — it is Windows-only and PC-verification pending (see
docs/TEST_PLAN.md). What IS proven here, with the probe stubbed:
the monitor's transition logic, the audit events on appear/clear,
the /v1/status field, and that the real probe reports inactive off
Windows.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import bridge_agent  # noqa: E402

TOKEN = "test-token-v11-uac"
ON_WINDOWS = sys.platform.startswith("win")


def make_core(root: Path) -> bridge_agent.BridgeCore:
    cfg = dict(bridge_agent.DEFAULT_CONFIG)
    cfg.update({
        "host": "127.0.0.1", "port": 0, "token": TOKEN,
        "allowed_file_root": str(root / "bridge-files"),
        "audit_log": str(root / "logs" / "audit.jsonl"),
        "state_dir": str(root / "state"),
    })
    return bridge_agent.BridgeCore(cfg)


def audit_events(core: bridge_agent.BridgeCore) -> list[dict]:
    try:
        lines = core.audit_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [json.loads(ln) for ln in lines if ln.strip()]


class MonitorTransitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = make_core(Path(self.tmp.name))
        self.reading = {"active": False}
        self.monitor = bridge_agent.UacMonitor(
            self.core, probe=lambda: self.reading["active"])
        # The core's own monitor would also see cfg's default real
        # probe; these tests drive only the injected one.

    def tearDown(self):
        self.tmp.cleanup()

    def test_appear_and_clear_transitions(self):
        m = self.monitor
        self.assertEqual(m.snapshot(), {"active": False, "since": None})
        self.assertFalse(m.check_once(now=1000.0))
        self.reading["active"] = True
        self.assertTrue(m.check_once(now=1005.0))
        snap = m.snapshot()
        self.assertTrue(snap["active"])
        self.assertTrue(snap["since"].startswith("1970-01-01T00:16:45"))
        # Steady state: no duplicate transition, since is stable.
        self.assertTrue(m.check_once(now=1009.0))
        self.assertEqual(m.snapshot()["since"], snap["since"])
        self.reading["active"] = False
        self.assertFalse(m.check_once(now=1012.0))
        self.assertEqual(m.snapshot(), {"active": False, "since": None})

    def test_transitions_are_audited_once_each(self):
        m = self.monitor
        self.reading["active"] = True
        m.check_once(now=2000.0)
        m.check_once(now=2001.0)          # steady: no second event
        self.reading["active"] = False
        m.check_once(now=2007.0)
        events = [e for e in audit_events(self.core)
                  if e.get("event", "").startswith("uac_prompt")]
        self.assertEqual([e["event"] for e in events],
                         ["uac_prompt_shown", "uac_prompt_cleared"])
        self.assertIn("after 7s", events[1]["summary"])
        for e in events:  # nothing about any credential, ever
            self.assertNotIn("password", json.dumps(e).lower())
            self.assertNotIn("credential", json.dumps(e).lower())

    def test_failing_probe_reads_as_no_prompt(self):
        def boom():
            raise RuntimeError("probe exploded")
        m = bridge_agent.UacMonitor(self.core, probe=boom)
        self.assertFalse(m.check_once(now=1.0))
        self.assertEqual(m.snapshot(), {"active": False, "since": None})

    def test_poll_interval_config_is_sane(self):
        core = self.core
        core.cfg["uac_poll_interval_s"] = "junk"
        m = bridge_agent.UacMonitor(core, probe=lambda: False)
        self.assertEqual(m._poll_s, 2.0)
        core.cfg["uac_poll_interval_s"] = 0.01
        m = bridge_agent.UacMonitor(core, probe=lambda: False)
        self.assertGreaterEqual(m._poll_s, 0.5)


class ProbeTests(unittest.TestCase):
    @unittest.skipIf(ON_WINDOWS, "off-Windows behaviour only")
    def test_real_probe_is_inactive_off_windows(self):
        self.assertFalse(bridge_agent.consent_prompt_active())


class StatusFieldTests(unittest.TestCase):
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
        })
        cls.server = bridge_agent.create_server(cfg)
        cls.core = cls.server.core
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def get_status(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/status",
            headers={"Authorization": f"Bearer {TOKEN}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_status_reports_uac_inactive_by_default(self):
        obj = self.get_status()
        self.assertEqual(obj["uac_prompt"],
                         {"active": False, "since": None})

    def test_status_reflects_monitor_transitions(self):
        # Swap the core monitor's probe for a stub and drive it the
        # way the poll thread would on Windows.
        self.core.uac._probe = lambda: True
        try:
            self.core.uac.check_once(now=3000.0)
            obj = self.get_status()
            self.assertTrue(obj["uac_prompt"]["active"])
            self.assertIsNotNone(obj["uac_prompt"]["since"])
        finally:
            self.core.uac._probe = lambda: False
            self.core.uac.check_once(now=3001.0)
        obj = self.get_status()
        self.assertEqual(obj["uac_prompt"],
                         {"active": False, "since": None})


if __name__ == "__main__":
    unittest.main()
