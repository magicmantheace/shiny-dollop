"""Frozen-protocol unit tests for GatedArchivePrequentialMemory.

Protocol: benchmarks/early_post_switch_adaptation_protocol.json.
These tests use only handcrafted synthetic events and the ALREADY
INSPECTED stochastic cohort seed 212003 (frame/source shape only).
The frozen cohorts of this experiment (292003-family / 293001-family)
are never touched here: no cohort scores are viewed before or during
implementation.
"""
from __future__ import annotations

import copy
import math
import unittest

from developmental_ai.gated_archive_prequential_memory import (
    GatedArchivePrequentialMemory, SCHEMA, ARCHIVE_SIZE, WARMUP, WINDOWS,
    SCORING_TAIL, DISPLACEMENT_MARGIN, CONTRADICTION_WINDOW,
    CONTRADICTION_MIN, CONTRADICTION_P, ADEQUACY_MEAN_THRESHOLD,
    ADEQUACY_TOTAL_THRESHOLD,
)
from developmental_ai.observable_affordances import digest
from developmental_ai.relation_outcome_memory import RelationOutcomeMemory
from benchmarks.stochastic_prequential_benchmark import (
    DEV as STOCHASTIC_DEV, StochasticWorld, public_train,
)


def row(outcome, span=5):
    return {"features": {"inlet": 0, "outlet": span},
            "progress": outcome == "progress",
            "damage": outcome == "damage"}


def fed(rows):
    m = GatedArchivePrequentialMemory()
    for r in rows:
        m.observe(r)
    return m


class GatedArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Already-inspected seed from the preceding stochastic study;
        # used only for a realistic public source stream and TEST frame.
        cls.seed = STOCHASTIC_DEV[0]
        cls.source, cls.cost = public_train(cls.seed, "original", 1000, 240)

    def test_frozen_parameters_match_protocol(self):
        self.assertEqual(ARCHIVE_SIZE, 192)
        self.assertEqual(WARMUP, 240)
        self.assertEqual(WINDOWS, (8, 32))
        self.assertEqual(SCORING_TAIL, 8)
        self.assertEqual(DISPLACEMENT_MARGIN, 1.0)
        self.assertEqual((CONTRADICTION_WINDOW, CONTRADICTION_MIN,
                          CONTRADICTION_P), (4, 2, 0.125))
        self.assertEqual(ADEQUACY_MEAN_THRESHOLD, -1.2)
        self.assertEqual(ADEQUACY_TOTAL_THRESHOLD, -9.6)
        self.assertAlmostEqual(ADEQUACY_TOTAL_THRESHOLD,
                               ADEQUACY_MEAN_THRESHOLD * SCORING_TAIL)

    def test_warmup_required(self):
        m = fed([row("progress") for _ in range(WARMUP - 1)])
        with self.assertRaises(ValueError):
            m.selection()

    def test_stationary_evidence_retains_archive(self):
        m = fed([row("progress") for _ in range(240)])
        decision, model = m.selection()
        self.assertEqual(decision["source"], "archive")
        self.assertEqual(decision["selection"], "archive")
        self.assertFalse(decision["abstained"])
        self.assertFalse(decision["contradiction_override"])
        self.assertEqual(decision["archive_contradictions_latest4"], 0)
        self.assertEqual(decision["prequential_scoring_events"], 8)
        self.assertEqual(decision["predictor_training_overlap"], 0)
        self.assertTrue(all(math.isfinite(s)
                            for s in decision["prequential_scores"]))
        # The live archive is exactly the model fitted on the first 192.
        archive = RelationOutcomeMemory()
        for r in m.events[:ARCHIVE_SIZE]:
            archive.observe(r)
        self.assertEqual(model.estimate({"inlet": 0, "outlet": 5}),
                         archive.estimate({"inlet": 0, "outlet": 5}))
        self.assertEqual(len(model.events), ARCHIVE_SIZE)

    def test_margin_displacement_without_contradiction(self):
        rows = [row("progress" if i % 2 == 0 else "damage")
                for i in range(192)]
        rows += [row("progress") for _ in range(48)]
        decision, _ = fed(rows).selection()
        self.assertFalse(decision["contradiction_override"])
        self.assertEqual(decision["archive_contradictions_latest4"], 0)
        self.assertEqual(decision["source"], "recent8")
        self.assertFalse(decision["abstained"])
        scores = decision["prequential_scores"]
        self.assertGreater(scores[1] - scores[0], DISPLACEMENT_MARGIN)
        self.assertLessEqual(scores[2] - scores[1], DISPLACEMENT_MARGIN)

    def test_contradiction_override_displaces_archive_fast(self):
        # Four reversed outcomes: the latest-4 scoring window is entirely
        # damage, so the override fires within 4 post-switch observations.
        # (At exactly 8 reversed outcomes the selected recent model's mean
        # score is -1.2009, marginally under the adequacy gate, and the
        # learner abstains instead -- see the adequacy-gate test for the
        # abstention path exercised deterministically.)
        rows = [row("progress") for _ in range(240)]
        rows += [row("damage") for _ in range(4)]
        m = fed(rows)
        decision, _ = m.selection()
        self.assertTrue(decision["contradiction_override"])
        self.assertEqual(decision["archive_contradictions_latest4"], 4)
        self.assertEqual(decision["source"], "recent8")
        self.assertTrue(decision["reason"].startswith(
            "contradiction_override"))
        self.assertFalse(decision["abstained"])

    def test_adequacy_gate_abstains_when_selected_model_fits_poorly(self):
        rows = [row("progress", span=i % 8) for i in range(232)]
        rows += [row("damage", span=s) for s in range(8)]
        m = fed(rows)
        decision, _ = m.selection()
        self.assertTrue(decision["contradiction_override"])
        self.assertEqual(decision["source"], "recent8")
        self.assertLess(decision["selected_mean_prequential_log_score"],
                        ADEQUACY_MEAN_THRESHOLD)
        self.assertTrue(decision["abstained"])
        self.assertEqual(decision["selection"], "abstained-by-gate")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(m.choose(frame))

    def test_archive_reselected_on_return_to_original_rule(self):
        rows = [row("progress") for _ in range(240)]
        rows += [row("damage") for _ in range(8)]
        rows += [row("progress") for _ in range(32)]
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["source"], "archive")
        self.assertFalse(decision["contradiction_override"])
        self.assertFalse(decision["abstained"])

    def test_archive_never_refitted_by_later_events(self):
        rows = [row("progress") for _ in range(240)]
        rows += [row("damage") for _ in range(64)]
        m = fed(rows)
        _, model = m.selection()
        decision = m.selection()[0]
        self.assertNotEqual(decision["source"], "archive")
        frozen = RelationOutcomeMemory()
        for r in rows[:ARCHIVE_SIZE]:
            frozen.observe(r)
        # Recompute the archive directly: it still equals the first-192 fit
        # even though the selection has moved on to a recent window.
        self.assertEqual(frozen.estimate({"inlet": 0, "outlet": 5}),
                         m._model(m.events[:ARCHIVE_SIZE])
                         .estimate({"inlet": 0, "outlet": 5}))
        self.assertEqual(len(frozen.events), ARCHIVE_SIZE)

    def test_new_feedback_invalidates_cached_selection(self):
        m = fed([row("progress") for _ in range(240)])
        old = m.selection()
        self.assertIs(old, m.selection())
        m.observe(row("damage"))
        new = m.selection()
        self.assertIsNot(new, old)
        self.assertEqual(new[0]["recorded_events"], 241)

    def test_replay_exact_and_choice_read_only(self):
        m = fed(self.source)
        for r in public_train(self.seed, "reversed", 2000, 8)[0]:
            m.observe(r)
        saved = m.record()
        restored = GatedArchivePrequentialMemory.restore(
            copy.deepcopy(saved))
        frame = StochasticWorld(self.seed, "test", 160000,
                                "reversed").frame()
        self.assertEqual(m.choose(frame), restored.choose(frame))
        self.assertEqual(m.selection()[0], restored.selection()[0])
        self.assertEqual(m.record(), saved)
        self.assertEqual(restored.record(), saved)
        self.assertFalse(hasattr(m, "step"))

    def test_choose_returns_frame_action_when_not_abstaining(self):
        m = fed(self.source)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        picked = m.choose(frame)
        self.assertIn(picked, {a["id"] for a in frame["actions"]})

    def test_reject_invalid_events_without_partial_write(self):
        m = GatedArchivePrequentialMemory()
        m.observe(row("progress"))
        saved = m.record()
        with self.assertRaises(ValueError):
            m.observe({"features": {"inlet": 0, "outlet": 5},
                       "progress": True, "damage": True})
        with self.assertRaises(ValueError):
            m.observe({"features": {"other": 0, "outlet": 5},
                       "progress": True, "damage": False})
        self.assertEqual(m.record(), saved)

    def test_reject_forged_or_rehashed_record(self):
        m = fed([row("progress")])
        saved = m.record()
        bad = copy.deepcopy(saved)
        bad["state"]["events"][0]["damage"] = True
        with self.assertRaises(ValueError):
            GatedArchivePrequentialMemory.restore(bad)
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            GatedArchivePrequentialMemory.restore(bad)
        bad2 = copy.deepcopy(saved)
        bad2["state"]["schema"] = "developmental-ai.other/v1"
        bad2["sha256"] = digest(bad2["state"])
        with self.assertRaises(ValueError):
            GatedArchivePrequentialMemory.restore(bad2)

    def test_record_contains_only_public_events(self):
        m = fed(self.source)
        state = m.record()["state"]
        self.assertEqual(set(state), {"schema", "events"})
        self.assertEqual(state["schema"], SCHEMA)
        self.assertEqual(set(state["events"][0]),
                         {"features", "progress", "damage"})
        for forbidden in ('"physics"', '"phase"', '"episode"',
                          '"split"', '"seed"', '"rule"'):
            self.assertNotIn(forbidden, str(m.record()))


if __name__ == "__main__":
    unittest.main()
