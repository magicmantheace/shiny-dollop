"""Stream-monitor regression: causality, restarts, corruption, and safety."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from developmental_ai.online_dynamics import ModelBank, fit, trajectory
from developmental_ai.continuous_dynamics import StreamMonitor, catalogue


class StreamMonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.models = Path(self.tmp.name) / "models.db"
        self.state = Path(self.tmp.name) / "stream.db"
        seed = 17
        with ModelBank(self.models, seed) as bank:
            normal, _ = fit([trajectory(seed, "train", i) for i in range(75)], iterations=5)
            high, _ = fit([trajectory(seed, "train", i, "high", "shifted") for i in range(75)], iterations=5)
            bank.save("original", normal, 75)
            bank.save("changed", high, 75)

    def run_stream(self, schedules, monitor=None):
        events = []
        if monitor is None:
            with ModelBank(self.models, 17) as bank, StreamMonitor(self.state, bank) as monitor:
                return self.run_stream(schedules, monitor)
        for i, condition in schedules:
            h = trajectory(17, "test", 6000+i, *condition)
            events.append(monitor.observe(h))
        return events

    def test_switch_and_recover_original_without_regime_labels(self):
        schedule = ([(i, ("standard", "fixed")) for i in range(22)]
                    + [(i, ("high", "shifted")) for i in range(22, 48)]
                    + [(i, ("standard", "fixed")) for i in range(48, 74)])
        events = self.run_stream(schedule)
        self.assertEqual(events[20]["selected"], "original")
        self.assertEqual(events[45]["selected"], "changed")
        self.assertEqual(events[-1]["selected"], "original")
        self.assertTrue(all(set(e) == {"schema", "seq", "selected", "status", "candidate", "scores", "window_size", "scope", "previous_event_digest"} for e in events))
        self.assertTrue(all(e["scope"] == "simulation-only" for e in events))
        with ModelBank(self.models, 17) as bank, StreamMonitor(self.state, bank) as monitor:
            self.assertEqual(monitor.events(), events)

    def test_restart_is_event_and_state_exact(self):
        histories = [(i, ("standard", "fixed") if i < 15 else ("high", "shifted")) for i in range(30)]
        first = self.run_stream(histories[:17])
        rest = self.run_stream(histories[17:])
        with ModelBank(self.models, 17) as bank, StreamMonitor(self.state, bank) as monitor:
            combined = monitor.events()
        self.assertEqual(first+rest, combined)
        alt = Path(self.tmp.name) / "unbroken.db"
        with ModelBank(self.models, 17) as bank, StreamMonitor(alt, bank) as monitor:
            other = self.run_stream(histories, monitor)
        self.assertEqual(combined, other)

    def test_invalid_history_rejected_without_database_mutation(self):
        with ModelBank(self.models, 17) as bank, StreamMonitor(self.state, bank) as monitor:
            before = monitor.state.copy()
            bad = trajectory(17, "test", 6000)
            bad["actual_regime"] = "high"
            with self.assertRaises(ValueError):
                monitor.observe(bad)
            self.assertEqual(before, monitor.state)
            self.assertEqual(monitor.events(), [])

    def test_binding_mismatch_and_tamper_fail_closed(self):
        self.run_stream([(0, ("standard", "fixed"))])
        with ModelBank(self.models, 17) as bank:
            with self.assertRaises(ValueError):
                StreamMonitor(self.state, bank, window=6)
        with ModelBank(self.models, 17) as bank:
            bank.save("extra", bank.get("original"), 1)
            with self.assertRaises(ValueError):
                StreamMonitor(self.state, bank)
        with sqlite3.connect(self.state) as conn:
            conn.execute("UPDATE continuous_state SET body='{}' WHERE id=1")
        with ModelBank(self.models, 17) as bank:
            with self.assertRaises(ValueError):
                StreamMonitor(self.state, bank)

    def test_event_tampering_is_detected(self):
        self.run_stream([(0, ("standard", "fixed"))])
        with sqlite3.connect(self.state) as conn:
            conn.execute("UPDATE continuous_events SET body='{}' WHERE seq=1")
        with ModelBank(self.models, 17) as bank:
            with self.assertRaises(ValueError):
                StreamMonitor(self.state, bank)

    def test_missing_entire_event_history_is_detected(self):
        self.run_stream([(0, ("standard", "fixed"))])
        with ModelBank(self.models, 17) as bank, StreamMonitor(self.state, bank) as monitor:
            monitor.conn.execute("DELETE FROM continuous_events")
            monitor.conn.commit()
            with self.assertRaises(ValueError):
                monitor.events()

    def test_empty_bank_and_invalid_config(self):
        empty = Path(self.tmp.name) / "empty.db"
        with ModelBank(empty, 17) as bank:
            with self.assertRaises(ValueError):
                catalogue(bank)
        with ModelBank(self.models, 17) as bank:
            for kwargs in ({"window":1}, {"margin":float("nan")}, {"confirmations":0}, {"floor":float("inf")}):
                with self.assertRaises(ValueError):
                    StreamMonitor(Path(self.tmp.name)/"invalid.db", bank, **kwargs)

    def test_unfamiliar_evidence_reports_unknown_without_replacing_model(self):
        with ModelBank(self.models, 17) as bank, StreamMonitor(self.state, bank, floor=-0.001) as monitor:
            events = [monitor.observe(trajectory(17, "test", 6000+i)) for i in range(7)]
            self.assertTrue(any(ev["status"] == "unknown" for ev in events))
            self.assertIsNone(monitor.state["active"])
            self.assertEqual(monitor.state["last_status"], "unknown")

    def test_single_conflicting_episode_does_not_force_switch(self):
        schedule = [(i, ("standard", "fixed")) for i in range(16)]
        events = self.run_stream(schedule)
        self.assertEqual(events[-1]["selected"], "original")
        # One anomalous episode alone cannot satisfy the confirmation gate.
        event = self.run_stream([(16, ("high", "shifted"))])[-1]
        self.assertEqual(event["selected"], "original")

    def test_checkpoint_and_event_are_atomic(self):
        self.run_stream([(0, ("standard", "fixed"))])
        with sqlite3.connect(self.state) as conn:
            row = conn.execute("SELECT body FROM continuous_state").fetchone()[0]
            self.assertEqual(json.loads(row)["seq"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM continuous_events").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
