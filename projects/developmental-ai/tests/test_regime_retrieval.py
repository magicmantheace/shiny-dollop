"""Outcome-backed retrieval memory: replay, leakage, return and action limits."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.observable_affordances import (
    RegimeRetrievalMemory, NumericOutcomeMemory, digest, REGIME_CHUNK,
    REGIME_TAIL, ObservableWorld,
)
from benchmarks.regime_retrieval_benchmark import (
    DEV, ADDITIONAL, STAGES, METHODS, actor_event, test_episode,
)


def evidence(kind):
    return {"features": [2, 6],
            "progress": kind == "A", "damage": kind == "B"}


class RegimeRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.bank = RegimeRetrievalMemory()
        for _ in range(REGIME_CHUNK):
            self.bank.observe(evidence("A"))
        for _ in range(REGIME_TAIL):
            self.bank.observe(evidence("A"))

    def test_existing_knn_is_untouched_and_new_model_is_opt_in(self):
        old = NumericOutcomeMemory()
        old.add(evidence("A"))
        self.assertEqual(old.estimate([2, 6])["progress"], 1.0)
        self.assertFalse(hasattr(old, "selection"))
        self.assertFalse(hasattr(self.bank, "step"))
        self.assertFalse(hasattr(self.bank, "probe"))

    def test_selector_uses_out_of_sample_tail_and_retains_prior_regime(self):
        self.assertEqual(self.bank.selection()["chunk_index"], 0)
        # Put the B block on a *complete* new chunk. The initial setUp
        # included a 12-event incomplete A chunk; appending B there would
        # deliberately mix rules and is not evidence of a B-only memory.
        bank = RegimeRetrievalMemory()
        for _ in range(REGIME_CHUNK * 2):
            bank.observe(evidence("A"))
        for _ in range(REGIME_CHUNK + REGIME_TAIL):
            bank.observe(evidence("B"))
        # Last 12 training points are never allowed in candidate chunks.
        self.assertEqual(bank.selection()["chunks_evaluated"], 3)
        self.assertEqual(bank.selection()["chunk_index"], 2)
        for _ in range(REGIME_TAIL):
            bank.observe(evidence("A"))
        self.assertEqual(bank.selection()["chunk_index"], 0)

    def test_no_independent_selection_evidence_is_rejected(self):
        bank = RegimeRetrievalMemory()
        for _ in range(REGIME_CHUNK + REGIME_TAIL - 1):
            bank.observe(evidence("A"))
        with self.assertRaises(ValueError):
            bank.selection()

    def test_restart_retrieves_identical_regime_and_future_predictions(self):
        for _ in range(REGIME_CHUNK):
            self.bank.observe(evidence("B"))
        for _ in range(REGIME_TAIL):
            self.bank.observe(evidence("B"))
        for _ in range(REGIME_TAIL):
            self.bank.observe(evidence("A"))
        saved = self.bank.record()
        restored = RegimeRetrievalMemory.restore(copy.deepcopy(saved))
        self.assertEqual(restored.record(), saved)
        self.assertEqual(restored.selection(), self.bank.selection())
        frame = ObservableWorld(DEV[0], "test", 52000, "route").frame()
        self.assertEqual(restored.choose(frame), self.bank.choose(frame))
        self.assertEqual(restored.record(), saved)

    def test_modified_checksum_and_invalid_rehashed_events_rejected(self):
        saved = self.bank.record()
        wrong = copy.deepcopy(saved)
        wrong["state"]["events"][0]["damage"] = True
        with self.assertRaises(ValueError):
            RegimeRetrievalMemory.restore(wrong)
        wrong["sha256"] = digest(wrong["state"])
        with self.assertRaises(ValueError):
            RegimeRetrievalMemory.restore(wrong)
        with self.assertRaises(ValueError):
            self.bank.observe({"features": [2, 6], "progress": 1, "damage": 0})

    def test_event_record_contains_no_domain_names_or_phase_controls(self):
        payload = self.bank.record()["state"]
        self.assertEqual(set(payload), {"schema", "events"})
        self.assertEqual(set(payload["events"][0]), {"features", "progress", "damage"})
        for marker in ("route-reversed", "return_A", "stage", "target"):
            self.assertNotIn(marker, str(payload))

    def test_external_observer_does_not_give_action_authority(self):
        event = actor_event(DEV[0], "route", STAGES[0][2])
        self.assertEqual(set(event), {"features", "progress", "damage"})
        self.assertEqual(sum((event["progress"], event["damage"])) <= 1, True)
        self.assertEqual(len(METHODS), 7)
        self.assertNotEqual(DEV, ADDITIONAL)
        with self.assertRaises(ValueError):
            test_episode(DEV[0], "route", 50000, "unknown", self.bank, self.bank.events)

    def test_selecting_a_real_test_frame_never_mutates_memory(self):
        before = self.bank.record()
        frame = ObservableWorld(DEV[0], "test", 50000, "route").frame()
        choice = self.bank.choose(frame)
        self.assertIn(choice, {a["id"] for a in frame["actions"]})
        self.assertEqual(self.bank.record(), before)


if __name__ == "__main__":
    unittest.main()
