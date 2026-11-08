"""Optional consistency filter tests, replay and historical comparators."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.observable_affordances import (
    ConsistentRegimeMemory, FastRegimeMemory, RegimeRetrievalMemory,
    NumericOutcomeMemory, ObservableWorld, digest,
)
from benchmarks.archive_consistency_benchmark import (
    DEV, ADDITIONAL, STAGES, CHECKPOINTS, METHODS, TEST_N, measure
)
from benchmarks.regime_retrieval_benchmark import actor_event


def event(kind):
    return {"features": [2, 6], "progress": kind == "A",
            "damage": kind == "B"}


class ArchiveConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.memory = ConsistentRegimeMemory()
        self.fast = FastRegimeMemory()
        for kind, count in (("A", 160), ("B", 48)):
            for _ in range(count):
                self.memory.observe(event(kind))
                self.fast.observe(event(kind))

    def test_discard_only_internal_mixed_block_not_historical_records(self):
        before = self.memory.record()
        decided = self.memory.selection()
        self.assertIn(2, decided["quarantined_archive_indices"])
        self.assertNotEqual(decided["source"], "archive_2")
        self.assertEqual(self.memory.record(), before)
        self.assertEqual(len(self.memory.events), 208)

    def test_early_return_recovers_a_pure_archived_rule(self):
        for _ in range(112):
            self.memory.observe(event("B"))
        for _ in range(4):
            self.memory.observe(event("A"))
        choice = self.memory.selection()
        self.assertTrue(choice["source"] in ("archive_0", "archive_1", "recent_8"))
        self.assertNotIn(2, [int(choice["source"].split("_")[1])]
                         if choice["source"].startswith("archive_") else [])
        self.assertEqual(choice["overlap_with_selected_training"], 0)

    def test_mixed_chunk_fails_cross_half_out_of_sample_prediction(self):
        pure = [event("A") for _ in range(64)]
        mixed = [event("A") for _ in range(32)] + [event("B") for _ in range(32)]
        self.assertGreater(self.memory._cross_half_score(pure), -1.5)
        self.assertLess(self.memory._cross_half_score(mixed), -1.5)

    def test_learned_records_not_promoted_and_no_acting_interface(self):
        self.assertFalse(hasattr(self.memory, "step"))
        self.assertFalse(hasattr(self.memory, "probe"))
        self.assertFalse(hasattr(NumericOutcomeMemory(), "selection"))
        self.assertEqual(self.memory.record()["state"]["schema"],
                         "developmental-ai.consistent-regime-retrieval/v1")
        self.assertNotEqual(self.memory.record()["state"]["schema"],
                            self.fast.record()["state"]["schema"])

    def test_resume_after_shutdown_reproduces_selection_and_choice(self):
        checkpoint = self.memory.record()
        recovered = ConsistentRegimeMemory.restore(copy.deepcopy(checkpoint))
        self.assertEqual(recovered.record(), checkpoint)
        self.assertEqual(recovered.selection(), self.memory.selection())
        frame = ObservableWorld(DEV[0], "test", 90000, "route-reversed").frame()
        self.assertEqual(recovered.choose(frame), self.memory.choose(frame))
        self.assertEqual(recovered.record(), checkpoint)

    def test_corrupted_hash_and_rehashed_bad_events_rejected(self):
        checkpoint = self.memory.record()
        bad = copy.deepcopy(checkpoint)
        bad["state"]["events"][0]["progress"] = False
        with self.assertRaises(ValueError):
            ConsistentRegimeMemory.restore(bad)
        bad["state"]["events"][0]["progress"] = 1
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            ConsistentRegimeMemory.restore(bad)

    def test_training_origin_and_context_independence(self):
        row = actor_event(DEV[0], "route", STAGES[0][2])
        self.assertEqual(set(row), {"features", "progress", "damage"})
        self.assertEqual(set(self.memory.record()["state"]), {"schema", "events"})
        for word in ("route-reversed", "return_A", "phase", "oracle"):
            self.assertNotIn(word, str(self.memory.record()["state"]))

    def test_frozen_study_shape_and_strict_cohort(self):
        self.assertEqual(len(METHODS), 10)
        self.assertEqual(TEST_N, 30)
        self.assertEqual(CHECKPOINTS["B"], (0,4,8,12,24,48,160))
        self.assertNotEqual(DEV, ADDITIONAL)
        with self.assertRaises(ValueError):
            measure((11,12,13))
        with self.assertRaises(ValueError):
            measure((ADDITIONAL[0],))


if __name__ == "__main__":
    unittest.main()
