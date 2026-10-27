"""Fast recovery reproducibility, independence and optional-controller tests."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.observable_affordances import (
    FastRegimeMemory, RegimeRetrievalMemory, NumericOutcomeMemory,
    ObservableWorld, FAST_REGIME_TAIL, FAST_REGIME_RECENT, digest,
)
from benchmarks.fast_reacquisition_benchmark import (
    DEV, ADDITIONAL, STAGES, METHODS, CHECKPOINTS, TEST_N,
    build_controllers, eval_episode, freeze_numeric, measure,
)
from benchmarks.regime_retrieval_benchmark import actor_event


def row(kind):
    return {"features": [2, 6],
            "progress": kind == "A", "damage": kind == "B"}


class FastRegimeTests(unittest.TestCase):
    def setUp(self):
        self.fast, self.old = FastRegimeMemory(), RegimeRetrievalMemory()
        for _ in range(160):
            self.fast.observe(row("A"))
            self.old.observe(row("A"))

    def feed(self, kind, count):
        for _ in range(count):
            self.fast.observe(row(kind))
            self.old.observe(row(kind))

    def test_no_changed_default_controller_or_added_probing_authority(self):
        self.assertFalse(hasattr(NumericOutcomeMemory(), "selection"))
        self.assertFalse(hasattr(self.fast, "probe"))
        self.assertFalse(hasattr(self.fast, "step"))
        self.assertEqual(self.fast.record()["state"]["schema"],
                         "developmental-ai.fast-regime-retrieval/v1")

    def test_new_reversed_rule_can_fit_recent_nonoverlapping_evidence(self):
        self.feed("B", 12)
        self.assertEqual(self.fast.selection()["source"], "recent_8")
        self.assertEqual(self.fast.selection()["overlap_with_selected_training"], 0)
        self.assertEqual(self.fast.selection()["scoring_events"], FAST_REGIME_TAIL)

    def test_prior_rule_retrieved_after_four_observed_return_events(self):
        self.feed("B", 160)
        self.feed("A", 4)
        self.assertTrue(self.fast.selection()["source"].startswith("archive_"))
        self.assertEqual(self.old.selection()["evidence_events"], 12)

    def test_all_checkpoint_memory_restarts_and_action_identity(self):
        self.feed("B", 12)
        saved = self.fast.record()
        restored = FastRegimeMemory.restore(copy.deepcopy(saved))
        self.assertEqual(saved, restored.record())
        self.assertEqual(self.fast.selection(), restored.selection())
        frame = ObservableWorld(DEV[0], "test", 70000, "route-reversed").frame()
        self.assertEqual(self.fast.choose(frame), restored.choose(frame))
        self.assertEqual(saved, restored.record())

    def test_tampered_or_noncanonical_history_rejected(self):
        bad = copy.deepcopy(self.fast.record())
        bad["state"]["events"][0]["progress"] = False
        with self.assertRaises(ValueError):
            FastRegimeMemory.restore(bad)
        bad["sha256"] = digest(bad["state"])
        # An authentic neutral event could be legitimate, so make it invalid.
        bad["state"]["events"][0]["damage"] = True
        bad["state"]["events"][0]["progress"] = True
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            FastRegimeMemory.restore(bad)

    def test_phase_and_world_labels_absent_from_checkpoint(self):
        record = self.fast.record()
        self.assertEqual(set(record["state"]), {"schema", "events"})
        self.assertEqual(set(record["state"]["events"][0]),
                         {"features", "progress", "damage"})
        for forbidden in ("return_A", "route-reversed", "stage", "oracle"):
            self.assertNotIn(forbidden, str(record))

    def test_observed_evidence_is_from_an_independent_actor(self):
        event = actor_event(DEV[0], "route", STAGES[0][2])
        self.assertEqual(set(event), {"features", "progress", "damage"})
        self.assertTrue(type(event["progress"]) is bool)
        self.assertTrue(type(event["damage"]) is bool)
        self.assertEqual(len(METHODS), 9)
        self.assertEqual(TEST_N, 30)
        self.assertEqual(CHECKPOINTS["B"], (0, 4, 8, 12, 24, 48, 160))
        self.assertEqual(CHECKPOINTS["return_A"], (0, 4, 8, 12, 24, 48))

    def test_comparators_see_identical_historical_training_events(self):
        self.feed("B", 12)
        frozen = freeze_numeric(self.fast.events[:160])
        policies = build_controllers(self.fast, self.old, frozen)
        self.assertEqual(len(policies["recent_8_knn"].examples), 8)
        self.assertEqual(len(policies["recent_32_knn"].examples), 32)
        self.assertEqual(len(policies["cumulative_knn"].examples), 172)
        self.assertEqual(self.fast.events, self.old.events)

    def test_evaluation_never_updates_model_and_abstention_fails(self):
        snapshot = self.fast.record()
        policies = build_controllers(self.fast, self.old,
                                     freeze_numeric(self.fast.events[:160]))
        for method in METHODS:
            result = eval_episode(DEV[0], "route-reversed", 70000, method, policies)
            self.assertTrue(result["success"] in (0, 1))
            self.assertTrue(result["hurt"] in (0, 1))
            if method == "always_abstain":
                self.assertEqual(result["success"], 0)
                self.assertEqual(result["abstained"], 1)
        self.assertEqual(snapshot, self.fast.record())

    def test_only_exact_frozen_cohorts_are_accepted(self):
        self.assertNotEqual(DEV, ADDITIONAL)
        for seeds in ((1, 2, 3), (DEV[0],), tuple(reversed(ADDITIONAL))):
            with self.assertRaises(ValueError):
                measure(seeds)


if __name__ == "__main__":
    unittest.main()
