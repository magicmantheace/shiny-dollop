"""Frozen-protocol unit tests for JointConcordanceRecoveryMemory.

Protocol: benchmarks/joint_concordance_recovery_protocol.json.
These tests use only handcrafted synthetic events and the ALREADY
INSPECTED stochastic cohort seed 212003 (frame/source shape only).
The frozen cohorts of this experiment (332003-family / 333001-family)
are never touched here: no cohort scores are viewed or run before or
during implementation.
"""
from __future__ import annotations

import copy
import unittest

from developmental_ai.joint_concordance_recovery import (
    JointConcordanceRecoveryMemory, SCHEMA, ACTING_WINDOW,
    NEWEST_WINDOW, REFERENCE_WINDOW, MINIMUM_EVENTS,
    GATE_OPPOSED_COUNT, RECOVERY_JOINT_COUNT,
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
    m = JointConcordanceRecoveryMemory()
    for r in rows:
        m.observe(r)
    return m


def plain_model(rows):
    m = RelationOutcomeMemory()
    for r in rows:
        m.observe(r)
    return m


# Archive (10 progress) + reference (24 damage) + newest (2 progress),
# all at span 5: both newest events are opposed to the reference AND
# concordant with the archive, on the SAME events -> both joint,
# recovery must fire, taking priority over abstention (opposed == 2).
RECOVERY_ROWS = ([row("progress") for _ in range(10)]
                 + [row("damage") for _ in range(24)]
                 + [row("progress"), row("progress")])

# Archive (10 progress) + reference (24 progress) + newest (2 damage):
# both newest opposed, neither archive-concordant -> joint 0, abstain.
ABSTAIN_ROWS = ([row("progress") for _ in range(10)]
                + [row("progress") for _ in range(24)]
                + [row("damage"), row("damage")])


class JointConcordanceRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = STOCHASTIC_DEV[0]
        cls.source, cls.cost = public_train(cls.seed, "original", 1000, 240)

    def test_frozen_parameters_match_protocol(self):
        self.assertEqual(ACTING_WINDOW, 8)
        self.assertEqual(NEWEST_WINDOW, 2)
        self.assertEqual(REFERENCE_WINDOW, 24)
        self.assertEqual(MINIMUM_EVENTS, 27)
        self.assertEqual(MINIMUM_EVENTS,
                         NEWEST_WINDOW + REFERENCE_WINDOW + 1)
        self.assertEqual(GATE_OPPOSED_COUNT, 2)
        self.assertEqual(RECOVERY_JOINT_COUNT, 1)

    def test_signals_not_evaluable_below_minimum_events(self):
        m = fed(RECOVERY_ROWS[:MINIMUM_EVENTS - 1])
        decision, model = m.selection()
        self.assertFalse(decision["gate_evaluable"])
        self.assertFalse(decision["abstained"])
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "all_available_below_minimum")
        self.assertEqual(decision["signal_events"], [])
        self.assertEqual(decision["archive_events"], [])
        self.assertEqual(decision["joint_events"], [])
        self.assertEqual(decision["joint_flags"], [])
        self.assertEqual(decision["joint_count"], 0)
        self.assertEqual(len(model.events), MINIMUM_EVENTS - 1)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIn(m.choose(frame),
                      {a["id"] for a in frame["actions"]})

    def test_minimum_events_exactly_is_evaluable(self):
        rows = ([row("progress")]
                + [row("damage") for _ in range(24)]
                + [row("progress"), row("progress")])
        self.assertEqual(len(rows), MINIMUM_EVENTS)
        decision, model = fed(rows).selection()
        self.assertTrue(decision["gate_evaluable"])
        self.assertTrue(decision["recovery_fired"])
        self.assertEqual(decision["joint_count"], 2)
        self.assertEqual(decision["archive_events_count"], 1)
        self.assertEqual(len(model.events), 1)

    def test_empty_memory_selection_rejected(self):
        with self.assertRaises(ValueError):
            JointConcordanceRecoveryMemory().selection()
        with self.assertRaises(ValueError):
            JointConcordanceRecoveryMemory().record()

    def test_recovery_fires_exact_records_and_archive_model(self):
        m = fed(RECOVERY_ROWS)
        decision, model = m.selection()
        self.assertTrue(decision["gate_evaluable"])
        self.assertEqual(decision["signal_events"], [
            {"span": 5, "reported_class": "progress",
             "reference_count": 24, "reference_majority": "damage",
             "matched": True, "opposed": True},
            {"span": 5, "reported_class": "progress",
             "reference_count": 24, "reference_majority": "damage",
             "matched": True, "opposed": True},
        ])
        self.assertEqual(decision["archive_events"], [
            {"span": 5, "reported_class": "progress",
             "archive_count": 10, "archive_majority": "progress",
             "archive_matched": True, "archive_concordant": True},
            {"span": 5, "reported_class": "progress",
             "archive_count": 10, "archive_majority": "progress",
             "archive_matched": True, "archive_concordant": True},
        ])
        self.assertEqual(decision["joint_flags"], [True, True])
        self.assertEqual(decision["joint_events"], [
            {"span": 5, "reported_class": "progress",
             "archive_concordant": True, "opposed": True, "joint": True},
            {"span": 5, "reported_class": "progress",
             "archive_concordant": True, "opposed": True, "joint": True},
        ])
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["matched_count"], 2)
        self.assertEqual(decision["concordant_count"], 2)
        self.assertEqual(decision["archive_matched_count"], 2)
        self.assertEqual(decision["joint_count"], 2)
        self.assertTrue(decision["recovery_fired"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "retained_archive")
        self.assertEqual(decision["source"], "retained_archive")
        self.assertEqual(decision["archive_events_count"], 10)
        self.assertEqual(decision["learner_training_actions"], 0)
        self.assertEqual(model.events, [dict(r) for r in RECOVERY_ROWS[:10]])
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(m.choose(frame),
                         plain_model(RECOVERY_ROWS[:10]).choose(frame))

    def test_recovery_takes_priority_over_abstention(self):
        decision, _ = fed(RECOVERY_ROWS).selection()
        self.assertEqual(decision["opposed_count"], GATE_OPPOSED_COUNT)
        self.assertTrue(decision["recovery_fired"])
        self.assertFalse(decision["abstained"])
        self.assertFalse(decision["gate_fired"])

    def test_single_joint_event_recovers(self):
        # The single changed element vs the graded retained-recovery
        # candidate: ONE joint event suffices. Newest 1 (span 5):
        # progress, opposed to damage reference, concordant with
        # progress archive -> joint. Newest 2 (span 5): damage,
        # concordant with the reference, not concordant with the
        # archive -> not joint. concordant 1 / opposed 1 / joint 1.
        # The preceding candidate did NOT recover here (it required
        # concordant_count == 2); this candidate must.
        rows = ([row("progress") for _ in range(10)]
                + [row("damage") for _ in range(24)]
                + [row("progress"), row("damage")])
        decision, model = fed(rows).selection()
        self.assertEqual(decision["concordant_count"], 1)
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["joint_flags"], [True, False])
        self.assertEqual(decision["joint_count"], 1)
        self.assertTrue(decision["recovery_fired"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "retained_archive")
        self.assertEqual(len(model.events), 10)

    def test_single_joint_event_recovers_despite_opposed_count_two(self):
        # Span 5 newest: joint (as above). Span 3 newest: damage with
        # progress archive and progress reference -> opposed only,
        # not concordant, not joint. opposed 2, joint 1 -> recovery
        # still takes priority over abstention.
        archive = ([row("progress") for _ in range(6)]
                   + [row("progress", span=3) for _ in range(6)])
        reference = ([row("damage") for _ in range(12)]
                     + [row("progress", span=3) for _ in range(12)])
        rows = archive + reference + [row("progress"),
                                      row("damage", span=3)]
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["concordant_count"], 1)
        self.assertEqual(decision["joint_flags"], [True, False])
        self.assertEqual(decision["joint_count"], 1)
        self.assertTrue(decision["recovery_fired"])
        self.assertFalse(decision["abstained"])

    def test_pooled_counts_on_different_events_do_not_recover(self):
        # Concordance and opposition pooled across DIFFERENT events
        # must NOT trigger recovery. Span 5 newest: progress with
        # progress archive and progress reference -> concordant only.
        # Span 3 newest: damage with progress archive and progress
        # reference -> opposed only (archive-matched, not concordant).
        # concordant 1, opposed 1, joint 0 -> recent8, no abstention.
        archive = ([row("progress") for _ in range(6)]
                   + [row("progress", span=3) for _ in range(6)])
        reference = ([row("progress") for _ in range(12)]
                     + [row("progress", span=3) for _ in range(12)])
        rows = archive + reference + [row("progress"),
                                      row("damage", span=3)]
        decision, model = fed(rows).selection()
        self.assertEqual(decision["concordant_count"], 1)
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["joint_flags"], [False, False])
        self.assertEqual(decision["joint_count"], 0)
        self.assertFalse(decision["recovery_fired"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(len(model.events), ACTING_WINDOW)

    def test_both_concordant_but_none_opposed_does_not_recover(self):
        # Stationary progress: concordant_count == 2 satisfied the
        # concordance half of the OLD pooled rule, but with no
        # opposition there is no joint event -> recent8 exactly.
        # (The old rule also required opposed >= 1, so this case is
        # shared; it pins that joint, not concordance, is the test.)
        rows = [row("progress") for _ in range(40)]
        m = fed(rows)
        decision, model = m.selection()
        self.assertEqual(decision["concordant_count"], 2)
        self.assertEqual(decision["opposed_count"], 0)
        self.assertEqual(decision["joint_count"], 0)
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(len(model.events), ACTING_WINDOW)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(m.choose(frame),
                         plain_model(rows[-ACTING_WINDOW:]).choose(frame))

    def test_both_opposed_but_none_concordant_abstains(self):
        m = fed(ABSTAIN_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["concordant_count"], 0)
        self.assertEqual(decision["joint_count"], 0)
        self.assertFalse(decision["recovery_fired"])
        self.assertTrue(decision["abstained"])
        self.assertTrue(decision["gate_fired"])
        self.assertEqual(decision["branch"], "abstained")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(m.choose(frame))
        self.assertEqual(m.record()["state"]["events"],
                         [dict(r) for r in ABSTAIN_ROWS])

    def test_neutral_newest_event_is_never_joint(self):
        rows = ([row("progress") for _ in range(10)]
                + [row("damage") for _ in range(24)]
                + [row("neutral"), row("neutral")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["joint_flags"], [False, False])
        self.assertEqual(decision["joint_count"], 0)
        self.assertEqual(decision["concordant_count"], 0)
        self.assertEqual(decision["opposed_count"], 0)
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "recent8")

    def test_joint_event_with_second_neutral_still_recovers(self):
        rows = ([row("progress") for _ in range(10)]
                + [row("damage") for _ in range(24)]
                + [row("progress"), row("neutral")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["joint_flags"], [True, False])
        self.assertEqual(decision["joint_count"], 1)
        self.assertTrue(decision["recovery_fired"])

    def test_tied_archive_majority_gives_no_joint(self):
        rows = ([row("progress") for _ in range(5)]
                + [row("damage") for _ in range(5)]
                + [row("damage") for _ in range(24)]
                + [row("progress"), row("progress")])
        decision, _ = fed(rows).selection()
        for rec in decision["archive_events"]:
            self.assertIsNone(rec["archive_majority"])
            self.assertFalse(rec["archive_concordant"])
        self.assertEqual(decision["joint_count"], 0)
        self.assertFalse(decision["recovery_fired"])
        self.assertTrue(decision["abstained"])

    def test_tied_reference_majority_gives_no_joint(self):
        # Reference tied progress/damage at span 5 -> no expectation,
        # so newest progress events are concordant but not opposed.
        rows = ([row("progress") for _ in range(10)]
                + [row("damage") for _ in range(12)]
                + [row("progress") for _ in range(12)]
                + [row("progress"), row("progress")])
        decision, _ = fed(rows).selection()
        for rec in decision["signal_events"]:
            self.assertIsNone(rec["reference_majority"])
            self.assertFalse(rec["opposed"])
        self.assertEqual(decision["concordant_count"], 2)
        self.assertEqual(decision["joint_count"], 0)
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "recent8")

    def test_span_absent_from_archive_is_not_joint(self):
        rows = ([row("progress") for _ in range(10)]
                + [row("damage") for _ in range(24)]
                + [row("progress", span=9), row("progress")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["archive_events"][0]["archive_count"], 0)
        self.assertEqual(decision["joint_flags"], [False, True])
        self.assertEqual(decision["joint_count"], 1)
        self.assertTrue(decision["recovery_fired"])

    def test_joint_is_span_specific(self):
        archive = ([row("progress") for _ in range(6)]
                   + [row("damage", span=3) for _ in range(6)])
        reference = ([row("damage") for _ in range(12)]
                     + [row("progress", span=3) for _ in range(12)])
        rows = archive + reference + [row("progress"),
                                      row("damage", span=3)]
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["joint_flags"], [True, True])
        self.assertEqual(decision["joint_count"], 2)
        self.assertEqual(decision["concordant_count"], 2)
        self.assertEqual(decision["opposed_count"], 2)
        self.assertTrue(decision["recovery_fired"])

    def test_archive_excludes_reference_and_newest_windows(self):
        rows = ([row("progress") for _ in range(2)]
                + [row("damage") for _ in range(24)]
                + [row("progress"), row("progress")])
        decision, model = fed(rows).selection()
        self.assertEqual(decision["archive_events_count"], 2)
        for rec in decision["archive_events"]:
            self.assertEqual(rec["archive_count"], 2)
            self.assertEqual(rec["archive_majority"], "progress")
        self.assertTrue(decision["recovery_fired"])
        self.assertEqual(model.events, [dict(r) for r in rows[:2]])

    def test_no_fitted_probability_fields_in_decision(self):
        decision, _ = fed(RECOVERY_ROWS).selection()
        for key in decision:
            self.assertNotIn("probabilit", key)
            self.assertNotIn("log_score", key)
        for rec in decision["signal_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class", "reference_count",
                              "reference_majority", "matched", "opposed"})
        for rec in decision["archive_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class", "archive_count",
                              "archive_majority", "archive_matched",
                              "archive_concordant"})
        for rec in decision["joint_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class",
                              "archive_concordant", "opposed", "joint"})

    def test_new_feedback_invalidates_cached_selection(self):
        m = fed([row("progress") for _ in range(30)])
        old = m.selection()
        self.assertIs(old, m.selection())
        m.observe(row("progress"))
        new = m.selection()
        self.assertIsNot(new, old)
        self.assertEqual(new[0]["recorded_events"], 31)

    def test_replay_exact_and_choice_read_only(self):
        m = fed(self.source)
        for r in public_train(self.seed, "reversed", 2000, 8)[0]:
            m.observe(r)
        saved = m.record()
        restored = JointConcordanceRecoveryMemory.restore(
            copy.deepcopy(saved))
        frame = StochasticWorld(self.seed, "test", 160000,
                                "reversed").frame()
        self.assertEqual(m.choose(frame), restored.choose(frame))
        self.assertEqual(m.selection()[0], restored.selection()[0])
        self.assertEqual(m.record(), saved)
        self.assertEqual(restored.record(), saved)
        self.assertFalse(hasattr(m, "step"))

    def test_replay_reproduces_recovery_decision(self):
        m = fed(RECOVERY_ROWS)
        saved = m.record()
        restored = JointConcordanceRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertTrue(restored.selection()[0]["recovery_fired"])
        self.assertEqual(restored.selection()[0]["joint_events"],
                         m.selection()[0]["joint_events"])
        self.assertEqual(restored.selection()[0]["joint_count"], 2)

    def test_reject_invalid_events_without_partial_write(self):
        m = JointConcordanceRecoveryMemory()
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
            JointConcordanceRecoveryMemory.restore(bad)
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            JointConcordanceRecoveryMemory.restore(bad)
        bad2 = copy.deepcopy(saved)
        bad2["state"]["schema"] = "developmental-ai.other/v1"
        bad2["sha256"] = digest(bad2["state"])
        with self.assertRaises(ValueError):
            JointConcordanceRecoveryMemory.restore(bad2)

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
