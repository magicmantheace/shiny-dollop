"""Frozen-protocol unit tests for LongDisagreementJointRecoveryMemory.

Protocol: benchmarks/long_disagreement_joint_recovery_protocol.json.
These tests use only handcrafted synthetic events and the ALREADY
INSPECTED stochastic cohort seed 212003 (frame/source shape only).
The frozen cohorts of this experiment (352003-family / 353001-family)
are never touched here: no cohort scores are viewed or run before or
during implementation.
"""
from __future__ import annotations

import copy
import unittest

from developmental_ai.bounded_authority_joint_recovery import (
    BoundedAuthorityJointRecoveryMemory,
)
from developmental_ai.long_disagreement_joint_recovery import (
    LongDisagreementJointRecoveryMemory, SCHEMA, ACTING_WINDOW,
    NEWEST_WINDOW, REFERENCE_WINDOW, LOCAL_WINDOW, PRECEDING_WINDOW,
    MINIMUM_EVENTS, GATE_OPPOSED_COUNT, RECOVERY_JOINT_COUNT,
    RECENT_CONCORDANT_THRESHOLD,
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
    m = LongDisagreementJointRecoveryMemory()
    for r in rows:
        m.observe(r)
    return m


def plain_model(rows):
    m = RelationOutcomeMemory()
    for r in rows:
        m.observe(r)
    return m


# Long disagreement: archive majority progress (30 progress head plus
# the 26-event damage preceding segment still leaves 30 vs 26), the
# preceding window is entirely damage, and the local window is damage
# with ONE joint newest event. Both disagreement flags are set, so
# recovery is armed through the LONG leg even though
# recent_concordant_count == 1 - the exact profile at which the graded
# bounded candidate is disarmed on these same rows.
LONG_RECOVERY_ROWS = ([row("progress") for _ in range(30)]
                      + [row("damage") for _ in range(26)]
                      + [row("damage") for _ in range(24)]
                      + [row("progress"), row("damage")])

# Late single flip-back: a large progress archive, a long damage
# segment, and ONE joint newest event. The preceding window is
# dominated by the archive-rule segment (progress majority), so the
# long leg does NOT arm; with recent_concordant_count == 1 recovery
# stays disarmed, exactly as in the graded bounded candidate.
DISARMED_RECOVERY_ROWS = ([row("progress") for _ in range(100)]
                          + [row("damage") for _ in range(32)]
                          + [row("progress"), row("damage")])

# Corroboration still arms: archive (10 progress) + reference
# (24 damage) + newest (2 progress). Only 36 events, so the preceding
# window is partial (10 events) and agrees with the archive; the long
# leg is unset and recovery fires through corroboration (count 2).
CORROBORATION_ROWS = ([row("progress") for _ in range(10)]
                      + [row("damage") for _ in range(24)]
                      + [row("progress"), row("progress")])

# Archive and reference agree (progress); newest both damage: no
# stable disagreement, abstention armed, joint 0 -> abstain.
ABSTAIN_ROWS = ([row("progress") for _ in range(10)]
                + [row("progress") for _ in range(24)]
                + [row("damage"), row("damage")])

# Long disagreement with an abstention trigger: stable disagreement
# is carried by spans 3 and 7 in BOTH the preceding and local windows
# (long flag set), while the newest span-5 events are opposed
# (damage vs progress reference) but not archive-concordant. The long
# leg arms RECOVERY only; abstention remains disarmed by design.
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

# Preceding strict-majority boundary: preceding spans 3 and 7 are
# both comparable, only span 3 disagrees (C2 == 2, D2 == 1), so
# D2 * 2 > C2 is false and the preceding flag is NOT set; the long
# leg cannot arm and the single joint event stays disarmed.
PRECEDING_BOUNDARY_ROWS = (
    [row("progress") for _ in range(20)]
    + [row("progress", span=3) for _ in range(20)]
    + [row("progress", span=7) for _ in range(20)]
    + [row("damage", span=3) for _ in range(13)]
    + [row("progress", span=7) for _ in range(13)]
    + [row("damage") for _ in range(24)]
    + [row("progress"), row("damage")])


class LongDisagreementJointRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = STOCHASTIC_DEV[0]
        cls.source, cls.cost = public_train(cls.seed, "original", 1000, 240)

    def test_frozen_parameters_match_protocol(self):
        self.assertEqual(ACTING_WINDOW, 8)
        self.assertEqual(NEWEST_WINDOW, 2)
        self.assertEqual(REFERENCE_WINDOW, 24)
        self.assertEqual(LOCAL_WINDOW, 26)
        self.assertEqual(LOCAL_WINDOW, NEWEST_WINDOW + REFERENCE_WINDOW)
        self.assertEqual(PRECEDING_WINDOW, 26)
        self.assertEqual(PRECEDING_WINDOW, LOCAL_WINDOW)
        self.assertEqual(MINIMUM_EVENTS, 27)
        self.assertEqual(MINIMUM_EVENTS,
                         NEWEST_WINDOW + REFERENCE_WINDOW + 1)
        self.assertEqual(GATE_OPPOSED_COUNT, 2)
        self.assertEqual(RECOVERY_JOINT_COUNT, 1)
        self.assertEqual(RECENT_CONCORDANT_THRESHOLD, 2)

    def test_signals_not_evaluable_below_minimum_events(self):
        m = fed(LONG_RECOVERY_ROWS[:MINIMUM_EVENTS - 1])
        decision, model = m.selection()
        self.assertFalse(decision["gate_evaluable"])
        self.assertFalse(decision["abstained"])
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "all_available_below_minimum")
        self.assertEqual(decision["signal_events"], [])
        self.assertEqual(decision["archive_events"], [])
        self.assertEqual(decision["joint_events"], [])
        self.assertEqual(decision["expiry_spans"], [])
        self.assertEqual(decision["preceding_spans"], [])
        self.assertEqual(decision["recent_events"], [])
        self.assertFalse(decision["stable_disagreement"])
        self.assertFalse(decision["preceding_stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])
        self.assertFalse(decision["recovery_armed"])
        self.assertEqual(decision["recovery_arming_leg"], "none")
        self.assertFalse(decision["abstention_armed"])
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
        # Partial preceding window: the single archive event, agreeing
        # with the archive, so the preceding and long flags are unset;
        # recovery fires through corroboration as in the bounded case.
        self.assertEqual(decision["preceding_spans"], [
            {"span": 5, "preceding_count": 1,
             "preceding_majority": "progress", "archive_count": 1,
             "archive_majority": "progress",
             "preceding_comparable": True,
             "preceding_disagreeing": False},
        ])
        self.assertFalse(decision["preceding_stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])
        self.assertTrue(decision["stable_disagreement"])
        self.assertEqual(decision["recovery_arming_leg"], "corroboration")
        self.assertTrue(decision["recovery_fired"])
        self.assertEqual(decision["archive_events_count"], 1)
        self.assertEqual(len(model.events), 1)

    def test_empty_memory_selection_rejected(self):
        with self.assertRaises(ValueError):
            LongDisagreementJointRecoveryMemory().selection()
        with self.assertRaises(ValueError):
            LongDisagreementJointRecoveryMemory().record()

    def test_recovery_fires_via_long_leg_exact_records(self):
        m = fed(LONG_RECOVERY_ROWS)
        decision, model = m.selection()
        self.assertTrue(decision["gate_evaluable"])
        self.assertEqual(decision["joint_count"], 1)
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["comparable_span_count"], 1)
        self.assertEqual(decision["disagreeing_span_count"], 1)
        self.assertTrue(decision["stable_disagreement"])
        self.assertEqual(decision["preceding_spans"], [
            {"span": 5, "preceding_count": 26,
             "preceding_majority": "damage", "archive_count": 56,
             "archive_majority": "progress",
             "preceding_comparable": True,
             "preceding_disagreeing": True},
        ])
        self.assertEqual(decision["preceding_comparable_span_count"], 1)
        self.assertEqual(decision["preceding_disagreeing_span_count"], 1)
        self.assertTrue(decision["preceding_stable_disagreement"])
        self.assertTrue(decision["long_disagreement"])
        self.assertEqual(decision["recent_concordant_count"], 1)
        self.assertTrue(decision["recovery_armed"])
        self.assertEqual(decision["recovery_arming_leg"], "long")
        self.assertFalse(decision["abstention_armed"])
        self.assertTrue(decision["recovery_would_fire"])
        self.assertFalse(decision["abstention_would_fire"])
        self.assertTrue(decision["recovery_fired"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "retained_archive")
        self.assertEqual(decision["source"], "retained_archive")
        self.assertEqual(decision["archive_events_count"], 56)
        self.assertEqual(decision["learner_training_actions"], 0)
        self.assertEqual(model.events,
                         [dict(r) for r in LONG_RECOVERY_ROWS[:56]])
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(m.choose(frame),
                         plain_model(LONG_RECOVERY_ROWS[:56]).choose(frame))

    def test_long_leg_restores_what_bounded_candidate_starves(self):
        # The discriminating comparison: identical rows, identical
        # recorded profile (joint 1, recent_concordant 1, stable set);
        # the graded bounded candidate is disarmed, this candidate
        # recovers through the long leg alone.
        bounded = BoundedAuthorityJointRecoveryMemory()
        for r in LONG_RECOVERY_ROWS:
            bounded.observe(r)
        bounded_decision, _ = bounded.selection()
        self.assertTrue(bounded_decision["stable_disagreement"])
        self.assertEqual(bounded_decision["recent_concordant_count"], 1)
        self.assertFalse(bounded_decision["recovery_armed"])
        self.assertFalse(bounded_decision["recovery_fired"])
        self.assertEqual(bounded_decision["branch"], "recent8")
        decision, _ = fed(LONG_RECOVERY_ROWS).selection()
        self.assertTrue(decision["recovery_fired"])

    def test_single_joint_event_disarmed_late(self):
        decision, model = fed(DISARMED_RECOVERY_ROWS).selection()
        self.assertEqual(decision["joint_count"], 1)
        self.assertTrue(decision["recovery_would_fire"])
        self.assertTrue(decision["stable_disagreement"])
        # Preceding window is archive-rule dominated: comparable but
        # not disagreeing, so neither preceding nor long flag sets.
        self.assertEqual(decision["preceding_spans"], [
            {"span": 5, "preceding_count": 26,
             "preceding_majority": "progress", "archive_count": 108,
             "archive_majority": "progress",
             "preceding_comparable": True,
             "preceding_disagreeing": False},
        ])
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
        # The bounded candidate agrees here: the long leg is the ONLY
        # authority difference, and it does not fire late.
        bounded = BoundedAuthorityJointRecoveryMemory()
        for r in DISARMED_RECOVERY_ROWS:
            bounded.observe(r)
        self.assertFalse(bounded.selection()[0]["recovery_fired"])

    def test_recovery_fires_via_corroboration_partial_preceding(self):
        decision, _ = fed(CORROBORATION_ROWS).selection()
        self.assertTrue(decision["stable_disagreement"])
        self.assertFalse(decision["preceding_stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])
        self.assertEqual(decision["recent_concordant_count"], 2)
        self.assertTrue(decision["recovery_armed"])
        self.assertEqual(decision["recovery_arming_leg"], "corroboration")
        self.assertEqual(decision["joint_count"], 2)
        self.assertTrue(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "retained_archive")

    def test_recovery_armed_without_stable_disagreement(self):
        # No comparable local span (C == 0), so the stable flag cannot
        # set; recent_concordant is only 1 and the long flag is unset,
        # so recovery is armed SOLELY by the absence of stable
        # disagreement, exactly as in the bounded candidate.
        archive = ([row("progress") for _ in range(10)]
                   + [row("progress", span=3) for _ in range(5)]
                   + [row("damage", span=3) for _ in range(5)])
        reference = ([row("damage")]
                     + [row("progress", span=3) for _ in range(23)])
        rows = archive + reference + [row("progress"), row("neutral")]
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["comparable_span_count"], 0)
        self.assertFalse(decision["stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])
        self.assertEqual(decision["recent_concordant_count"], 1)
        self.assertTrue(decision["recovery_armed"])
        self.assertEqual(decision["recovery_arming_leg"],
                         "no_stable_disagreement")
        self.assertTrue(decision["abstention_armed"])
        self.assertEqual(decision["joint_count"], 1)
        self.assertTrue(decision["recovery_fired"])

    def test_long_leg_does_not_rearm_abstention(self):
        decision, model = fed(LONG_ABSTAIN_DISARMED_ROWS).selection()
        self.assertTrue(decision["stable_disagreement"])
        self.assertTrue(decision["preceding_stable_disagreement"])
        self.assertTrue(decision["long_disagreement"])
        self.assertEqual(decision["preceding_comparable_span_count"], 2)
        self.assertEqual(decision["preceding_disagreeing_span_count"], 2)
        self.assertTrue(decision["recovery_armed"])
        self.assertEqual(decision["recovery_arming_leg"], "long")
        self.assertEqual(decision["joint_count"], 0)
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["opposed_count"], 2)
        self.assertTrue(decision["abstention_would_fire"])
        self.assertFalse(decision["abstention_armed"])
        self.assertFalse(decision["abstained"])
        self.assertFalse(decision["gate_fired"])
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
        # The preceding window is a subset of the archive it is
        # compared against (the protocol's recorded self-inclusion
        # bias, accepted uncorrected): a span appearing ONLY in the
        # preceding window still has those very events in the
        # archive, so its archive majority equals its preceding
        # majority and the span is comparable but NOT disagreeing -
        # the bias runs against the long flag, as preregistered.
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
        # The preceding records must be scored against events[:N-26]
        # only, and the preceding window must hold exactly the 26
        # events before the local window: at N == 82 its per-span
        # counts sum to 26 and its archive counts equal the archive's.
        decision, _ = fed(LONG_RECOVERY_ROWS).selection()
        self.assertEqual(
            sum(r["preceding_count"] for r in decision["preceding_spans"]),
            PRECEDING_WINDOW)
        for rec in decision["preceding_spans"]:
            self.assertEqual(rec["archive_count"], 56)
            self.assertEqual(rec["archive_majority"], "progress")
        self.assertEqual(decision["preceding_window_events"],
                         PRECEDING_WINDOW)
        self.assertEqual(decision["local_window_events"], LOCAL_WINDOW)

    def test_abstains_when_armed_as_bounded_candidate(self):
        m = fed(ABSTAIN_ROWS)
        decision, _ = m.selection()
        self.assertFalse(decision["stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])
        self.assertTrue(decision["abstention_armed"])
        self.assertEqual(decision["recovery_arming_leg"],
                         "no_stable_disagreement")
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["joint_count"], 0)
        self.assertTrue(decision["abstained"])
        self.assertTrue(decision["gate_fired"])
        self.assertEqual(decision["branch"], "abstained")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(m.choose(frame))

    def test_local_strict_majority_boundary_unchanged(self):
        # Carried-over leg (A): C == 2, D == 1 is NOT stable.
        archive = ([row("progress") for _ in range(10)]
                   + [row("progress", span=3) for _ in range(10)])
        reference = ([row("progress") for _ in range(12)]
                     + [row("damage", span=3) for _ in range(12)])
        rows = archive + reference + [row("progress"), row("progress")]
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["comparable_span_count"], 2)
        self.assertEqual(decision["disagreeing_span_count"], 1)
        self.assertFalse(decision["stable_disagreement"])
        self.assertTrue(decision["abstention_armed"])

    def test_stationary_stream_matches_recent8(self):
        rows = [row("progress") for _ in range(40)]
        m = fed(rows)
        decision, model = m.selection()
        self.assertFalse(decision["stable_disagreement"])
        self.assertFalse(decision["preceding_stable_disagreement"])
        self.assertFalse(decision["long_disagreement"])
        self.assertEqual(decision["joint_count"], 0)
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(len(model.events), ACTING_WINDOW)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(m.choose(frame),
                         plain_model(rows[-ACTING_WINDOW:]).choose(frame))

    def test_neutral_newest_event_is_never_joint(self):
        rows = ([row("progress") for _ in range(10)]
                + [row("damage") for _ in range(24)]
                + [row("neutral"), row("neutral")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["joint_flags"], [False, False])
        self.assertEqual(decision["joint_count"], 0)
        self.assertFalse(decision["recovery_would_fire"])
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "recent8")

    def test_no_fitted_probability_fields_in_decision(self):
        decision, _ = fed(LONG_RECOVERY_ROWS).selection()
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
        restored = LongDisagreementJointRecoveryMemory.restore(
            copy.deepcopy(saved))
        frame = StochasticWorld(self.seed, "test", 160000,
                                "reversed").frame()
        self.assertEqual(m.choose(frame), restored.choose(frame))
        self.assertEqual(m.selection()[0], restored.selection()[0])
        self.assertEqual(m.record(), saved)
        self.assertEqual(restored.record(), saved)
        self.assertFalse(hasattr(m, "step"))

    def test_replay_reproduces_long_decision(self):
        m = fed(LONG_RECOVERY_ROWS)
        saved = m.record()
        restored = LongDisagreementJointRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["preceding_spans"],
                         m.selection()[0]["preceding_spans"])
        self.assertTrue(restored.selection()[0]["long_disagreement"])
        self.assertEqual(restored.selection()[0]["recovery_arming_leg"],
                         "long")
        self.assertTrue(restored.selection()[0]["recovery_fired"])

    def test_reject_invalid_events_without_partial_write(self):
        m = LongDisagreementJointRecoveryMemory()
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
            LongDisagreementJointRecoveryMemory.restore(bad)
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            LongDisagreementJointRecoveryMemory.restore(bad)
        bad2 = copy.deepcopy(saved)
        bad2["state"]["schema"] = "developmental-ai.other/v1"
        bad2["sha256"] = digest(bad2["state"])
        with self.assertRaises(ValueError):
            LongDisagreementJointRecoveryMemory.restore(bad2)

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
