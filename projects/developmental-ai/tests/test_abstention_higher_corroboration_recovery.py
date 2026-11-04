"""Frozen-protocol unit tests for AbstentionHigherCorroborationRecoveryMemory.

Protocol: benchmarks/abstention_higher_corroboration_recovery_protocol.json.
These tests use only handcrafted synthetic events and the ALREADY
INSPECTED stochastic cohort seed 212003 (frame/source shape only).
The frozen cohorts of this experiment (412003-family / 413001-family)
are never touched here: no cohort scores are viewed or run before or
during implementation.
"""
from __future__ import annotations

import copy
import unittest

from developmental_ai.abstention_higher_corroboration_recovery import (
    AbstentionHigherCorroborationRecoveryMemory, SCHEMA, ACTING_WINDOW,
    NEWEST_WINDOW, REFERENCE_WINDOW, LEGACY_REFERENCE_WINDOW,
    ARCHIVE_PARTITION, LOCAL_WINDOW, PRECEDING_WINDOW,
    MINIMUM_EVENTS, GATE_OPPOSED_COUNT, RECOVERY_JOINT_COUNT,
    RECENT_CONCORDANT_THRESHOLD, MINORITY_FRACTION_THRESHOLD,
    MINORITY_DISCORDANT_MINIMUM, MINORITY_JOINT_THRESHOLD,
    PURITY_THRESHOLD, SUPPORT_THRESHOLD,
)
from developmental_ai.reference_purity_gated_recovery import (
    ReferencePurityGatedRecoveryMemory as GradedPurityMemory,
)
from developmental_ai.abstention_release_gated_recovery import (
    AbstentionReleaseGatedRecoveryMemory as GradedReleaseMemory,
)
from developmental_ai.minority_archive_joint_recovery import (
    MinorityArchiveJointRecoveryMemory,
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
    m = AbstentionHigherCorroborationRecoveryMemory()
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
# fall-through abstention is itself blocked by leg S here.
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
# the minority set is empty; the graded purity candidate abstains
# here, while this candidate's abstention is blocked by leg S.
ABSTAIN_ROWS = ([row("progress") for _ in range(10)]
                + [row("progress") for _ in range(50)]
                + [row("damage"), row("damage")])

# Late single flip-back (carried over): one regular joint event,
# no authority leg arms regular recovery, and the minority joint
# count is 0, so the learner stays on recent8.
DISARMED_RECOVERY_ROWS = ([row("progress") for _ in range(100)]
                          + [row("damage") for _ in range(32)]
                          + [row("progress"), row("damage")])

# Purity-armed regular recovery (DISCRIMINATING for the gate's armed
# side): the reference window is 50 damage events (purity 1.0), the
# archive majority is progress, and both newest progress events are
# archive-concordant AND reference-opposed; recovery is armed by the
# long leg, so the branch taken is retained_archive, exactly as the
# graded minority candidate takes it on the same rows.
PURITY_ARMED_RECOVERY_ROWS = ([row("progress") for _ in range(60)]
                              + [row("damage") for _ in range(24)]
                              + [row("damage") for _ in range(26)]
                              + [row("progress"), row("progress")])

# Purity-disarmed regular recovery, multi-span construction (see
# module-level verification in the implementation pass): reference
# purity 32/50 = 0.64, one regular joint event, recovery armed by
# the absence of stable disagreement; the graded minority candidate
# recovers on these rows and this candidate stays on recent8 with
# recovery_disarmed_by_purity recorded.
REGULAR_PURITY_DISARMED_ROWS = (
    [row("progress", span=5) for _ in range(40)]
    + [row("damage", span=5) for _ in range(10)]
    + [row("progress", span=3) for _ in range(38)]
    + [row("damage", span=3) for _ in range(13)]
    + [row("progress", span=9) for _ in range(7)]
    + [row("damage", span=9) for _ in range(6)]
    + [row("damage", span=5) for _ in range(4)]
    + [row("progress", span=3) for _ in range(12)]
    + [row("progress", span=9) for _ in range(8)]
    + [row("progress", span=5), row("damage", span=3)])

# Purity-disarmed minority recovery, mirror construction: reference
# purity 31/50 = 0.62, one minority joint event, minority armed
# (fraction 29/114); the graded minority candidate takes the
# minority branch on these rows and this candidate stays on recent8
# with minority_disarmed_by_purity recorded.
MINORITY_PURITY_DISARMED_ROWS = (
    [row("damage", span=5) for _ in range(40)]
    + [row("progress", span=5) for _ in range(10)]
    + [row("damage", span=3) for _ in range(38)]
    + [row("progress", span=3) for _ in range(13)]
    + [row("damage", span=9) for _ in range(7)]
    + [row("progress", span=9) for _ in range(6)]
    + [row("damage", span=3) for _ in range(20)]
    + [row("progress", span=5) for _ in range(4)]
    + [row("progress", span=3), row("damage", span=9)])

# In the graded purity candidate abstention was NOT gated: same
# mixed reference as REGULAR_PURITY_DISARMED_ROWS (purity 0.64,
# recovery trigger present and disarmed by purity) and both newest
# events opposed, so that candidate abstains. Here BOTH release
# legs block the abstention (purity 0.64 disarmed; acting opposed
# count 2, no supporting event), so both disarmed flags are true
# and the branch taken is recent8.
ABSTENTION_UNGATED_ROWS = (
    [row("progress", span=5) for _ in range(40)]
    + [row("damage", span=5) for _ in range(10)]
    + [row("progress", span=3) for _ in range(38)]
    + [row("damage", span=3) for _ in range(13)]
    + [row("progress", span=9) for _ in range(7)]
    + [row("damage", span=9) for _ in range(6)]
    + [row("damage", span=5) for _ in range(4)]
    + [row("progress", span=3) for _ in range(12)]
    + [row("progress", span=9) for _ in range(8)]
    + [row("progress", span=3), row("progress", span=3)])

# Purity threshold boundary: the reference window (events 50..99)
# is 35 progress + 15 damage on one span, so purity is exactly
# 35/50 = 0.70 and the gate is armed (threshold is >=).
PURITY_BOUNDARY_ROWS = ([row("progress") for _ in range(50)]
                        + [row("progress") for _ in range(35)]
                        + [row("damage") for _ in range(15)]
                        + [row("progress"), row("progress")])

# Release-gate-ARMED abstention at the RAISED bar (DISCRIMINATING
# for the gate's armed side): the reference is 48 progress + 2
# damage (purity 0.96, leg P armed) and both damage events sit
# among the 6 acting-window events preceding the newest pair, so
# the acting opposed count is 4 (leg S armed at the raised bar:
# supporting count 2). Both newest events are opposed damage, no
# recovery/minority trigger fires, and abstention is TAKEN,
# exactly as the graded abstention-release candidate takes it on
# the same rows.
GATE_ARMED_ABSTAIN_ROWS = (
    [row("progress") for _ in range(60)]
    + [row("progress") for _ in range(44)]
    + [row("damage"), row("damage")]
    + [row("progress") for _ in range(4)]
    + [row("damage"), row("damage")])

# Single-support rows (DISCRIMINATING for the raised bar): identical
# shape to GATE_ARMED_ABSTAIN_ROWS but with only ONE supporting
# opposed event among the 6 acting-window events preceding the
# newest pair (acting opposed count 3, purity 0.98). The graded
# abstention-release candidate abstains on these rows (its bar was
# >= 3); this candidate's raised bar (>= 4) blocks the abstention
# by leg S alone and falls through to recent8. These are exactly
# the graded release candidate's gate-armed test rows.
SINGLE_SUPPORT_ABSTAIN_ROWS = (
    [row("progress") for _ in range(60)]
    + [row("progress") for _ in range(44)]
    + [row("damage")]
    + [row("progress") for _ in range(5)]
    + [row("damage"), row("damage")])

# Purity leg ALONE blocks at the raised bar: the acting opposed
# count is 4 (support satisfied at the raised bar: two supporting
# opposed events, the span-9 damage pair) while purity is 0.60
# (leg P disarmed). Both flags are recorded individually:
# by_purity true, by_support false.
PURITY_ALONE_BLOCKED_ROWS = (
    [row("progress", span=5) for _ in range(40)]
    + [row("damage", span=5) for _ in range(10)]
    + [row("progress", span=3) for _ in range(38)]
    + [row("damage", span=3) for _ in range(13)]
    + [row("progress", span=9) for _ in range(7)]
    + [row("damage", span=9) for _ in range(6)]
    + [row("damage", span=5) for _ in range(4)]
    + [row("progress", span=3) for _ in range(12)]
    + [row("progress", span=9) for _ in range(6)]
    + [row("damage", span=9), row("damage", span=9)]
    + [row("progress", span=3), row("progress", span=3)])

# Authority-disarmed abstention: the local window (last 26, all
# damage) stably disagrees with the archive (all progress), so the
# carried-over abstention arming is already disarmed; realized
# purity is 0.52 and the acting opposed count is 8, yet BOTH
# release-gate flags must be false - the gate did not block this
# state, the authority did.
AUTHORITY_DISARMED_ABSTAIN_ROWS = (
    [row("progress") for _ in range(100)]
    + [row("damage") for _ in range(26)])


class AbstentionHigherCorroborationRecoveryTests(unittest.TestCase):
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
        self.assertEqual(PURITY_THRESHOLD, 0.70)
        self.assertEqual(SUPPORT_THRESHOLD, 4)

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
        self.assertEqual(decision["reference_events"], [])
        self.assertEqual(decision["reference_matched_count"], 0)
        self.assertEqual(decision["reference_concordant_count"], 0)
        self.assertEqual(decision["reference_purity"], 0.0)
        self.assertFalse(decision["purity_armed"])
        self.assertFalse(decision["recovery_disarmed_by_purity"])
        self.assertFalse(decision["minority_disarmed_by_purity"])
        self.assertEqual(decision["acting_events"], [])
        self.assertEqual(decision["acting_matched_count"], 0)
        self.assertEqual(decision["acting_opposed_count"], 0)
        self.assertEqual(decision["supporting_opposed_count"], 0)
        self.assertEqual(decision["support_threshold"], SUPPORT_THRESHOLD)
        self.assertFalse(decision["abstention_gate_armed"])
        self.assertFalse(decision["abstention_disarmed_by_purity"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
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
            AbstentionHigherCorroborationRecoveryMemory().selection()
        with self.assertRaises(ValueError):
            AbstentionHigherCorroborationRecoveryMemory().record()

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
        # The fall-through abstention is itself blocked by leg S
        # (acting opposed count 2, no supporting event) where the
        # graded purity candidate abstained on these rows.
        self.assertFalse(decision["abstained"])
        self.assertTrue(decision["abstention_disarmed_by_support"])
        self.assertFalse(decision["abstention_disarmed_by_purity"])
        self.assertEqual(decision["branch"], "recent8")

    def test_minority_disarmed_below_count_floor(self):
        decision, _ = fed(MINORITY_BELOW_COUNT_ROWS).selection()
        self.assertEqual(decision["minority_discordant_count"], 7)
        self.assertAlmostEqual(decision["minority_fraction"], 7 / 26)
        self.assertGreaterEqual(decision["minority_fraction"],
                                MINORITY_FRACTION_THRESHOLD)
        self.assertFalse(decision["minority_armed"])
        self.assertTrue(decision["minority_would_fire"])
        self.assertFalse(decision["minority_fired"])
        self.assertFalse(decision["abstained"])
        self.assertTrue(decision["abstention_disarmed_by_support"])
        self.assertEqual(decision["branch"], "recent8")

    def test_purity_armed_recovery_fires_like_minority_candidate(self):
        decision, model = fed(PURITY_ARMED_RECOVERY_ROWS).selection()
        self.assertEqual(decision["reference_matched_count"], 50)
        self.assertEqual(decision["reference_concordant_count"], 50)
        self.assertEqual(decision["reference_purity"], 1.0)
        self.assertTrue(decision["purity_armed"])
        self.assertEqual(decision["joint_count"], 2)
        self.assertEqual(decision["minority_joint_count"], 0)
        self.assertTrue(decision["recovery_fired"])
        self.assertFalse(decision["recovery_disarmed_by_purity"])
        self.assertEqual(decision["branch"], "retained_archive")
        self.assertEqual(decision["archive_events_count"], 86)
        self.assertEqual(model.events,
                         [dict(r) for r in PURITY_ARMED_RECOVERY_ROWS[:86]])
        old = MinorityArchiveJointRecoveryMemory()
        for r in PURITY_ARMED_RECOVERY_ROWS:
            old.observe(r)
        self.assertEqual(old.selection()[0]["branch"], "retained_archive")

    def test_extended_recovery_rows_are_disarmed_by_purity(self):
        # The graded extended/minority test rows carry a mixed
        # reference (32 concordant of 50 matched): the graded
        # minority candidate recovers there, this candidate does not.
        decision, model = fed(EXTENDED_RECOVERY_ROWS).selection()
        self.assertEqual(decision["joint_count"], 1)
        self.assertEqual(decision["legacy_joint_count"], 0)
        self.assertAlmostEqual(decision["minority_fraction"], 26 / 74)
        self.assertTrue(decision["minority_armed"])
        self.assertEqual(decision["minority_joint_count"], 0)
        self.assertEqual(decision["reference_matched_count"], 50)
        self.assertEqual(decision["reference_concordant_count"], 32)
        self.assertAlmostEqual(decision["reference_purity"], 32 / 50)
        self.assertFalse(decision["purity_armed"])
        self.assertTrue(decision["recovery_armed"])
        self.assertTrue(decision["recovery_disarmed_by_purity"])
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "recovery_disarmed_by_purity")
        self.assertEqual(len(model.events), ACTING_WINDOW)
        old = MinorityArchiveJointRecoveryMemory()
        for r in EXTENDED_RECOVERY_ROWS:
            old.observe(r)
        self.assertEqual(old.selection()[0]["branch"], "retained_archive")

    def test_regular_recovery_disarmed_by_purity_multispan(self):
        decision, _ = fed(REGULAR_PURITY_DISARMED_ROWS).selection()
        self.assertEqual(decision["joint_count"], 1)
        self.assertTrue(decision["recovery_would_fire"])
        self.assertTrue(decision["recovery_armed"])
        self.assertEqual(decision["reference_concordant_count"], 32)
        self.assertAlmostEqual(decision["reference_purity"], 0.64)
        self.assertFalse(decision["purity_armed"])
        self.assertTrue(decision["recovery_disarmed_by_purity"])
        self.assertFalse(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "recovery_disarmed_by_purity")
        old = MinorityArchiveJointRecoveryMemory()
        for r in REGULAR_PURITY_DISARMED_ROWS:
            old.observe(r)
        self.assertEqual(old.selection()[0]["branch"], "retained_archive")

    def test_minority_recovery_disarmed_by_purity(self):
        decision, _ = fed(MINORITY_PURITY_DISARMED_ROWS).selection()
        self.assertEqual(decision["joint_count"], 0)
        self.assertEqual(decision["minority_joint_count"], 1)
        self.assertTrue(decision["minority_would_fire"])
        self.assertTrue(decision["minority_armed"])
        self.assertAlmostEqual(decision["minority_fraction"], 29 / 114)
        self.assertEqual(decision["reference_concordant_count"], 31)
        self.assertAlmostEqual(decision["reference_purity"], 0.62)
        self.assertFalse(decision["purity_armed"])
        self.assertTrue(decision["minority_disarmed_by_purity"])
        self.assertFalse(decision["minority_fired"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "minority_disarmed_by_purity")
        old = MinorityArchiveJointRecoveryMemory()
        for r in MINORITY_PURITY_DISARMED_ROWS:
            old.observe(r)
        self.assertEqual(old.selection()[0]["branch"], "minority_archive")

    def test_abstention_blocked_by_both_gate_legs(self):
        decision, _ = fed(ABSTENTION_UNGATED_ROWS).selection()
        self.assertAlmostEqual(decision["reference_purity"], 0.64)
        self.assertFalse(decision["purity_armed"])
        self.assertTrue(decision["recovery_disarmed_by_purity"])
        self.assertEqual(decision["opposed_count"], 2)
        self.assertTrue(decision["abstention_armed"])
        self.assertEqual(decision["acting_opposed_count"], 2)
        self.assertEqual(decision["supporting_opposed_count"], 0)
        self.assertFalse(decision["abstention_gate_armed"])
        self.assertTrue(decision["abstention_disarmed_by_purity"])
        self.assertTrue(decision["abstention_disarmed_by_support"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        old = GradedPurityMemory()
        for r in ABSTENTION_UNGATED_ROWS:
            old.observe(r)
        self.assertEqual(old.selection()[0]["branch"], "abstained")

    def test_abstention_blocked_by_support_leg_alone(self):
        # ABSTAIN_ROWS: pure reference (purity 1.0, leg P armed),
        # opposed pair, but no supporting opposed event among the
        # preceding 6 acting-window events - leg S alone blocks.
        decision, _ = fed(ABSTAIN_ROWS).selection()
        self.assertEqual(decision["minority_discordant_count"], 0)
        self.assertFalse(decision["minority_armed"])
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["reference_purity"], 1.0)
        self.assertTrue(decision["purity_armed"])
        self.assertEqual(decision["acting_opposed_count"], 2)
        self.assertEqual(decision["supporting_opposed_count"], 0)
        self.assertFalse(decision["abstention_gate_armed"])
        self.assertFalse(decision["abstention_disarmed_by_purity"])
        self.assertTrue(decision["abstention_disarmed_by_support"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "abstention_disarmed_by_support")
        old = GradedPurityMemory()
        for r in ABSTAIN_ROWS:
            old.observe(r)
        self.assertEqual(old.selection()[0]["branch"], "abstained")

    def test_abstention_blocked_by_purity_leg_alone(self):
        decision, _ = fed(PURITY_ALONE_BLOCKED_ROWS).selection()
        self.assertAlmostEqual(decision["reference_purity"], 0.60)
        self.assertFalse(decision["purity_armed"])
        self.assertEqual(decision["opposed_count"], 2)
        self.assertTrue(decision["abstention_armed"])
        self.assertEqual(decision["acting_opposed_count"], 4)
        self.assertEqual(decision["supporting_opposed_count"], 2)
        self.assertFalse(decision["abstention_gate_armed"])
        self.assertTrue(decision["abstention_disarmed_by_purity"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")

    def test_gate_armed_abstention_taken(self):
        m = fed(GATE_ARMED_ABSTAIN_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["reference_matched_count"], 50)
        self.assertEqual(decision["reference_concordant_count"], 48)
        self.assertAlmostEqual(decision["reference_purity"], 0.96)
        self.assertTrue(decision["purity_armed"])
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["acting_matched_count"], 8)
        self.assertEqual(decision["acting_opposed_count"], 4)
        self.assertEqual(decision["supporting_opposed_count"], 2)
        self.assertTrue(decision["abstention_gate_armed"])
        self.assertFalse(decision["abstention_disarmed_by_purity"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertTrue(decision["abstained"])
        self.assertEqual(decision["branch"], "abstained")
        self.assertEqual(decision["reason"],
                         "evidence_opposition_gate_abstain_armed")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(m.choose(frame))
        old = GradedPurityMemory()
        for r in GATE_ARMED_ABSTAIN_ROWS:
            old.observe(r)
        self.assertEqual(old.selection()[0]["branch"], "abstained")
        graded = GradedReleaseMemory()
        for r in GATE_ARMED_ABSTAIN_ROWS:
            graded.observe(r)
        self.assertEqual(graded.selection()[0]["branch"], "abstained")

    def test_single_support_abstention_disarmed_at_raised_bar(self):
        # DISCRIMINATING for this experiment's single changed
        # element: one supporting opposed event (acting opposed
        # count exactly 3) satisfied the graded release gate but
        # does NOT satisfy the raised bar. The graded release
        # candidate abstains on these rows; this candidate records
        # the block by leg S alone and falls through to recent8.
        decision, _ = fed(SINGLE_SUPPORT_ABSTAIN_ROWS).selection()
        self.assertEqual(decision["reference_concordant_count"], 49)
        self.assertAlmostEqual(decision["reference_purity"], 0.98)
        self.assertTrue(decision["purity_armed"])
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["acting_opposed_count"], 3)
        self.assertEqual(decision["supporting_opposed_count"], 1)
        self.assertEqual(decision["support_threshold"], 4)
        self.assertFalse(decision["abstention_gate_armed"])
        self.assertFalse(decision["abstention_disarmed_by_purity"])
        self.assertTrue(decision["abstention_disarmed_by_support"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "abstention_disarmed_by_support")
        graded = GradedReleaseMemory()
        for r in SINGLE_SUPPORT_ABSTAIN_ROWS:
            graded.observe(r)
        graded_decision = graded.selection()[0]
        self.assertEqual(graded_decision["support_threshold"], 3)
        self.assertTrue(graded_decision["abstention_gate_armed"])
        self.assertEqual(graded_decision["branch"], "abstained")

    def test_authority_disarmed_abstention_has_no_gate_flags(self):
        decision, _ = fed(AUTHORITY_DISARMED_ABSTAIN_ROWS).selection()
        self.assertEqual(decision["opposed_count"], 2)
        self.assertTrue(decision["stable_disagreement"])
        self.assertFalse(decision["abstention_armed"])
        self.assertAlmostEqual(decision["reference_purity"], 0.52)
        self.assertEqual(decision["acting_opposed_count"], 8)
        self.assertEqual(decision["supporting_opposed_count"], 6)
        self.assertFalse(decision["abstention_disarmed_by_purity"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "abstention_disarmed_by_expiry")

    def test_purity_threshold_boundary_is_armed(self):
        decision, _ = fed(PURITY_BOUNDARY_ROWS).selection()
        self.assertEqual(decision["reference_matched_count"], 50)
        self.assertEqual(decision["reference_concordant_count"], 35)
        self.assertAlmostEqual(decision["reference_purity"], 0.70)
        self.assertTrue(decision["purity_armed"])
        self.assertEqual(decision["purity_threshold"], PURITY_THRESHOLD)

    def test_purity_records_exact_shape_on_pure_reference(self):
        decision, _ = fed(MINORITY_RECOVERY_ROWS).selection()
        self.assertEqual(len(decision["reference_events"]), 50)
        self.assertEqual(decision["reference_events"][0], {
            "span": 5, "reported_class": "progress",
            "reference_count": 50, "reference_majority": "progress",
            "reference_matched": True, "reference_concordant": True})
        self.assertTrue(all(r["reference_concordant"]
                            for r in decision["reference_events"]))
        self.assertEqual(decision["reference_purity"], 1.0)
        self.assertTrue(decision["purity_armed"])

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
        # Purity alone did not block this state: the carried-over
        # authority was already disarmed, so the purity flag is
        # false even though the realized purity is below threshold.
        self.assertAlmostEqual(decision["reference_purity"], 0.64)
        self.assertFalse(decision["recovery_disarmed_by_purity"])
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
        for rec in decision["reference_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class", "reference_count",
                              "reference_majority", "reference_matched",
                              "reference_concordant"})
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
        self.assertEqual(len(decision["acting_events"]), ACTING_WINDOW)
        for rec in decision["acting_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class", "reference_count",
                              "reference_majority", "matched", "opposed"})

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
        restored = AbstentionHigherCorroborationRecoveryMemory.restore(
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
        restored = AbstentionHigherCorroborationRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"],
                         "minority_archive")
        self.assertEqual(
            restored.selection()[0]["minority_discordant_count"], 30)
        self.assertTrue(restored.selection()[0]["minority_fired"])

    def test_replay_reproduces_purity_disarmed_decision(self):
        m = fed(REGULAR_PURITY_DISARMED_ROWS)
        saved = m.record()
        restored = AbstentionHigherCorroborationRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "recent8")
        self.assertTrue(
            restored.selection()[0]["recovery_disarmed_by_purity"])
        self.assertAlmostEqual(
            restored.selection()[0]["reference_purity"], 0.64)

    def test_replay_reproduces_gate_blocked_abstention(self):
        m = fed(ABSTAIN_ROWS)
        saved = m.record()
        restored = AbstentionHigherCorroborationRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "recent8")
        self.assertTrue(
            restored.selection()[0]["abstention_disarmed_by_support"])
        self.assertEqual(
            restored.selection()[0]["acting_opposed_count"], 2)

    def test_replay_reproduces_gate_armed_abstention(self):
        m = fed(GATE_ARMED_ABSTAIN_ROWS)
        saved = m.record()
        restored = AbstentionHigherCorroborationRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "abstained")
        self.assertTrue(restored.selection()[0]["abstention_gate_armed"])
        self.assertEqual(
            restored.selection()[0]["supporting_opposed_count"], 2)

    def test_replay_reproduces_single_support_disarmed_decision(self):
        m = fed(SINGLE_SUPPORT_ABSTAIN_ROWS)
        saved = m.record()
        restored = AbstentionHigherCorroborationRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "recent8")
        self.assertTrue(
            restored.selection()[0]["abstention_disarmed_by_support"])
        self.assertEqual(
            restored.selection()[0]["acting_opposed_count"], 3)

    def test_reject_invalid_events_without_partial_write(self):
        m = AbstentionHigherCorroborationRecoveryMemory()
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
            AbstentionHigherCorroborationRecoveryMemory.restore(bad)
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            AbstentionHigherCorroborationRecoveryMemory.restore(bad)
        bad2 = copy.deepcopy(saved)
        bad2["state"]["schema"] = "developmental-ai.other/v1"
        bad2["sha256"] = digest(bad2["state"])
        with self.assertRaises(ValueError):
            AbstentionHigherCorroborationRecoveryMemory.restore(bad2)

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
