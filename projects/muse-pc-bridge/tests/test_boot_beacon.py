"""Boot beacon tests (durable job runner release).

Fresh-boot detection is driven by the machine boot time seam:
same boot time across two starts = agent restart (fresh_boot
False); a different boot time = a real reboot (fresh_boot True).
The boot time source is monkeypatched; everything else is the
real file code against a temp state dir.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import boot_beacon  # noqa: E402

BOOT_A = 1_700_000_000.0
BOOT_B = 1_700_100_000.0


class BootBeaconTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.tmp.name)
        self._orig = boot_beacon.system_boot_time
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(
            setattr, boot_beacon, "system_boot_time", self._orig)

    def _log(self) -> list[dict]:
        path = self.state_dir / "boot-log.jsonl"
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines()]

    def test_first_start_unknown_previous_counts_fresh(self):
        boot_beacon.system_boot_time = lambda: BOOT_A
        entry = boot_beacon.note_boot(self.state_dir, "supervisor")
        self.assertTrue(entry["fresh_boot"])
        self.assertEqual(entry["boot_time"], BOOT_A)
        self.assertEqual(entry["event"], "supervisor_start")
        self.assertEqual(entry["source"], "supervisor")

    def test_same_boot_restart_is_not_fresh(self):
        boot_beacon.system_boot_time = lambda: BOOT_A
        boot_beacon.note_boot(self.state_dir, "supervisor")
        entry = boot_beacon.note_boot(self.state_dir, "agent")
        self.assertFalse(entry["fresh_boot"])

    def test_new_boot_time_is_fresh(self):
        boot_beacon.system_boot_time = lambda: BOOT_A
        boot_beacon.note_boot(self.state_dir, "supervisor")
        boot_beacon.system_boot_time = lambda: BOOT_B
        entry = boot_beacon.note_boot(self.state_dir, "supervisor")
        self.assertTrue(entry["fresh_boot"])
        entries = self._log()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]["boot_time"], BOOT_B)

    def test_unknown_boot_time_is_null_not_guessed(self):
        boot_beacon.system_boot_time = lambda: None
        entry = boot_beacon.note_boot(self.state_dir, "agent")
        self.assertIsNone(entry["fresh_boot"])
        self.assertIsNone(entry["boot_time"])

    def test_beacon_state_file_tracks_last_boot(self):
        boot_beacon.system_boot_time = lambda: BOOT_A
        boot_beacon.note_boot(self.state_dir, "supervisor")
        state = json.loads((self.state_dir / "boot-beacon.json")
                           .read_text(encoding="utf-8"))
        self.assertEqual(state["boot_time"], BOOT_A)

    def test_append_event_records_resumed_jobs(self):
        boot_beacon.system_boot_time = lambda: BOOT_A
        boot_beacon.note_boot(self.state_dir, "supervisor")
        entry = boot_beacon.append_event(
            self.state_dir, "jobs_resumed", resumed=["job-1"])
        self.assertEqual(entry["event"], "jobs_resumed")
        self.assertEqual(entry["resumed"], ["job-1"])
        self.assertFalse(entry["fresh_boot"])


if __name__ == "__main__":
    unittest.main()
