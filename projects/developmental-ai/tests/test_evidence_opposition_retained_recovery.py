"""Frozen-protocol unit tests for EvidenceOppositionRecoveryMemory.

Protocol: benchmarks/evidence_opposition_retained_recovery_protocol.json.
These tests use only handcrafted synthetic events and the ALREADY
INSPECTED stochastic cohort seed 212003 (frame/source shape only).
The frozen cohorts of this experiment (322003-family / 323001-family)
are never touched here: no cohort scores are viewed or run before or
during implementation.
"""
from __future__ import annotations

import copy
import unittest

from developmental_ai.evidence_opposition_retained_recovery import (
    EvidenceOppositionRecoveryMemory, SCHEMA, ACTING_WINDOW,
    NEWEST_WINDOW, REFERENCE_WINDOW, MINIMUM_EVENTS,
    GATE_OPPOSED_COUNT, RECOVERY_CONCORDANT_COUNT,
    RECOVERY_MINIMUM_OPPOSED,
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
    m = EvidenceOppositionRecoveryMemory()
    for r in rows:
        m.observe(r)
    return m


def plain_model(rows):
    m = RelationOutcomeMemory()
    for r in rows:
        m.observe(r)
    return m


# Archive (10 progress) + reference (24 damage) + newest (2 progress),
# all at span 5: both newest events are opposed to the reference and
# concordant with the archive -> recovery must fire, taking priority
# over the abstention branch even though opposed_count == 2.
RECOVERY_ROWS = ([row("progress") for _ in range(10)]
                 + [row("damage") for _ in range(24)]
                 + [row("progress"), row("progress")])

# Archive (10 progress) + reference (24 progress) + newest (2 damage):
# both newest opposed, neither archive-concordant -> abstention.
ABSTAIN_ROWS = ([row("progress") for _ in range(10)]
                + [row("progress") for _ in range(24)]
                + [row("damage"), row("damage")])


class EvidenceOppositionRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Already-inspected seed from the preceding stochastic study;
        # used only for a realistic public source stream and TEST frame.
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
        self.assertEqual(RECOVERY_CONCORDANT_COUNT, 2)
        self.assertEqual(RECOVERY_MINIMUM_OPPOSED, 1)

    def test_signals_not_evaluable_below_minimum_events(self):
        # Even a stream shaped like a recovery case cannot fire any
        # branch below 27 events: the learner acts through a fit on
        # all available events and does not abstain or recover.
        m = fed(RECOVERY_ROWS[:MINIMUM_EVENTS - 1])
        decision, model = m.selection()
        self.assertFalse(decision["gate_evaluable"])
        self.assertFalse(decision["abstained"])
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "all_available_below_minimum")
        self.assertEqual(decision["signal_events"], [])
        self.assertEqual(decision["archive_events"], [])
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
        self.assertEqual(decision["archive_events_count"], 1)
        self.assertEqual(len(model.events), 1)

    def test_empty_memory_selection_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceOppositionRecoveryMemory().selection()
        with self.assertRaises(ValueError):
            EvidenceOppositionRecoveryMemory().record()

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
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["matched_count"], 2)
        self.assertEqual(decision["concordant_count"], 2)
        self.assertEqual(decision["archive_matched_count"], 2)
        self.assertTrue(decision["recovery_fired"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "retained_archive")
        self.assertEqual(decision["source"], "retained_archive")
        self.assertEqual(decision["archive_events_count"], 10)
        self.assertEqual(decision["learner_training_actions"], 0)
        # The recovery model is fitted on the archive events ONLY:
        # no reference-window or newest-window events are included.
        self.assertEqual(model.events, [dict(r) for r in RECOVERY_ROWS[:10]])
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(m.choose(frame),
                         plain_model(RECOVERY_ROWS[:10]).choose(frame))

    def test_recovery_takes_priority_over_abstention(self):
        # opposed_count == 2 would abstain under the guard; with both
        # events archive-concordant the recovery branch comes first.
        decision, _ = fed(RECOVERY_ROWS).selection()
        self.assertEqual(decision["opposed_count"], GATE_OPPOSED_COUNT)
        self.assertTrue(decision["recovery_fired"])
        self.assertFalse(decision["abstained"])
        self.assertFalse(decision["gate_fired"])

    def test_recovery_fires_with_single_opposed_event(self):
        # Span 5: opposed + concordant. Span 3: reference and archive
        # both progress, newest progress -> concordant, not opposed.
        # opposed_count == 1 with concordant_count == 2 still recovers.
        archive = ([row("progress") for _ in range(6)]
                   + [row("progress", span=3) for _ in range(6)])
        reference = ([row("damage") for _ in range(12)]
                     + [row("progress", span=3) for _ in range(12)])
        rows = archive + reference + [row("progress"),
                                      row("progress", span=3)]
        decision, model = fed(rows).selection()
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["concordant_count"], 2)
        self.assertTrue(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "retained_archive")
        self.assertEqual(len(model.events), len(archive))

    def test_no_recovery_without_any_opposition(self):
        # Stationary progress: both newest events are archive-
        # concordant but opposed_count == 0, so the learner must act
        # through recent8 exactly, not through the archive.
        rows = [row("progress") for _ in range(40)]
        m = fed(rows)
        decision, model = m.selection()
        self.assertEqual(decision["concordant_count"], 2)
        self.assertEqual(decision["opposed_count"], 0)
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(len(model.events), ACTING_WINDOW)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(m.choose(frame),
                         plain_model(rows[-ACTING_WINDOW:]).choose(frame))

    def test_single_concordant_event_does_not_recover(self):
        # Newest 1: progress (opposed to damage reference, concordant
        # with progress archive). Newest 2: damage (concordant with
        # the reference, opposed to the archive). concordant == 1,
        # opposed == 1 -> neither recovery nor abstention: recent8.
        rows = ([row("progress") for _ in range(10)]
                + [row("damage") for _ in range(24)]
                + [row("progress"), row("damage")])
        decision, model = fed(rows).selection()
        self.assertEqual(decision["concordant_count"], 1)
        self.assertEqual(decision["opposed_count"], 1)
        self.assertFalse(decision["recovery_fired"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(len(model.events), ACTING_WINDOW)

    def test_abstention_when_opposed_without_concordance(self):
        m = fed(ABSTAIN_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["concordant_count"], 0)
        self.assertEqual(decision["archive_matched_count"], 2)
        self.assertFalse(decision["recovery_fired"])
        self.assertTrue(decision["abstained"])
        self.assertTrue(decision["gate_fired"])
        self.assertEqual(decision["branch"], "abstained")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(m.choose(frame))
        self.assertEqual(m.record()["state"]["events"],
                         [dict(r) for r in ABSTAIN_ROWS])

    def test_neutral_newest_event_is_never_concordant_or_opposed(self):
        rows = ([row("progress") for _ in range(10)]
                + [row("damage") for _ in range(24)]
                + [row("progress"), row("neutral")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["archive_events"][1],
                         {"span": 5, "reported_class": "neutral",
                          "archive_count": 10,
                          "archive_majority": "progress",
                          "archive_matched": False,
                          "archive_concordant": False})
        self.assertEqual(decision["concordant_count"], 1)
        self.assertFalse(decision["recovery_fired"])

    def test_tied_archive_majority_gives_no_expectation(self):
        rows = ([row("progress") for _ in range(5)]
                + [row("damage") for _ in range(5)]
                + [row("damage") for _ in range(24)]
                + [row("progress"), row("progress")])
        decision, _ = fed(rows).selection()
        for rec in decision["archive_events"]:
            self.assertEqual(rec["archive_count"], 10)
            self.assertIsNone(rec["archive_majority"])
            self.assertFalse(rec["archive_matched"])
            self.assertFalse(rec["archive_concordant"])
        self.assertFalse(decision["recovery_fired"])
        # Both newest events are still opposed -> abstention branch.
        self.assertTrue(decision["abstained"])

    def test_span_absent_from_archive_is_unmatched(self):
        rows = ([row("progress") for _ in range(10)]
                + [row("damage") for _ in range(24)]
                + [row("progress", span=9), row("progress")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["archive_events"][0],
                         {"span": 9, "reported_class": "progress",
                          "archive_count": 0, "archive_majority": None,
                          "archive_matched": False,
                          "archive_concordant": False})
        self.assertEqual(decision["concordant_count"], 1)
        self.assertFalse(decision["recovery_fired"])

    def test_archive_is_span_specific(self):
        archive = ([row("progress") for _ in range(6)]
                   + [row("damage", span=3) for _ in range(6)])
        reference = ([row("damage") for _ in range(12)]
                     + [row("progress", span=3) for _ in range(12)])
        rows = archive + reference + [row("progress"),
                                      row("damage", span=3)]
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["archive_events"][0]["archive_count"], 6)
        self.assertEqual(decision["archive_events"][0]
                         ["archive_majority"], "progress")
        self.assertEqual(decision["archive_events"][1]["archive_count"], 6)
        self.assertEqual(decision["archive_events"][1]
                         ["archive_majority"], "damage")
        self.assertEqual(decision["concordant_count"], 2)
        self.assertEqual(decision["opposed_count"], 2)
        self.assertTrue(decision["recovery_fired"])

    def test_archive_excludes_reference_and_newest_windows(self):
        # Only the 2 pre-reference progress events form the archive;
        # the 24 damage reference events must not dilute it.
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
        restored = EvidenceOppositionRecoveryMemory.restore(
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
        restored = EvidenceOppositionRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertTrue(restored.selection()[0]["recovery_fired"])
        self.assertEqual(restored.selection()[0]["archive_events"],
                         m.selection()[0]["archive_events"])
        self.assertEqual(restored.selection()[0]["signal_events"],
                         m.selection()[0]["signal_events"])

    def test_reject_invalid_events_without_partial_write(self):
        m = EvidenceOppositionRecoveryMemory()
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
            EvidenceOppositionRecoveryMemory.restore(bad)
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            EvidenceOppositionRecoveryMemory.restore(bad)
        bad2 = copy.deepcopy(saved)
        bad2["state"]["schema"] = "developmental-ai.other/v1"
        bad2["sha256"] = digest(bad2["state"])
        with self.assertRaises(ValueError):
            EvidenceOppositionRecoveryMemory.restore(bad2)

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
