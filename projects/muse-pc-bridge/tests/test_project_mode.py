"""Project Mode tests (durable job runner release).

The engage/disengage state machine runs against a FakeOps seam:
an in-memory process table, power plan, and service. Proven:
engage records exactly what it changed; disengage restores
exactly that recorded state (power-plan GUID, relaunched exe
paths, service restart only if engage stopped it); unlisted
processes are never touched; a process that refuses a graceful
close is left running and reported (never force-killed — the
Ops API has no force operation at all); a step that needs
elevation degrades to `skipped` without failing the toggle;
the presence auto-disengage decision is pure and tested
directly, and the monitor fires it end to end.

Windows operations themselves are NOT proven here — they sit
behind the seam and are verified on the owner's PC.
"""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import project_mode  # noqa: E402

BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
HIGH_PERF = project_mode.HIGH_PERFORMANCE_GUID


class FakeOps(project_mode.Ops):
    def __init__(self):
        self.processes: list[dict] = []
        self.stubborn: set[int] = set()
        self.power_plan: str | None = BALANCED
        self.service: str | None = "running"
        self.launched: list[str] = []
        self.service_starts = 0
        self.service_stops = 0
        self.stop_service_result = (True, "stopped")

    def add(self, name: str, pid: int, exe: str | None = None):
        self.processes.append(
            {"name": name, "pid": pid, "exe": exe or f"C:\\x\\{name}"})

    def names(self) -> list[str]:
        return [p["name"] for p in self.processes]

    def list_processes(self):
        return [dict(p) for p in self.processes]

    def close_process_graceful(self, pid, grace_s):
        if pid in self.stubborn:
            return False, "still running after grace"
        self.processes = [p for p in self.processes
                          if p["pid"] != pid]
        return True, "WM_CLOSE"

    def launch(self, exe):
        self.launched.append(exe)
        return True, "launched"

    def active_power_plan(self):
        return self.power_plan

    def set_power_plan(self, guid):
        self.power_plan = guid
        return True, "scheme set"

    def service_state(self, name):
        return self.service

    def stop_service(self, name):
        ok, detail = self.stop_service_result
        if ok:
            self.service = "stopped"
            self.service_stops += 1
        return ok, detail

    def start_service(self, name):
        self.service = "running"
        self.service_starts += 1
        return True, "started"


class ProjectModeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.ops = FakeOps()
        self.ops.add("Lively.exe", 10)
        self.ops.add("steamwebhelper.exe", 11)
        self.ops.add("chrome.exe", 12)        # NOT on the list
        self.ops.add("OneDrive.exe", 13)
        self.ops.add("explorer.exe", 14)

    def engage(self, **kw):
        return project_mode.engage(self.state_dir, ops=self.ops,
                                   **kw)

    def steps(self, record, key="engage_steps"):
        return {s["step"]: s["status"] for s in record[key]}


class EngageDisengageTest(ProjectModeCase):
    def test_engage_records_and_applies(self):
        record = self.engage()
        self.assertTrue(record["engaged"])
        self.assertEqual(self.ops.power_plan, HIGH_PERF)
        self.assertEqual(record["previous_power_plan"], BALANCED)
        # Lively + listed helper + OneDrive closed; chrome and
        # explorer (unlisted) untouched.
        self.assertEqual(sorted(self.ops.names()),
                         ["chrome.exe", "explorer.exe"])
        self.assertEqual(self.ops.service, "stopped")
        statuses = self.steps(record)
        for step in ("power_plan", "lively", "close_list",
                     "onedrive", "search_indexing"):
            self.assertEqual(statuses[step], "applied", step)
        closed = {c["name"] for c in record["closed_processes"]}
        self.assertEqual(closed,
                         {"Lively.exe", "steamwebhelper.exe"})
        state = project_mode.status(self.state_dir)
        self.assertTrue(state["engaged"])

    def test_disengage_restores_exactly_the_record(self):
        self.engage()
        record = project_mode.disengage(self.state_dir,
                                        ops=self.ops)
        self.assertFalse(record["engaged"])
        self.assertEqual(self.ops.power_plan, BALANCED)
        self.assertEqual(self.ops.service, "running")
        self.assertEqual(self.ops.service_starts, 1)
        relaunched = set(self.ops.launched)
        self.assertEqual(relaunched, {
            "C:\\x\\Lively.exe", "C:\\x\\steamwebhelper.exe",
            "C:\\x\\OneDrive.exe"})
        # Nothing unlisted was ever launched or closed.
        self.assertNotIn("C:\\x\\chrome.exe", relaunched)

    def test_engage_twice_is_a_noop(self):
        self.engage()
        again = self.engage()
        self.assertEqual(again.get("note"), "already engaged")
        self.assertEqual(self.ops.service_stops, 1)

    def test_disengage_when_not_engaged(self):
        out = project_mode.disengage(self.state_dir, ops=self.ops)
        self.assertFalse(out["engaged"])
        self.assertEqual(self.ops.launched, [])


class DegradationTest(ProjectModeCase):
    def test_service_needing_elevation_degrades(self):
        self.ops.stop_service_result = (
            False, "needs elevation (access denied)")
        record = self.engage()
        self.assertTrue(record["engaged"])  # toggle still succeeds
        self.assertEqual(self.steps(record)["search_indexing"],
                         "skipped")
        self.assertFalse(record["wsearch"]["stopped_by_us"])
        project_mode.disengage(self.state_dir, ops=self.ops)
        # Never stopped by us -> never "restored".
        self.assertEqual(self.ops.service_starts, 0)

    def test_stubborn_process_left_running_never_forced(self):
        self.ops.stubborn = {11}  # steamwebhelper refuses to close
        record = self.engage()
        self.assertTrue(record["engaged"])
        self.assertIn("steamwebhelper.exe", self.ops.names())
        self.assertEqual(self.steps(record)["close_list"], "failed")
        closed = {c["name"] for c in record["closed_processes"]}
        self.assertNotIn("steamwebhelper.exe", closed)
        project_mode.disengage(self.state_dir, ops=self.ops)
        self.assertNotIn("C:\\x\\steamwebhelper.exe",
                         self.ops.launched)

    def test_nothing_running_is_not_applicable(self):
        self.ops.processes = [p for p in self.ops.processes
                              if p["name"] == "explorer.exe"]
        record = self.engage()
        statuses = self.steps(record)
        self.assertEqual(statuses["lively"], "not_applicable")
        self.assertEqual(statuses["close_list"], "not_applicable")
        self.assertEqual(statuses["onedrive"], "not_applicable")


class PureLogicTest(unittest.TestCase):
    def test_close_candidates_exact_list_only(self):
        procs = [{"name": "steamwebhelper.exe", "pid": 1},
                 {"name": "SteamWebHelper.exe", "pid": 2},
                 {"name": "chrome.exe", "pid": 3}]
        out = project_mode.close_candidates(
            procs, ["steamwebhelper.exe"])
        self.assertEqual([p["pid"] for p in out], [1, 2])

    def test_parse_active_scheme(self):
        text = ("Power Scheme GUID: 381b4222-f694-41f0-9685-"
                "ff5bb260df2e  (Balanced)")
        self.assertEqual(project_mode.parse_active_scheme(text),
                         BALANCED)
        self.assertIsNone(project_mode.parse_active_scheme("junk"))

    def test_parse_service_state(self):
        self.assertEqual(project_mode.parse_service_state(
            "        STATE              : 4  RUNNING"), "running")
        self.assertEqual(project_mode.parse_service_state(
            "        STATE              : 1  STOPPED"), "stopped")
        self.assertIsNone(project_mode.parse_service_state("junk"))

    def test_auto_disengage_decisions(self):
        gaming = {"gaming": True, "games": ["Wow.exe"],
                  "input_idle_s": 900.0}
        calm = {"gaming": False, "games": [], "input_idle_s": 900.0}
        # Settle window: even a game cannot disengage instantly
        # (the owner's own engage click is fresh input).
        self.assertIsNone(
            project_mode.auto_disengage_reason(gaming, 900.0, 5.0))
        self.assertEqual(
            project_mode.auto_disengage_reason(gaming, 900.0, 60.0),
            "game launched: Wow.exe")
        self.assertIsNone(
            project_mode.auto_disengage_reason(calm, 900.0, 60.0))
        # Idle DROPPING between polls = fresh input.
        active = {"gaming": False, "games": [], "input_idle_s": 2.0}
        self.assertEqual(
            project_mode.auto_disengage_reason(active, 900.0, 60.0),
            "fresh user input")
        # Idle growing = nobody home.
        self.assertIsNone(project_mode.auto_disengage_reason(
            calm, 800.0, 60.0))
        # No idle reading = no input conclusion.
        blind = {"gaming": False, "games": [], "input_idle_s": None}
        self.assertIsNone(
            project_mode.auto_disengage_reason(blind, None, 60.0))


class MonitorTest(ProjectModeCase):
    def test_monitor_disengages_on_game_launch(self):
        self.engage()

        class StubCore:
            def __init__(self, state_dir):
                self.state_dir = state_dir
                self.cfg = {}
                self.audits = []

            def audit(self, entry):
                self.audits.append(entry)

        core = StubCore(self.state_dir)
        monitor = project_mode.ProjectModeMonitor(
            core, poll_s=1.0,
            snapshot_fn=lambda: {"gaming": True,
                                 "games": ["Wow.exe"],
                                 "input_idle_s": 900.0})
        monitor._engaged_since = time.monotonic() - 120
        reason = monitor.check_once()
        self.assertEqual(reason, "game launched: Wow.exe")
        self.assertFalse(project_mode.is_engaged(self.state_dir))


if __name__ == "__main__":
    unittest.main()
