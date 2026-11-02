"""Frozen-protocol unit tests for MinorityArchiveJointRecoveryMemory.

Protocol: benchmarks/minority_archive_joint_recovery_protocol.json.
These tests use only handcrafted synthetic events and the ALREADY
INSPECTED stochastic cohort seed 212003 (frame/source shape only).
The frozen cohorts of this experiment (372003-family / 373001-family)
are never touched here: no cohort scores are viewed or run before or
during implementation.
"""
from __future__ import annotations

import copy
import unittest

from developmental_ai.minority_archive_joint_recovery import (
    MinorityArchiveJointRecoveryMemory, SCHEMA, ACTING_WINDOW,
    NEWEST_WINDOW, REFERENCE_WINDOW, LEGACY_REFERENCE_WINDOW,
    ARCHIVE_PARTITION, LOCAL_WINDOW, PRECEDING_WINDOW,
    MINIMUM_EVENTS, GATE_OPPOSED_COUNT, RECOVERY_JOINT_COUNT,
    RECENT_CONCORDANT_THRESHOLD, MINORITY_FRACTION_THRESHOLD,
    MINORITY_DISCORDANT_MINIMUM, MINORITY_JOINT_THRESHOLD,
)
from developmental_ai.extended_reference_joint_recovery import (
    ExtendedReferenceJointRecoveryMemory,
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
    m = MinorityArchiveJointRecoveryMemory()
    for r in rows:
        m.observe(r)
    return m


def plain_model(rows):
    m = RelationOutcomeMemory()
    for r in rows:
        m.observe(r)
    return m


# Minority recovery, DISCRIMINATING vs the graded extended candidate:
# the archive (30 damage + 60 progress) is progress-majority, so its
# discordant minority set is exactly the 30 damage events and the
# minority fraction is 30/90 = 1/3 (armed). The reference (archive
# tail progress + 24 progress) is progress-majority, so the newest
# damage events are reference-opposed AND minority-concordant but
# archive-DISCORDANT: the regular joint count is 0 and the graded
# extended candidate abstains (opposed_count == 2, armed); this
# candidate takes the minority branch, which sits ABOVE abstention.
MINORITY_RECOVERY_ROWS = ([row("damage") for _ in range(30)]
                          + [row("progress") for _ in range(60)]
                          + [row("progress") for _ in range(24)]
                          + [row("damage"), row("damage")])

# Same shape with a thin minority: archive 10 damage + 80 progress,
# minority fraction 10/90 = 0.111 < 0.25, so the minority branch is
# NOT armed even though both newest events are minority-joint; the
# learner falls through to the armed abstention branch.
MINORITY_BELOW_FRACTION_ROWS = ([row("damage") for _ in range(10)]
                                + [row("progress") for _ in range(80)]
                                + [row("progress") for _ in range(24)]
                                + [row("damage"), row("damage")])

# Count-floor disarming at exactly MINIMUM_EVENTS: archive is the
# first 26 events (19 progress + 7 damage), fraction 7/26 = 0.269
# >= 0.25 but minority_discordant_count 7 < 8, so NOT armed.
MINORITY_BELOW_COUNT_ROWS = ([row("progress") for _ in range(19)]
                             + [row("damage") for _ in range(7)]
                             + [row("progress") for _ in range(24)]
                             + [row("damage"), row("damage")])

# Regular recovery takes precedence over minority recovery: newest
# span-5 progress is archive-concordant + opposed (regular joint),
# newest span-3 progress is minority-concordant + opposed (minority
# joint); both counts are 1 and the branch taken is retained_archive.
PRECEDENCE_ROWS = (
    [row("progress", span=5) for _ in range(40)]
    + [row("damage", span=3) for _ in range(40)]
    + [row("damage", span=5) for _ in range(15)]
    + [row("progress", span=3) for _ in range(15)]
    + [row("damage", span=5) for _ in range(13)]
    + [row("damage", span=3) for _ in range(13)]
    + [row("damage", span=5) for _ in range(12)]
    + [row("damage", span=3) for _ in range(12)]
    + [row("progress", span=5), row("progress", span=3)])

# Carried-over extended-reference recovery rows (graded extended
# test set): regular recovery fires; the minority branch is armed
# (archive 48 progress + 26 damage, fraction 26/74) but its joint
# count is 0, so it changes nothing.
EXTENDED_RECOVERY_ROWS = ([row("progress") for _ in range(48)]
                          + [row("damage") for _ in range(26)]
                          + [row("progress") for _ in range(18)]
                          + [row("damage") for _ in range(6)]
                          + [row("progress"), row("damage")])

# Archive and extended reference agree (progress); newest both
# damage but the archive contains no discordant events at all, so
# the minority set is empty and abstention fires as before.
ABSTAIN_ROWS = ([row("progress") for _ in range(10)]
                + [row("progress") for _ in range(50)]
                + [row("damage"), row("damage")])

# Late single flip-back (carried over): one regular joint event,
# no authority leg arms regular recovery, and the minority joint
# count is 0, so the learner stays on recent8.
DISARMED_RECOVERY_ROWS = ([row("progress") for _ in range(100)]
                          + [row("damage") for _ in range(32)]
                          + [row("progress"), row("damage")])


class MinorityArchiveJointRecoveryTests(unittest.TestCase):
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
        self.assertEqual(LOCAL_WINDOW, 26)
        self.assertEqual(PRECEDING_WINDOW, 26)
        self.assertEqual(MINIMUM_EVENTS, 52)
        self.assertEqual(GATE_OPPOSED_COUNT, 2)
        self.assertEqual(RECOVERY_JOINT_COUNT, 1)
        self.assertEqual(RECENT_CONCORDANT_THRESHOLD, 2)
        self.assertEqual(MINORITY_FRACTION_THRESHOLD, 0.25)
        self.assertEqual(MINORITY_DISCORDANT_MINIMUM, 8)
        self.assertEqual(MINORITY_JOINT_THRESHOLD, 1)

    def test_signals_not_evaluable_below_minimum_events(self):
        m = fed(MINORITY_RECOVERY_ROWS[:MINIMUM_EVENTS - 1])
        decision, model = m.selection()
        self.assertFalse(decision["gate_evaluable"])
        self.assertEqual(decision["branch"], "all_available_below_minimum")
        self.assertEqual(decision["minority_events"], [])
        self.assertEqual(decision["minority_joint_events"], [])
        self.assertEqual(decision["minority_joint_flags"], [])
        self.assertEqual(decision["minority_joint_count"], 0)
        self.assertEqual(decision["minority_discordant_count"], 0)
        self.assertEqual(decision["minority_fraction"], 0.0)
        self.assertFalse(decision["minority_armed"])
        self.assertFalse(decision["minority_fired"])
        self.assertFalse(decision["minority_would_fire"])
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
        self.assertEqual(decision["opposed_count"], 0)
        self.assertEqual(decision["legacy_opposed_count"], 2)
        # Archive is 26 progress events only: no discordant events.
        self.assertEqual(decision["minority_archive_matched_count"], 26)
        self.assertEqual(decision["minority_discordant_count"], 0)
        self.assertEqual(decision["minority_fraction"], 0.0)
        self.assertFalse(decision["minority_armed"])
        self.assertEqual(decision["minority_joint_count"], 0)

    def test_empty_memory_selection_rejected(self):
        with self.assertRaises(ValueError):
            MinorityArchiveJointRecoveryMemory().selection()
        with self.assertRaises(ValueError):
            MinorityArchiveJointRecoveryMemory().record()

    def test_minority_recovery_exact_records(self):
        m = fed(MINORITY_RECOVERY_ROWS)
        decision, model = m.selection()
        self.assertTrue(decision["gate_evaluable"])
        self.assertEqual(decision["joint_count"], 0)
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["concordant_count"], 0)
        self.assertEqual(decision["minority_archive_matched_count"], 90)
        self.assertEqual(decision["minority_discordant_count"], 30)
        self.assertEqual(decision["minority_set_count"], 30)
        self.assertAlmostEqual(decision["minority_fraction"], 30 / 90)
        self.assertTrue(decision["minority_armed"])
        self.assertEqual(decision["minority_events"], [
            {"span": 5, "reported_class": "damage", "minority_count": 30,
             "minority_majority": "damage", "minority_matched": True,
             "minority_concordant": True},
            {"span": 5, "reported_class": "damage", "minority_count": 30,
             "minority_majority": "damage", "minority_matched": True,
             "minority_concordant": True},
        ])
        self.assertEqual(decision["minority_matched_count"], 2)
        self.assertEqual(decision["minority_concordant_count"], 2)
        self.assertEqual(decision["minority_joint_flags"], [True, True])
        self.assertEqual(decision["minority_joint_count"], 2)
        self.assertTrue(decision["minority_would_fire"])
        self.assertTrue(decision["minority_fired"])
        self.assertTrue(decision["minority_recovery_fired"])
        self.assertFalse(decision["recovery_fired"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "minority_archive")
        self.assertEqual(decision["source"], "minority_archive")
        self.assertEqual(decision["reason"],
                         "minority_archive_recovery_armed")
        self.assertEqual(decision["archive_events_count"], 90)
        self.assertEqual(decision["learner_training_actions"], 0)
        # The minority model holds exactly the 30 discordant events.
        self.assertEqual(model.events,
                         [dict(r) for r in MINORITY_RECOVERY_ROWS[:30]])
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(
            m.choose(frame),
            plain_model(MINORITY_RECOVERY_ROWS[:30]).choose(frame))

    def test_minority_recovers_where_extended_candidate_abstains(self):
        ext = ExtendedReferenceJointRecoveryMemory()
        for r in MINORITY_RECOVERY_ROWS:
            ext.observe(r)
        ext_decision, _ = ext.selection()
        self.assertEqual(ext_decision["joint_count"], 0)
        self.assertTrue(ext_decision["abstained"])
        self.assertEqual(ext_decision["branch"], "abstained")
        decision, _ = fed(MINORITY_RECOVERY_ROWS).selection()
        self.assertEqual(decision["branch"], "minority_archive")
        # The extended candidate's rule is still derivable from the
        # carried-over records: legacy counts and authority agree.
        self.assertEqual(decision["legacy_joint_count"],
                         ext_decision["legacy_joint_count"])
        self.assertEqual(decision["stable_disagreement"],
                         ext_decision["stable_disagreement"])
        self.assertEqual(decision["recent_concordant_count"],
                         ext_decision["recent_concordant_count"])

    def test_regular_recovery_takes_precedence_over_minority(self):
        decision, model = fed(PRECEDENCE_ROWS).selection()
        self.assertEqual(decision["joint_count"], 1)
        self.assertEqual(decision["minority_joint_count"], 1)
        self.assertEqual(decision["minority_discordant_count"], 43)
        self.assertAlmostEqual(decision["minority_fraction"], 43 / 136)
        self.assertTrue(decision["minority_armed"])
        self.assertTrue(decision["recovery_fired"])
        self.assertFalse(decision["minority_fired"])
        self.assertEqual(decision["branch"], "retained_archive")
        self.assertEqual(len(model.events), 136)

    def test_minority_disarmed_below_fraction_threshold(self):
        decision, _ = fed(MINORITY_BELOW_FRACTION_ROWS).selection()
        self.assertAlmostEqual(decision["minority_fraction"], 10 / 90)
        self.assertEqual(decision["minority_discordant_count"], 10)
        self.assertFalse(decision["minority_armed"])
        self.assertEqual(decision["minority_joint_count"], 2)
        self.assertTrue(decision["minority_would_fire"])
        self.assertFalse(decision["minority_fired"])
        self.assertTrue(decision["abstained"])
        self.assertEqual(decision["branch"], "abstained")

    def test_minority_disarmed_below_count_floor(self):
        decision, _ = fed(MINORITY_BELOW_COUNT_ROWS).selection()
        self.assertEqual(decision["minority_discordant_count"], 7)
        self.assertAlmostEqual(decision["minority_fraction"], 7 / 26)
        self.assertGreaterEqual(decision["minority_fraction"],
                                MINORITY_FRACTION_THRESHOLD)
        self.assertFalse(decision["minority_armed"])
        self.assertTrue(decision["minority_would_fire"])
        self.assertFalse(decision["minority_fired"])
        self.assertEqual(decision["branch"], "abstained")

    def test_carried_over_recovery_unchanged_when_minority_silent(self):
        decision, model = fed(EXTENDED_RECOVERY_ROWS).selection()
        self.assertEqual(decision["joint_count"], 1)
        self.assertEqual(decision["legacy_joint_count"], 0)
        self.assertAlmostEqual(decision["minority_fraction"], 26 / 74)
        self.assertTrue(decision["minority_armed"])
        self.assertEqual(decision["minority_joint_count"], 0)
        self.assertFalse(decision["minority_fired"])
        self.assertTrue(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "retained_archive")
        self.assertEqual(decision["archive_events_count"], 74)
        self.assertEqual(model.events,
                         [dict(r) for r in EXTENDED_RECOVERY_ROWS[:74]])

    def test_abstains_when_no_minority_set(self):
        m = fed(ABSTAIN_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["minority_discordant_count"], 0)
        self.assertEqual(decision["minority_fraction"], 0.0)
        self.assertFalse(decision["minority_armed"])
        self.assertEqual(decision["opposed_count"], 2)
        self.assertTrue(decision["abstained"])
        self.assertEqual(decision["branch"], "abstained")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(m.choose(frame))

    def test_stationary_stream_matches_recent8(self):
        rows = [row("progress") for _ in range(60)]
        m = fed(rows)
        decision, model = m.selection()
        self.assertEqual(decision["minority_fraction"], 0.0)
        self.assertEqual(decision["minority_joint_count"], 0)
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(len(model.events), ACTING_WINDOW)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(m.choose(frame),
                         plain_model(rows[-ACTING_WINDOW:]).choose(frame))

    def test_neutral_newest_event_is_never_minority_joint(self):
        rows = ([row("damage") for _ in range(30)]
                + [row("progress") for _ in range(60)]
                + [row("progress") for _ in range(24)]
                + [row("neutral"), row("neutral")])
        decision, _ = fed(rows).selection()
        self.assertTrue(decision["minority_armed"])
        self.assertEqual(decision["minority_joint_flags"], [False, False])
        self.assertEqual(decision["minority_joint_count"], 0)
        self.assertFalse(decision["minority_would_fire"])
        self.assertEqual(decision["branch"], "recent8")

    def test_single_joint_event_disarmed_late_stays_recent8(self):
        decision, model = fed(DISARMED_RECOVERY_ROWS).selection()
        self.assertEqual(decision["joint_count"], 1)
        self.assertTrue(decision["recovery_would_fire"])
        self.assertFalse(decision["recovery_armed"])
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["minority_joint_count"], 0)
        self.assertFalse(decision["minority_fired"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "recovery_disarmed_by_expiry")
        self.assertEqual(len(model.events), ACTING_WINDOW)

    def test_minority_fraction_on_pure_segment_is_flip_level(self):
        # A single-segment archive with an exact 13/80 discordant
        # share records that share; arming is a threshold on the
        # recorded fraction, not a segment label.
        rows = ([row("damage") for _ in range(13)]
                + [row("progress") for _ in range(67)]
                + [row("progress") for _ in range(24)]
                + [row("progress"), row("progress")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["minority_archive_matched_count"], 80)
        self.assertEqual(decision["minority_discordant_count"], 13)
        self.assertAlmostEqual(decision["minority_fraction"], 13 / 80)
        self.assertFalse(decision["minority_armed"])

    def test_no_fitted_probability_fields_in_decision(self):
        decision, _ = fed(MINORITY_RECOVERY_ROWS).selection()
        for key in decision:
            self.assertNotIn("probabilit", key)
            self.assertNotIn("log_score", key)
        for rec in decision["minority_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class", "minority_count",
                              "minority_majority", "minority_matched",
                              "minority_concordant"})
        for rec in decision["minority_joint_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class",
                              "minority_concordant", "opposed",
                              "minority_joint", "joint"})
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
        restored = MinorityArchiveJointRecoveryMemory.restore(
            copy.deepcopy(saved))
        frame = StochasticWorld(self.seed, "test", 160000,
                                "reversed").frame()
        self.assertEqual(m.choose(frame), restored.choose(frame))
        self.assertEqual(m.selection()[0], restored.selection()[0])
        self.assertEqual(m.record(), saved)
        self.assertEqual(restored.record(), saved)
        self.assertFalse(hasattr(m, "step"))

    def test_replay_reproduces_minority_decision(self):
        m = fed(MINORITY_RECOVERY_ROWS)
        saved = m.record()
        restored = MinorityArchiveJointRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"],
                         "minority_archive")
        self.assertEqual(
            restored.selection()[0]["minority_discordant_count"], 30)
        self.assertTrue(restored.selection()[0]["minority_fired"])

    def test_reject_invalid_events_without_partial_write(self):
        m = MinorityArchiveJointRecoveryMemory()
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
            MinorityArchiveJointRecoveryMemory.restore(bad)
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            MinorityArchiveJointRecoveryMemory.restore(bad)
        bad2 = copy.deepcopy(saved)
        bad2["state"]["schema"] = "developmental-ai.other/v1"
        bad2["sha256"] = digest(bad2["state"])
        with self.assertRaises(ValueError):
            MinorityArchiveJointRecoveryMemory.restore(bad2)

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
