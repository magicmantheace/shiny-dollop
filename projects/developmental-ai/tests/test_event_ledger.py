"""Simulation ledger contract and trust boundary tests."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from developmental_ai.curriculum import CurriculumBrain
from developmental_ai.delayed_choice import DelayBrain
from developmental_ai.occluded_navigation import OccludedBrain
from developmental_ai.uncertain_navigation import RingBrain
from developmental_ai.event_ledger import export_trace, verify_ledger, _digest


class EventLedgerTests(unittest.TestCase):
    def make_trace(self, model: str) -> dict:
        if model == "uncertain":
            with tempfile.TemporaryDirectory() as folder:
                with RingBrain(Path(folder) / "ring.db", 11) as brain:
                    return brain.trace(1, policy="oracle")
        if model == "occluded":
            with tempfile.TemporaryDirectory() as folder:
                with OccludedBrain(Path(folder) / "brain.db", 11) as brain:
                    return brain.trace(1, policy="oracle")
        if model == "delayed":
            with tempfile.TemporaryDirectory() as folder:
                with DelayBrain(Path(folder) / "brain.db", 11) as brain:
                    return brain.trace(1)
        with tempfile.TemporaryDirectory() as folder:
            with CurriculumBrain(Path(folder) / "brain.db", 11) as brain:
                return brain.trace("collect", 1, policy="oracle")

    def test_export_and_replay_both_simulations(self):
        for model in ("delayed", "curriculum", "occluded", "uncertain"):
            with self.subTest(model=model):
                trace = self.make_trace(model)
                ledger = export_trace(trace)
                result = verify_ledger(ledger, trace)
                steps = trace["outcome"]["events"] if model in ("occluded", "uncertain") else trace["events"]
                self.assertEqual(len(ledger["events"]), len(steps) * 3 + 1)
                self.assertTrue(result["verified"])
                self.assertTrue(result["trace_bound"])
                self.assertEqual(ledger, export_trace(trace))

    def test_chain_can_detect_changes_but_not_authenticate_origin(self):
        trace = self.make_trace("delayed")
        ledger = export_trace(trace)
        tampered = copy.deepcopy(ledger)
        tampered["events"][1]["payload"]["action"] = 900
        with self.assertRaises(ValueError):
            verify_ledger(tampered)
        # Even after the attacker recomputes *every* hash, binding to the
        # separately verified trace catches the change.
        previous = "0" * 64
        for event in tampered["events"]:
            event["previous_sha256"] = previous
            previous = _digest({k: v for k, v in event.items() if k != "sha256"})
            event["sha256"] = previous
        self.assertTrue(verify_ledger(tampered)["verified"])  # checksum != attestation
        with self.assertRaises(ValueError):
            verify_ledger(tampered, trace)

    def test_untrusted_source_and_unbounded_ids_rejected(self):
        trace = self.make_trace("delayed")
        for subject_id in ("Person Name", "../traversal", "x" * 70, "ABC"):
            with self.assertRaises(ValueError):
                export_trace(trace, subject_id)
        for key, value in (("source_kind", "user"), ("scope", "execute-shell")):
            ledger = export_trace(trace)
            ledger[key] = value
            with self.assertRaises(ValueError):
                verify_ledger(ledger)
        ledger = export_trace(trace)
        ledger["events"][0]["payload"]["secret"] = "should not be accepted"
        with self.assertRaises(ValueError):
            verify_ledger(ledger, trace)

    def test_duplicate_and_missing_entries_rejected(self):
        trace = self.make_trace("delayed")
        ledger = export_trace(trace)
        ledger["events"].insert(0, copy.deepcopy(ledger["events"][0]))
        with self.assertRaises(ValueError):
            verify_ledger(ledger)


if __name__ == "__main__":
    unittest.main()
