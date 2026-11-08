"""Unit tests for agent/display_state.py — pure signal-to-display mapping.

Synthetic inputs only; no agent, supervisor, files, or network involved.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))

import display_state  # noqa: E402

NOW = 1_000_000.0


def agent(**kw):
    base = {"version": "1.0.0", "jobs_running": 0, "sessions_open": 0,
            "processes_alive": 0}
    base.update(kw)
    return base


def update(staged=None, result=None, current=None):
    return {"staged": staged, "last_result": result,
            "current_update": current}


class DisplayStateTests(unittest.TestCase):
    def resolve(self, sup=None, agt=None, upd=None, **kw):
        kw.setdefault("now", NOW)
        return display_state.resolve_display(
            sup if sup is not None else {"state": "running"},
            agt, upd if upd is not None else update(), **kw)

    def test_idle_when_reachable_and_quiet(self):
        v = self.resolve(agt=agent())
        self.assertEqual((v["state"], v["art"]), ("idle", "idle"))

    def test_working_when_job_running(self):
        v = self.resolve(agt=agent(jobs_running=2))
        self.assertEqual(v["state"], "working")

    def test_working_when_process_alive(self):
        v = self.resolve(agt=agent(processes_alive=1))
        self.assertEqual(v["state"], "working")

    def test_session_outranks_working(self):
        v = self.resolve(agt=agent(sessions_open=1, jobs_running=3))
        self.assertEqual(v["state"], "session")

    def test_staged_update_shows_connecting(self):
        v = self.resolve(agt=agent(), upd=update(staged={"version": "1.0.1"}))
        self.assertEqual((v["state"], v["label"]),
                         ("connecting", "Update staged"))

    def test_fresh_applied_ok_celebrates(self):
        v = self.resolve(agt=agent(),
                         upd=update(result={"outcome": "applied_ok",
                                            "at": NOW - 5}))
        self.assertEqual(v["state"], "celebrate")

    def test_stale_applied_ok_falls_back_to_idle(self):
        v = self.resolve(agt=agent(),
                         upd=update(result={"outcome": "applied_ok",
                                            "at": NOW - 3600}))
        self.assertEqual(v["state"], "idle")

    def test_apply_failed_is_alert(self):
        v = self.resolve(agt=agent(),
                         upd=update(result={"outcome": "apply_failed",
                                            "at": NOW - 5}))
        self.assertEqual(v["state"], "alert")

    def test_fresh_rollback_is_alert(self):
        v = self.resolve(agt=agent(),
                         upd=update(result={"rolled_back_version": "1.0.2",
                                            "at": NOW - 5}))
        self.assertEqual(v["state"], "alert")

    def test_supervisor_failure_state_is_alert(self):
        v = self.resolve(sup={"state": "update_apply_failed"}, agt=agent())
        self.assertEqual(v["state"], "alert")

    def test_unreachable_during_restart_is_connecting(self):
        v = self.resolve(sup={"state": "restarting"}, agt=None,
                         down_since=NOW - 3)
        self.assertEqual(v["state"], "connecting")

    def test_unreachable_too_long_is_alert(self):
        v = self.resolve(sup={"state": "running"}, agt=None,
                         down_since=NOW - 60)
        self.assertEqual(v["state"], "alert")

    def test_unreachable_briefly_is_connecting_not_alert(self):
        v = self.resolve(sup={"state": "running"}, agt=None,
                         down_since=NOW - 2)
        self.assertEqual(v["state"], "connecting")

    def test_alert_outranks_working(self):
        v = self.resolve(agt=agent(jobs_running=5),
                         upd=update(result={"outcome": "rollback_failed",
                                            "at": NOW - 5}))
        self.assertEqual(v["state"], "alert")


if __name__ == "__main__":
    unittest.main()
