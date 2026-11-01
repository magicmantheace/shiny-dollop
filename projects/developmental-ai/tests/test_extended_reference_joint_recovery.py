"""Frozen-protocol unit tests for ExtendedReferenceJointRecoveryMemory.

Protocol: benchmarks/extended_reference_joint_recovery_protocol.json.
These tests use only handcrafted synthetic events and the ALREADY
INSPECTED stochastic cohort seed 212003 (frame/source shape only).
The frozen cohorts of this experiment (362003-family / 363001-family)
are never touched here: no cohort scores are viewed or run before or
during implementation.
"""
from __future__ import annotations

import copy
import unittest

from developmental_ai.extended_reference_joint_recovery import (
    ExtendedReferenceJointRecoveryMemory, SCHEMA, ACTING_WINDOW,
    NEWEST_WINDOW, REFERENCE_WINDOW, LEGACY_REFERENCE_WINDOW,
    ARCHIVE_PARTITION, LOCAL_WINDOW, PRECEDING_WINDOW,
    MINIMUM_EVENTS, GATE_OPPOSED_COUNT, RECOVERY_JOINT_COUNT,
    RECENT_CONCORDANT_THRESHOLD,
)
from developmental_ai.long_disagreement_joint_recovery import (
    LongDisagreementJointRecoveryMemory,
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
    m = ExtendedReferenceJointRecoveryMemory()
    for r in rows:
        m.observe(r)
    return m


def plain_model(rows):
    m = RelationOutcomeMemory()
    for r in rows:
        m.observe(r)
    return m


# Extended-reference recovery, DISCRIMINATING vs the graded long
# candidate: the 24-event legacy reference is progress-majority
# (18 progress + 6 damage), so the newest progress event is
# legacy-matched-but-not-opposed and the long candidate's joint
# count is 0; the 50-event reference adds the 26-event damage
# segment before it (32 damage vs 18 progress), so the same event
# IS opposed, archive-concordant, and joint. recent_concordant is
# exactly 1 and there is no stable disagreement, so recovery is
# armed SOLELY by the absence of stable disagreement.
EXTENDED_RECOVERY_ROWS = ([row("progress") for _ in range(48)]
                          + [row("damage") for _ in range(26)]
                          + [row("progress") for _ in range(18)]
                          + [row("damage") for _ in range(6)]
                          + [row("progress"), row("damage")])

# Extended-reference abstention, DISCRIMINATING vs the graded long
# candidate: the archive span majority is neutral (48 neutral head;
# the preceding progress segment is archive-counted but not a
# majority), so the newest damage events are not archive-matched
# and joint stays 0. The legacy reference is damage-majority, so
# the long candidate records opposed 0; the 50-event reference is
# progress-majority (26 preceding progress + 4), so both newest
# events are opposed and the armed abstention branch fires.
EXTENDED_ABSTAIN_ROWS = ([row("neutral") for _ in range(48)]
                         + [row("progress") for _ in range(26)]
                         + [row("damage") for _ in range(20)]
                         + [row("progress") for _ in range(4)]
                         + [row("damage"), row("damage")])

# The graded long candidate's long-leg recovery rows, carried over:
# under the extended reference the signal and legacy records AGREE
# (both references damage-majority) and recovery fires via the long
# leg exactly as in the graded long candidate.
LONG_RECOVERY_ROWS = ([row("progress") for _ in range(30)]
                      + [row("damage") for _ in range(26)]
                      + [row("damage") for _ in range(24)]
                      + [row("progress"), row("damage")])

# Late single flip-back: a large progress archive, a long damage
# segment, and ONE joint newest event; the preceding window is
# archive-rule dominated, so no authority leg arms recovery.
DISARMED_RECOVERY_ROWS = ([row("progress") for _ in range(100)]
                          + [row("damage") for _ in range(32)]
                          + [row("progress"), row("damage")])

# Corroboration still arms: stable disagreement set, preceding
# window split (C2 == 2, D2 == 1, not stable, so no long leg), and
# recent_concordant_count == 2 with joint_count == 2.
CORROBORATION_ROWS = ([row("progress") for _ in range(8)]
                      + [row("progress", span=3) for _ in range(20)]
                      + [row("damage") for _ in range(6)]
                      + [row("damage") for _ in range(24)]
                      + [row("progress"), row("progress")])

# Archive and extended reference agree (progress); newest both
# damage: no stable disagreement, abstention armed, joint 0.
ABSTAIN_ROWS = ([row("progress") for _ in range(10)]
                + [row("progress") for _ in range(50)]
                + [row("damage"), row("damage")])

# Long disagreement with an abstention trigger (graded long rows):
# the long leg arms RECOVERY only; abstention remains disarmed.
LONG_ABSTAIN_DISARMED_ROWS = (
    [row("progress") for _ in range(20)]
    + [row("progress", span=3) for _ in range(20)]
    + [row("progress", span=7) for _ in range(20)]
    + [row("damage", span=3) for _ in range(13)]
    + [row("damage", span=7) for _ in range(13)]
    + [row("progress") for _ in range(8)]
    + [row("damage", span=3) for _ in range(8)]
    + [row("damage", span=7) for _ in range(8)]
    + [row("damage"), row("damage")])

# Preceding strict-majority boundary (graded long rows): C2 == 2,
# D2 == 1, so D2 * 2 > C2 is false, the preceding flag is NOT set,
# and the single joint event stays disarmed.
PRECEDING_BOUNDARY_ROWS = (
    [row("progress") for _ in range(20)]
    + [row("progress", span=3) for _ in range(20)]
    + [row("progress", span=7) for _ in range(20)]
    + [row("damage", span=3) for _ in range(13)]
    + [row("progress", span=7) for _ in range(13)]
    + [row("damage") for _ in range(24)]
    + [row("progress"), row("damage")])


class ExtendedReferenceJointRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = STOCHASTIC_DEV[0]
        cls.source, cls.cost = public_train(cls.seed, "original", 1000, 240)

    def test_frozen_parameters_match_protocol(self):
        self.assertEqual(ACTING_WINDOW, 8)
        self.assertEqual(NEWEST_WINDOW, 2)
        self.assertEqual(REFERENCE_WINDOW, 50)
        self.assertEqual(LEGACY_REFERENCE_WINDOW, 24)
        self.assertEqual(ARCHIVE_PARTITION, 26)
        self.assertEqual(ARCHIVE_PARTITION,
                         NEWEST_WINDOW + LEGACY_REFERENCE_WINDOW)
        self.assertEqual(LOCAL_WINDOW, 26)
        self.assertEqual(LOCAL_WINDOW, ARCHIVE_PARTITION)
        self.assertEqual(PRECEDING_WINDOW, 26)
        self.assertEqual(MINIMUM_EVENTS, 52)
        self.assertEqual(MINIMUM_EVENTS,
                         NEWEST_WINDOW + REFERENCE_WINDOW)
        self.assertEqual(GATE_OPPOSED_COUNT, 2)
        self.assertEqual(RECOVERY_JOINT_COUNT, 1)
        self.assertEqual(RECENT_CONCORDANT_THRESHOLD, 2)

    def test_signals_not_evaluable_below_minimum_events(self):
        m = fed(EXTENDED_RECOVERY_ROWS[:MINIMUM_EVENTS - 1])
        decision, model = m.selection()
        self.assertFalse(decision["gate_evaluable"])
        self.assertFalse(decision["abstained"])
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "all_available_below_minimum")
        self.assertEqual(decision["signal_events"], [])
        self.assertEqual(decision["legacy_signal_events"], [])
        self.assertEqual(decision["archive_events"], [])
        self.assertEqual(decision["joint_events"], [])
        self.assertEqual(decision["legacy_joint_events"], [])
        self.assertEqual(decision["legacy_joint_flags"], [])
        self.assertEqual(decision["legacy_opposed_count"], 0)
        self.assertEqual(decision["legacy_joint_count"], 0)
        self.assertEqual(decision["expiry_spans"], [])
        self.assertEqual(decision["preceding_spans"], [])
        self.assertEqual(decision["recent_events"], [])
        self.assertFalse(decision["stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])
        self.assertFalse(decision["recovery_armed"])
        self.assertEqual(decision["recovery_arming_leg"], "none")
        self.assertEqual(len(model.events), MINIMUM_EVENTS - 1)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIn(m.choose(frame),
                      {a["id"] for a in frame["actions"]})

    def test_minimum_events_exactly_is_evaluable(self):
        rows = ([row("progress") for _ in range(26)]
                + [row("damage") for _ in range(24)]
                + [row("progress"), row("progress")])
        self.assertEqual(len(rows), MINIMUM_EVENTS)
        decision, _ = fed(rows).selection()
        self.assertTrue(decision["gate_evaluable"])
        self.assertEqual(decision["archive_events_count"], 26)
        # Extended reference (all 50 preceding events: 26 progress +
        # 24 damage) is progress-majority, so neither newest event
        # is opposed; the legacy reference (24 damage) opposes both.
        self.assertEqual(decision["opposed_count"], 0)
        self.assertEqual(decision["legacy_opposed_count"], 2)
        self.assertEqual(decision["legacy_joint_count"], 2)
        self.assertEqual(decision["joint_count"], 0)
        self.assertEqual(decision["signal_events"][0]["reference_count"],
                         REFERENCE_WINDOW)
        self.assertEqual(
            decision["legacy_signal_events"][0]["reference_count"],
            LEGACY_REFERENCE_WINDOW)
        self.assertEqual(decision["preceding_spans"], [
            {"span": 5, "preceding_count": 26,
             "preceding_majority": "progress", "archive_count": 26,
             "archive_majority": "progress",
             "preceding_comparable": True,
             "preceding_disagreeing": False},
        ])
        self.assertFalse(decision["preceding_stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])

    def test_empty_memory_selection_rejected(self):
        with self.assertRaises(ValueError):
            ExtendedReferenceJointRecoveryMemory().selection()
        with self.assertRaises(ValueError):
            ExtendedReferenceJointRecoveryMemory().record()

    def test_extended_reference_recovery_exact_records(self):
        m = fed(EXTENDED_RECOVERY_ROWS)
        decision, model = m.selection()
        self.assertTrue(decision["gate_evaluable"])
        self.assertEqual(decision["signal_events"], [
            {"span": 5, "reported_class": "progress",
             "reference_count": 50, "reference_majority": "damage",
             "matched": True, "opposed": True},
            {"span": 5, "reported_class": "damage",
             "reference_count": 50, "reference_majority": "damage",
             "matched": True, "opposed": False},
        ])
        self.assertEqual(decision["legacy_signal_events"], [
            {"span": 5, "reported_class": "progress",
             "reference_count": 24, "reference_majority": "progress",
             "matched": True, "opposed": False},
            {"span": 5, "reported_class": "damage",
             "reference_count": 24, "reference_majority": "progress",
             "matched": True, "opposed": True},
        ])
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["legacy_opposed_count"], 1)
        self.assertEqual(decision["legacy_matched_count"], 2)
        self.assertEqual(decision["joint_count"], 1)
        self.assertEqual(decision["legacy_joint_count"], 0)
        self.assertEqual(decision["legacy_joint_flags"], [False, False])
        self.assertEqual(decision["concordant_count"], 1)
        self.assertFalse(decision["stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])
        self.assertEqual(decision["recent_concordant_count"], 1)
        self.assertTrue(decision["recovery_armed"])
        self.assertEqual(decision["recovery_arming_leg"],
                         "no_stable_disagreement")
        self.assertTrue(decision["recovery_fired"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "retained_archive")
        # Archive partition is the ORIGINAL 26, not the widened 52:
        # the recovery model holds exactly events[:74].
        self.assertEqual(decision["archive_events_count"], 74)
        self.assertEqual(decision["archive_partition_events"],
                         ARCHIVE_PARTITION)
        self.assertEqual(decision["learner_training_actions"], 0)
        self.assertEqual(model.events,
                         [dict(r) for r in EXTENDED_RECOVERY_ROWS[:74]])
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(
            m.choose(frame),
            plain_model(EXTENDED_RECOVERY_ROWS[:74]).choose(frame))

    def test_widened_reference_recovers_where_long_candidate_does_not(self):
        # The discriminating comparison: identical rows; the graded
        # long candidate's legacy joint count is 0 and it stays on
        # recent8, this candidate recovers through the widened
        # reference alone.
        long_m = LongDisagreementJointRecoveryMemory()
        for r in EXTENDED_RECOVERY_ROWS:
            long_m.observe(r)
        long_decision, _ = long_m.selection()
        self.assertEqual(long_decision["joint_count"], 0)
        self.assertFalse(long_decision["recovery_fired"])
        self.assertEqual(long_decision["branch"], "recent8")
        decision, _ = fed(EXTENDED_RECOVERY_ROWS).selection()
        self.assertTrue(decision["recovery_fired"])
        # The long candidate's rule is derivable from THIS
        # candidate's records alone: legacy joint 0, and the
        # authority fields agree with the long candidate's own.
        self.assertEqual(decision["legacy_joint_count"],
                         long_decision["joint_count"])
        self.assertEqual(decision["stable_disagreement"],
                         long_decision["stable_disagreement"])
        self.assertEqual(decision["recent_concordant_count"],
                         long_decision["recent_concordant_count"])

    def test_widened_reference_abstains_where_long_candidate_does_not(self):
        long_m = LongDisagreementJointRecoveryMemory()
        for r in EXTENDED_ABSTAIN_ROWS:
            long_m.observe(r)
        long_decision, _ = long_m.selection()
        self.assertEqual(long_decision["opposed_count"], 0)
        self.assertEqual(long_decision["branch"], "recent8")
        m = fed(EXTENDED_ABSTAIN_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["legacy_opposed_count"], 0)
        self.assertEqual(decision["joint_count"], 0)
        self.assertEqual(decision["archive_matched_count"], 0)
        self.assertEqual(decision["comparable_span_count"], 0)
        self.assertFalse(decision["stable_disagreement"])
        self.assertTrue(decision["abstention_armed"])
        self.assertTrue(decision["abstained"])
        self.assertTrue(decision["gate_fired"])
        self.assertEqual(decision["branch"], "abstained")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(m.choose(frame))

    def test_long_leg_recovery_carried_over_when_references_agree(self):
        m = fed(LONG_RECOVERY_ROWS)
        decision, model = m.selection()
        self.assertEqual(decision["joint_count"], 1)
        self.assertEqual(decision["legacy_joint_count"], 1)
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["legacy_opposed_count"], 1)
        self.assertEqual(decision["signal_events"][0]["reference_count"],
                         REFERENCE_WINDOW)
        self.assertTrue(decision["stable_disagreement"])
        self.assertTrue(decision["preceding_stable_disagreement"])
        self.assertTrue(decision["long_disagreement"])
        self.assertEqual(decision["recent_concordant_count"], 1)
        self.assertEqual(decision["recovery_arming_leg"], "long")
        self.assertTrue(decision["recovery_fired"])
        self.assertEqual(decision["archive_events_count"], 56)
        self.assertEqual(model.events,
                         [dict(r) for r in LONG_RECOVERY_ROWS[:56]])

    def test_single_joint_event_disarmed_late(self):
        decision, model = fed(DISARMED_RECOVERY_ROWS).selection()
        self.assertEqual(decision["joint_count"], 1)
        self.assertEqual(decision["legacy_joint_count"], 1)
        self.assertTrue(decision["recovery_would_fire"])
        self.assertTrue(decision["stable_disagreement"])
        self.assertFalse(decision["preceding_stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])
        self.assertEqual(decision["recent_concordant_count"], 1)
        self.assertFalse(decision["recovery_armed"])
        self.assertEqual(decision["recovery_arming_leg"], "none")
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "recovery_disarmed_by_expiry")
        self.assertEqual(len(model.events), ACTING_WINDOW)

    def test_recovery_fires_via_corroboration(self):
        decision, _ = fed(CORROBORATION_ROWS).selection()
        self.assertTrue(decision["stable_disagreement"])
        self.assertEqual(decision["preceding_comparable_span_count"], 2)
        self.assertEqual(decision["preceding_disagreeing_span_count"], 1)
        self.assertFalse(decision["preceding_stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])
        self.assertEqual(decision["recent_concordant_count"], 2)
        self.assertEqual(decision["recovery_arming_leg"], "corroboration")
        self.assertEqual(decision["joint_count"], 2)
        self.assertTrue(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "retained_archive")
        self.assertEqual(decision["archive_events_count"], 34)

    def test_long_leg_does_not_rearm_abstention(self):
        decision, model = fed(LONG_ABSTAIN_DISARMED_ROWS).selection()
        self.assertTrue(decision["stable_disagreement"])
        self.assertTrue(decision["preceding_stable_disagreement"])
        self.assertTrue(decision["long_disagreement"])
        self.assertEqual(decision["recovery_arming_leg"], "long")
        self.assertEqual(decision["joint_count"], 0)
        self.assertEqual(decision["legacy_joint_count"], 0)
        self.assertEqual(decision["opposed_count"], 2)
        self.assertTrue(decision["abstention_would_fire"])
        self.assertFalse(decision["abstention_armed"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "abstention_disarmed_by_expiry")
        self.assertEqual(len(model.events), ACTING_WINDOW)

    def test_preceding_strict_majority_boundary_is_not_stable(self):
        decision, _ = fed(PRECEDING_BOUNDARY_ROWS).selection()
        self.assertEqual(decision["preceding_comparable_span_count"], 2)
        self.assertEqual(decision["preceding_disagreeing_span_count"], 1)
        self.assertFalse(decision["preceding_stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])
        self.assertTrue(decision["stable_disagreement"])
        self.assertEqual(decision["recent_concordant_count"], 1)
        self.assertFalse(decision["recovery_armed"])
        self.assertEqual(decision["joint_count"], 1)
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "recent8")

    def test_preceding_tied_majority_is_not_comparable(self):
        rows = ([row("progress") for _ in range(30)]
                + [row("progress") for _ in range(13)]
                + [row("damage") for _ in range(13)]
                + [row("damage") for _ in range(24)]
                + [row("progress"), row("damage")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["preceding_spans"], [
            {"span": 5, "preceding_count": 26,
             "preceding_majority": None, "archive_count": 56,
             "archive_majority": "progress",
             "preceding_comparable": False,
             "preceding_disagreeing": False},
        ])
        self.assertEqual(decision["preceding_comparable_span_count"], 0)
        self.assertFalse(decision["preceding_stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])

    def test_preceding_window_is_self_included_in_archive(self):
        rows = ([row("progress") for _ in range(30)]
                + [row("damage", span=9) for _ in range(26)]
                + [row("damage") for _ in range(24)]
                + [row("progress"), row("damage")])
        decision, _ = fed(rows).selection()
        by_span = {r["span"]: r for r in decision["preceding_spans"]}
        self.assertEqual(by_span[9]["archive_count"], 26)
        self.assertEqual(by_span[9]["archive_majority"], "damage")
        self.assertTrue(by_span[9]["preceding_comparable"])
        self.assertFalse(by_span[9]["preceding_disagreeing"])

    def test_preceding_window_is_exactly_the_26_before_local(self):
        decision, _ = fed(LONG_RECOVERY_ROWS).selection()
        self.assertEqual(
            sum(r["preceding_count"] for r in decision["preceding_spans"]),
            PRECEDING_WINDOW)
        for rec in decision["preceding_spans"]:
            self.assertEqual(rec["archive_count"], 56)
        self.assertEqual(decision["preceding_window_events"],
                         PRECEDING_WINDOW)
        self.assertEqual(decision["local_window_events"], LOCAL_WINDOW)
        self.assertEqual(decision["reference_window_events"],
                         REFERENCE_WINDOW)
        self.assertEqual(decision["legacy_reference_window_events"],
                         LEGACY_REFERENCE_WINDOW)

    def test_abstains_when_armed(self):
        m = fed(ABSTAIN_ROWS)
        decision, _ = m.selection()
        self.assertFalse(decision["stable_disagreement"])
        self.assertTrue(decision["abstention_armed"])
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["joint_count"], 0)
        self.assertEqual(decision["archive_events_count"], 36)
        self.assertTrue(decision["abstained"])
        self.assertEqual(decision["branch"], "abstained")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(m.choose(frame))

    def test_local_strict_majority_boundary_unchanged(self):
        archive = ([row("progress") for _ in range(10)]
                   + [row("progress", span=3) for _ in range(10)])
        reference = ([row("progress") for _ in range(12)]
                     + [row("damage", span=3) for _ in range(12)])
        rows = ([row("progress") for _ in range(30)] + archive
                + reference + [row("progress"), row("progress")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["comparable_span_count"], 2)
        self.assertEqual(decision["disagreeing_span_count"], 1)
        self.assertFalse(decision["stable_disagreement"])
        self.assertTrue(decision["abstention_armed"])

    def test_stationary_stream_matches_recent8(self):
        rows = [row("progress") for _ in range(60)]
        m = fed(rows)
        decision, model = m.selection()
        self.assertFalse(decision["stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])
        self.assertEqual(decision["joint_count"], 0)
        self.assertEqual(decision["legacy_joint_count"], 0)
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(len(model.events), ACTING_WINDOW)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(m.choose(frame),
                         plain_model(rows[-ACTING_WINDOW:]).choose(frame))

    def test_neutral_newest_event_is_never_joint(self):
        rows = ([row("progress") for _ in range(30)]
                + [row("damage") for _ in range(24)]
                + [row("neutral"), row("neutral")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["joint_flags"], [False, False])
        self.assertEqual(decision["legacy_joint_flags"], [False, False])
        self.assertEqual(decision["joint_count"], 0)
        self.assertFalse(decision["recovery_would_fire"])
        self.assertEqual(decision["branch"], "recent8")

    def test_no_fitted_probability_fields_in_decision(self):
        decision, _ = fed(EXTENDED_RECOVERY_ROWS).selection()
        for key in decision:
            self.assertNotIn("probabilit", key)
            self.assertNotIn("log_score", key)
        for rec in decision["signal_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class", "reference_count",
                              "reference_majority", "matched", "opposed"})
        for rec in decision["legacy_signal_events"]:
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
        for rec in decision["legacy_joint_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class",
                              "archive_concordant", "opposed", "joint"})
        for rec in decision["expiry_spans"]:
            self.assertEqual(set(rec),
                             {"span", "local_count", "local_majority",
                              "archive_count", "archive_majority",
                              "comparable", "disagreeing"})
        for rec in decision["preceding_spans"]:
            self.assertEqual(set(rec),
                             {"span", "preceding_count",
                              "preceding_majority", "archive_count",
                              "archive_majority", "preceding_comparable",
                              "preceding_disagreeing"})
        for rec in decision["recent_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class", "archive_count",
                              "archive_majority", "archive_matched",
                              "archive_concordant"})

    def test_new_feedback_invalidates_cached_selection(self):
        m = fed([row("progress") for _ in range(55)])
        old = m.selection()
        self.assertIs(old, m.selection())
        m.observe(row("progress"))
        new = m.selection()
        self.assertIsNot(new, old)
        self.assertEqual(new[0]["recorded_events"], 56)

    def test_replay_exact_and_choice_read_only(self):
        m = fed(self.source)
        for r in public_train(self.seed, "reversed", 2000, 8)[0]:
            m.observe(r)
        saved = m.record()
        restored = ExtendedReferenceJointRecoveryMemory.restore(
            copy.deepcopy(saved))
        frame = StochasticWorld(self.seed, "test", 160000,
                                "reversed").frame()
        self.assertEqual(m.choose(frame), restored.choose(frame))
        self.assertEqual(m.selection()[0], restored.selection()[0])
        self.assertEqual(m.record(), saved)
        self.assertEqual(restored.record(), saved)
        self.assertFalse(hasattr(m, "step"))

    def test_replay_reproduces_extended_decision(self):
        m = fed(EXTENDED_RECOVERY_ROWS)
        saved = m.record()
        restored = ExtendedReferenceJointRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["legacy_joint_count"], 0)
        self.assertEqual(restored.selection()[0]["joint_count"], 1)
        self.assertTrue(restored.selection()[0]["recovery_fired"])

    def test_reject_invalid_events_without_partial_write(self):
        m = ExtendedReferenceJointRecoveryMemory()
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
            ExtendedReferenceJointRecoveryMemory.restore(bad)
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            ExtendedReferenceJointRecoveryMemory.restore(bad)
        bad2 = copy.deepcopy(saved)
        bad2["state"]["schema"] = "developmental-ai.other/v1"
        bad2["sha256"] = digest(bad2["state"])
        with self.assertRaises(ValueError):
            ExtendedReferenceJointRecoveryMemory.restore(bad2)

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
