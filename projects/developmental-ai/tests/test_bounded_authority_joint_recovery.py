"""Frozen-protocol unit tests for BoundedAuthorityJointRecoveryMemory.

Protocol: benchmarks/bounded_authority_joint_recovery_protocol.json.
These tests use only handcrafted synthetic events and the ALREADY
INSPECTED stochastic cohort seed 212003 (frame/source shape only).
The frozen cohorts of this experiment (342003-family / 343001-family)
are never touched here: no cohort scores are viewed or run before or
during implementation.
"""
from __future__ import annotations

import copy
import unittest

from developmental_ai.bounded_authority_joint_recovery import (
    BoundedAuthorityJointRecoveryMemory, SCHEMA, ACTING_WINDOW,
    NEWEST_WINDOW, REFERENCE_WINDOW, LOCAL_WINDOW, MINIMUM_EVENTS,
    GATE_OPPOSED_COUNT, RECOVERY_JOINT_COUNT,
    RECENT_CONCORDANT_THRESHOLD,
)
from developmental_ai.joint_concordance_recovery import (
    JointConcordanceRecoveryMemory,
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
    m = BoundedAuthorityJointRecoveryMemory()
    for r in rows:
        m.observe(r)
    return m


def plain_model(rows):
    m = RelationOutcomeMemory()
    for r in rows:
        m.observe(r)
    return m


# Archive (10 progress) + reference (24 damage) + newest (2 progress),
# all at span 5: both newest events are joint. Local window majority
# (damage) disagrees with the archive (progress) on the only span, so
# stable_disagreement is set; but the last 8 carry exactly the 2
# newest archive-concordant events, so recovery stays armed through
# corroboration and fires; abstention is disarmed by design.
RECOVERY_ROWS = ([row("progress") for _ in range(10)]
                 + [row("damage") for _ in range(24)]
                 + [row("progress"), row("progress")])

# Archive (10 progress) + reference (24 progress) + newest (2 damage):
# local and archive agree (progress), no stable disagreement, both
# branches armed; joint 0, opposed 2 -> abstain, as the joint gate.
ABSTAIN_ROWS = ([row("progress") for _ in range(10)]
                + [row("progress") for _ in range(24)]
                + [row("damage"), row("damage")])

# Late single flip-back: a large progress archive, a long damage
# segment, and a newest window with ONE joint event (progress) plus
# one damage event. Local majority (damage) disagrees with the
# archive on the only comparable span -> stable disagreement; the
# last 8 contain only that 1 archive-concordant event (< 2), so
# recovery is DISARMED despite joint_count == 1. The unexpired joint
# candidate recovers on these exact rows; this candidate must not.
DISARMED_RECOVERY_ROWS = ([row("progress") for _ in range(100)]
                          + [row("damage") for _ in range(32)]
                          + [row("progress"), row("damage")])

# Abstention disarmed: stable disagreement carried by spans 3 and 7
# (local damage vs archive progress), while the newest span-5 events
# are opposed (damage vs progress reference) but not concordant.
# opposed_count == 2 would fire, but abstention is disarmed, and
# joint_count == 0, so the learner acts through recent8.
DISARMED_ABSTAIN_ROWS = (
    [row("progress") for _ in range(20)]
    + [row("progress", span=3) for _ in range(20)]
    + [row("progress", span=7) for _ in range(20)]
    + [row("progress") for _ in range(8)]
    + [row("damage", span=3) for _ in range(8)]
    + [row("damage", span=7) for _ in range(8)]
    + [row("damage"), row("damage")])


class BoundedAuthorityJointRecoveryTests(unittest.TestCase):
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
        self.assertEqual(MINIMUM_EVENTS, 27)
        self.assertEqual(MINIMUM_EVENTS,
                         NEWEST_WINDOW + REFERENCE_WINDOW + 1)
        self.assertEqual(GATE_OPPOSED_COUNT, 2)
        self.assertEqual(RECOVERY_JOINT_COUNT, 1)
        self.assertEqual(RECENT_CONCORDANT_THRESHOLD, 2)

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
        self.assertEqual(decision["expiry_spans"], [])
        self.assertEqual(decision["recent_events"], [])
        self.assertFalse(decision["stable_disagreement"])
        self.assertFalse(decision["recovery_armed"])
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
        # Archive has the single progress event; local span-5 majority
        # is damage (disagreement, C=1 D=1), and the last 8 hold the 2
        # newest concordant events, so recovery is armed and fires.
        self.assertTrue(decision["stable_disagreement"])
        self.assertEqual(decision["recent_concordant_count"], 2)
        self.assertTrue(decision["recovery_armed"])
        self.assertTrue(decision["recovery_fired"])
        self.assertEqual(decision["joint_count"], 2)
        self.assertEqual(decision["archive_events_count"], 1)
        self.assertEqual(len(model.events), 1)

    def test_empty_memory_selection_rejected(self):
        with self.assertRaises(ValueError):
            BoundedAuthorityJointRecoveryMemory().selection()
        with self.assertRaises(ValueError):
            BoundedAuthorityJointRecoveryMemory().record()

    def test_recovery_fires_via_corroboration_exact_expiry_record(self):
        m = fed(RECOVERY_ROWS)
        decision, model = m.selection()
        self.assertTrue(decision["gate_evaluable"])
        self.assertEqual(decision["joint_count"], 2)
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["expiry_spans"], [
            {"span": 5, "local_count": 26, "local_majority": "damage",
             "archive_count": 10, "archive_majority": "progress",
             "comparable": True, "disagreeing": True},
        ])
        self.assertEqual(decision["comparable_span_count"], 1)
        self.assertEqual(decision["disagreeing_span_count"], 1)
        self.assertTrue(decision["stable_disagreement"])
        self.assertEqual(len(decision["recent_events"]), ACTING_WINDOW)
        self.assertEqual(
            [r["archive_concordant"] for r in decision["recent_events"]],
            [False] * 6 + [True, True])
        for rec in decision["recent_events"]:
            self.assertEqual(rec["archive_count"], 10)
            self.assertEqual(rec["archive_majority"], "progress")
        self.assertEqual(decision["recent_concordant_count"], 2)
        self.assertTrue(decision["recovery_armed"])
        self.assertFalse(decision["abstention_armed"])
        self.assertTrue(decision["recovery_would_fire"])
        self.assertTrue(decision["abstention_would_fire"])
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

    def test_recovery_armed_without_stable_disagreement(self):
        # No comparable span at all (C == 0): the span-5 local majority
        # is tied and the span-3 archive majority is tied, so the
        # stable-disagreement flag cannot set. recent_concordant is
        # only 1 (< 2), so recovery is armed SOLELY by the absence of
        # stable disagreement, and the single joint event fires it.
        archive = ([row("progress") for _ in range(10)]
                   + [row("progress", span=3) for _ in range(5)]
                   + [row("damage", span=3) for _ in range(5)])
        reference = ([row("damage")]
                     + [row("progress", span=3) for _ in range(23)])
        rows = archive + reference + [row("progress"), row("neutral")]
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["comparable_span_count"], 0)
        self.assertFalse(decision["stable_disagreement"])
        self.assertEqual(decision["recent_concordant_count"], 1)
        self.assertTrue(decision["recovery_armed"])
        self.assertTrue(decision["abstention_armed"])
        self.assertEqual(decision["joint_count"], 1)
        self.assertTrue(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "retained_archive")

    def test_single_joint_event_disarmed_late(self):
        decision, model = fed(DISARMED_RECOVERY_ROWS).selection()
        self.assertEqual(decision["joint_count"], 1)
        self.assertTrue(decision["recovery_would_fire"])
        self.assertTrue(decision["stable_disagreement"])
        self.assertEqual(decision["comparable_span_count"], 1)
        self.assertEqual(decision["disagreeing_span_count"], 1)
        self.assertEqual(decision["recent_concordant_count"], 1)
        self.assertFalse(decision["recovery_armed"])
        self.assertFalse(decision["recovery_fired"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "recovery_disarmed_by_expiry")
        self.assertEqual(len(model.events), ACTING_WINDOW)
        # The unexpired joint candidate recovers on the same rows:
        # the authority condition is the ONLY difference.
        joint = JointConcordanceRecoveryMemory()
        for r in DISARMED_RECOVERY_ROWS:
            joint.observe(r)
        self.assertTrue(joint.selection()[0]["recovery_fired"])

    def test_abstention_disarmed_by_stable_disagreement(self):
        decision, model = fed(DISARMED_ABSTAIN_ROWS).selection()
        self.assertEqual(decision["opposed_count"], 2)
        self.assertTrue(decision["abstention_would_fire"])
        self.assertEqual(decision["joint_count"], 0)
        self.assertFalse(decision["recovery_would_fire"])
        self.assertEqual(decision["comparable_span_count"], 3)
        self.assertEqual(decision["disagreeing_span_count"], 2)
        self.assertTrue(decision["stable_disagreement"])
        self.assertFalse(decision["abstention_armed"])
        self.assertFalse(decision["abstained"])
        self.assertFalse(decision["gate_fired"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "abstention_disarmed_by_expiry")
        self.assertEqual(len(model.events), ACTING_WINDOW)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNotNone(fed(DISARMED_ABSTAIN_ROWS).choose(frame))

    def test_disarmed_recovery_falls_through_to_armed_abstention(self):
        # Fall-through order: a disarmed branch behaves as if its
        # trigger had not fired. Here recovery would fire (joint 1)
        # but is disarmed, while abstention's trigger is met - in a
        # stream where abstention is NOT armed either, both fall
        # through; this case instead pins that a would-fire recovery
        # does not suppress the abstention evaluation: with stable
        # disagreement abstention is disarmed too, so recent8 acts.
        # (Abstention armed requires no stable disagreement, under
        # which recovery is also armed, so an armed abstention after
        # a disarmed recovery cannot occur by construction.)
        decision, _ = fed(DISARMED_RECOVERY_ROWS).selection()
        self.assertTrue(decision["recovery_would_fire"])
        self.assertFalse(decision["recovery_armed"])
        self.assertFalse(decision["abstention_armed"])
        self.assertEqual(decision["branch"], "recent8")

    def test_abstains_when_armed_as_joint_candidate(self):
        m = fed(ABSTAIN_ROWS)
        decision, _ = m.selection()
        self.assertFalse(decision["stable_disagreement"])
        self.assertTrue(decision["abstention_armed"])
        self.assertTrue(decision["recovery_armed"])
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["joint_count"], 0)
        self.assertTrue(decision["abstained"])
        self.assertTrue(decision["gate_fired"])
        self.assertEqual(decision["branch"], "abstained")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(m.choose(frame))

    def test_strict_majority_boundary_is_not_stable(self):
        # C == 2, D == 1: D * 2 > C is false (2 > 2), so the flag is
        # NOT set - the disagreement rule is a strict majority.
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

    def test_no_comparable_span_is_not_stable(self):
        # Archive majority neutral at the only local span -> the span
        # is not comparable, C == 0, flag unset, branches armed.
        rows = ([row("neutral") for _ in range(10)]
                + [row("damage") for _ in range(24)]
                + [row("damage"), row("damage")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["expiry_spans"], [
            {"span": 5, "local_count": 26, "local_majority": "damage",
             "archive_count": 10, "archive_majority": "neutral",
             "comparable": False, "disagreeing": False},
        ])
        self.assertEqual(decision["comparable_span_count"], 0)
        self.assertFalse(decision["stable_disagreement"])
        self.assertTrue(decision["abstention_armed"])
        self.assertTrue(decision["recovery_armed"])

    def test_tied_local_majority_is_not_comparable(self):
        # Local window = 12 damage + 12 progress + 2 neutral at span 5:
        # progress and damage tie for the strictly-highest count, so
        # the local majority is None and the span is not comparable.
        rows = ([row("progress") for _ in range(10)]
                + [row("damage") for _ in range(12)]
                + [row("progress") for _ in range(12)]
                + [row("neutral"), row("neutral")])
        decision, _ = fed(rows).selection()
        rec = decision["expiry_spans"][0]
        self.assertIsNone(rec["local_majority"])
        self.assertFalse(rec["comparable"])
        self.assertFalse(decision["stable_disagreement"])

    def test_span_absent_from_archive_is_not_comparable(self):
        archive = [row("progress") for _ in range(10)]
        reference = ([row("damage") for _ in range(12)]
                     + [row("damage", span=9) for _ in range(12)])
        rows = archive + reference + [row("progress", span=9),
                                      row("progress", span=9)]
        decision, _ = fed(rows).selection()
        by_span = {r["span"]: r for r in decision["expiry_spans"]}
        self.assertEqual(by_span[9]["archive_count"], 0)
        self.assertIsNone(by_span[9]["archive_majority"])
        self.assertFalse(by_span[9]["comparable"])

    def test_recent_concordance_uses_current_archive_only(self):
        # Recent records must be scored against events[:N-26] only:
        # every recent record's archive_count equals the archive's
        # per-span count, never a count including reference events.
        decision, _ = fed(RECOVERY_ROWS).selection()
        for rec in decision["recent_events"]:
            self.assertEqual(rec["archive_count"], 10)
        # In the disarmed case the archive is the first 108 events
        # (100 progress + 8 damage at span 5).
        decision2, _ = fed(DISARMED_RECOVERY_ROWS).selection()
        for rec in decision2["recent_events"]:
            self.assertEqual(rec["archive_count"], 108)
            self.assertEqual(rec["archive_majority"], "progress")
        self.assertEqual(decision2["archive_events_count"], 108)

    def test_stationary_stream_matches_recent8(self):
        rows = [row("progress") for _ in range(40)]
        m = fed(rows)
        decision, model = m.selection()
        self.assertFalse(decision["stable_disagreement"])
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
        for rec in decision["expiry_spans"]:
            self.assertEqual(set(rec),
                             {"span", "local_count", "local_majority",
                              "archive_count", "archive_majority",
                              "comparable", "disagreeing"})
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
        restored = BoundedAuthorityJointRecoveryMemory.restore(
            copy.deepcopy(saved))
        frame = StochasticWorld(self.seed, "test", 160000,
                                "reversed").frame()
        self.assertEqual(m.choose(frame), restored.choose(frame))
        self.assertEqual(m.selection()[0], restored.selection()[0])
        self.assertEqual(m.record(), saved)
        self.assertEqual(restored.record(), saved)
        self.assertFalse(hasattr(m, "step"))

    def test_replay_reproduces_expiry_decision(self):
        m = fed(DISARMED_RECOVERY_ROWS)
        saved = m.record()
        restored = BoundedAuthorityJointRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["expiry_spans"],
                         m.selection()[0]["expiry_spans"])
        self.assertTrue(restored.selection()[0]["stable_disagreement"])
        self.assertFalse(restored.selection()[0]["recovery_fired"])

    def test_reject_invalid_events_without_partial_write(self):
        m = BoundedAuthorityJointRecoveryMemory()
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
            BoundedAuthorityJointRecoveryMemory.restore(bad)
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            BoundedAuthorityJointRecoveryMemory.restore(bad)
        bad2 = copy.deepcopy(saved)
        bad2["state"]["schema"] = "developmental-ai.other/v1"
        bad2["sha256"] = digest(bad2["state"])
        with self.assertRaises(ValueError):
            BoundedAuthorityJointRecoveryMemory.restore(bad2)

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
