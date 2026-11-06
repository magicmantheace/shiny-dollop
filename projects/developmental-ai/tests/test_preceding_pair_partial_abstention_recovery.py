"""Frozen-protocol unit tests for PrecedingPairPartialAbstentionRecoveryMemory.

Protocol: benchmarks/preceding_pair_partial_abstention_recovery_protocol.json
(frozen 2026-11-05 at 657014a, BEFORE implementation).
These tests use only handcrafted synthetic events and the ALREADY
INSPECTED stochastic cohort seed 212003 (frame/source shape only).
The frozen cohorts of this experiment (442003-family / 443001-family)
are never touched here: no cohort scores are viewed or run before or
during implementation.
"""
from __future__ import annotations

import copy
import unittest

from developmental_ai.preceding_pair_partial_abstention_recovery import (
    PrecedingPairPartialAbstentionRecoveryMemory, SCHEMA, ACTING_WINDOW,
    NEWEST_WINDOW, REFERENCE_WINDOW, LEGACY_REFERENCE_WINDOW,
    ARCHIVE_PARTITION, LOCAL_WINDOW, PRECEDING_WINDOW,
    MINIMUM_EVENTS, GATE_OPPOSED_COUNT, RECOVERY_JOINT_COUNT,
    RECENT_CONCORDANT_THRESHOLD, MINORITY_FRACTION_THRESHOLD,
    MINORITY_DISCORDANT_MINIMUM, MINORITY_JOINT_THRESHOLD,
    PURITY_THRESHOLD, SUPPORT_THRESHOLD, PRECEDING_PAIR_THRESHOLD,
)
from developmental_ai.partial_opposition_abstention_recovery import (
    PartialOppositionAbstentionRecoveryMemory as GradedPartialMemory,
)
from developmental_ai.reference_purity_gated_recovery import (
    ReferencePurityGatedRecoveryMemory as GradedPurityMemory,
)
from developmental_ai.abstention_purity_only_recovery import (
    AbstentionPurityOnlyRecoveryMemory as GradedPurityOnlyMemory,
)
from developmental_ai.abstention_higher_corroboration_recovery import (
    AbstentionHigherCorroborationRecoveryMemory as GradedHigherMemory,
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
    m = PrecedingPairPartialAbstentionRecoveryMemory()
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
# fall-through abstention is then TAKEN under the purity-only gate
# (pure reference), where both graded release gates blocked it.
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
# the minority set is empty. ZERO supporting opposed events: both
# graded release gates blocked this abstention by leg S alone;
# the purity-only gate TAKES it (the checkpoint-2 B1 case).
ABSTAIN_ROWS = ([row("progress") for _ in range(10)]
                + [row("progress") for _ in range(50)]
                + [row("damage"), row("damage")])

# PARTIAL opposition (DISCRIMINATING for this experiment's single
# changed element): same pure shape as ABSTAIN_ROWS but only ONE
# of the newest pair is opposed (damage vs the progress reference);
# the other (progress) is matched and concordant, so no joint or
# minority trigger fires. The graded purity-only candidate's
# full-pair trigger cannot take this state (it acts on recent8);
# the widened trigger TAKES the abstention, recorded as partial.
PARTIAL_ABSTAIN_ROWS = ([row("progress") for _ in range(10)]
                        + [row("progress") for _ in range(50)]
                        + [row("damage"), row("progress")])

# Partial opposition with a minority joint event: the newest
# damage event is minority-concordant AND reference-opposed
# (minority_joint_count 1) while the newest progress event is
# neither, so the minority branch - which sits ABOVE abstention -
# takes the state even though the partial trigger also fired.
MINORITY_PARTIAL_ROWS = ([row("damage") for _ in range(30)]
                         + [row("progress") for _ in range(60)]
                         + [row("progress") for _ in range(24)]
                         + [row("damage"), row("progress")])

# Partial opposition blocked by leg P alone: the multi-span
# construction of ABSTENTION_UNGATED_ROWS (reference purity 0.64)
# with the newest pair carrying exactly one opposed event
# (progress span-3 opposed, damage span-3 matched-concordant to
# the span-3 reference majority). The partial trigger fires and
# leg P disarms it; there is no support leg.
PARTIAL_PURITY_BLOCKED_ROWS = (
    [row("progress", span=5) for _ in range(40)]
    + [row("damage", span=5) for _ in range(10)]
    + [row("progress", span=3) for _ in range(38)]
    + [row("damage", span=3) for _ in range(13)]
    + [row("progress", span=9) for _ in range(7)]
    + [row("damage", span=9) for _ in range(6)]
    + [row("damage", span=5) for _ in range(4)]
    + [row("progress", span=3) for _ in range(12)]
    + [row("progress", span=9) for _ in range(8)]
    + [row("progress", span=3), row("damage", span=3)])

# PARTIAL opposition RETAINED by leg R (DISCRIMINATING for this
# experiment's single changed element): identical newest pair to
# PARTIAL_ABSTAIN_ROWS (one opposed damage, one concordant
# progress) but the PRECEDING pair (events[-4:-2]) carries one
# opposed event (damage vs the progress reference), so leg R is
# armed (preceding_pair_opposed_count 1, purity 49/50 = 0.98) and
# the partial abstention is TAKEN, exactly as the graded partial
# candidate takes it; the graded purity-only candidate, whose
# trigger requires the full pair, acts on recent8 on these rows.
RETAINED_PARTIAL_ROWS = ([row("progress") for _ in range(58)]
                         + [row("damage"), row("progress")]
                         + [row("damage"), row("progress")])

# Partial opposition blocked by leg P ALONE: the
# PARTIAL_PURITY_BLOCKED_ROWS construction with ONE preceding-pair
# event flipped to an opposed damage (span 9), so leg R is armed
# (preceding_pair_opposed_count 1) while purity falls to 0.62 -
# the block is leg P's alone: by_purity true, by_preceding false.
_purity_only_blocked = list(PARTIAL_PURITY_BLOCKED_ROWS)
_purity_only_blocked[-4] = row("damage", span=9)
PARTIAL_PURITY_ONLY_BLOCKED_ROWS = _purity_only_blocked

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
# events opposed, so that candidate abstains. Here leg P alone
# blocks the abstention (purity 0.64 disarmed); there is no support
# leg, so abstention_disarmed_by_support is false and the branch
# taken is recent8.
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

# Gate-ARMED abstention with two supporting events: the reference
# is 48 progress + 2 damage (purity 0.96, leg P armed) and both
# damage events sit among the 6 acting-window events preceding
# the newest pair, so the acting opposed count is 4 (records
# only). Both newest events are opposed damage, no
# recovery/minority trigger fires, and abstention is TAKEN,
# exactly as both graded release candidates take it on the
# same rows.
GATE_ARMED_ABSTAIN_ROWS = (
    [row("progress") for _ in range(60)]
    + [row("progress") for _ in range(44)]
    + [row("damage"), row("damage")]
    + [row("progress") for _ in range(4)]
    + [row("damage"), row("damage")])

# Single-support rows (DISCRIMINATING for the removed leg):
# identical shape to GATE_ARMED_ABSTAIN_ROWS but with only ONE
# supporting opposed event among the 6 acting-window events
# preceding the newest pair (acting opposed count 3, purity
# 0.98). The graded higher-corroboration candidate blocks this
# abstention by leg S alone (>= 4) and falls through to recent8;
# the purity-only gate TAKES it, exactly as the graded
# abstention-release candidate (>= 3) does on the same rows.
SINGLE_SUPPORT_ABSTAIN_ROWS = (
    [row("progress") for _ in range(60)]
    + [row("progress") for _ in range(44)]
    + [row("damage")]
    + [row("progress") for _ in range(5)]
    + [row("damage"), row("damage")])

# Purity leg ALONE blocks: the acting opposed count is 4 (two
# supporting opposed events, the span-9 damage pair, records
# only) while purity is 0.60 (leg P disarmed). The flags are
# recorded individually: by_purity true, by_support false
# (always - there is no support leg).
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


class PrecedingPairPartialAbstentionRecoveryTests(unittest.TestCase):
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
        self.assertEqual(GATE_OPPOSED_COUNT, 1)
        self.assertEqual(RECOVERY_JOINT_COUNT, 1)
        self.assertEqual(RECENT_CONCORDANT_THRESHOLD, 2)
        self.assertEqual(MINORITY_FRACTION_THRESHOLD, 0.25)
        self.assertEqual(MINORITY_DISCORDANT_MINIMUM, 8)
        self.assertEqual(MINORITY_JOINT_THRESHOLD, 1)
        self.assertEqual(PURITY_THRESHOLD, 0.70)
        self.assertIsNone(SUPPORT_THRESHOLD)
        self.assertEqual(PRECEDING_PAIR_THRESHOLD, 1)

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
        self.assertIsNone(decision["support_threshold"])
        self.assertIsNone(decision["abstention_support_threshold"])
        self.assertFalse(decision["abstention_gate_armed"])
        self.assertFalse(decision["abstention_disarmed_by_purity"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertEqual(decision["abstention_trigger_kind"], "none")
        self.assertEqual(decision["preceding_pair_events"], [])
        self.assertEqual(decision["preceding_pair_matched_count"], 0)
        self.assertEqual(decision["preceding_pair_opposed_count"], 0)
        self.assertFalse(decision["preceding_pair_armed"])
        self.assertEqual(decision["preceding_pair_threshold"], 1)
        self.assertFalse(
            decision["abstention_disarmed_by_preceding_pair"])
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
            PrecedingPairPartialAbstentionRecoveryMemory().selection()
        with self.assertRaises(ValueError):
            PrecedingPairPartialAbstentionRecoveryMemory().record()

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
        # The fall-through abstention is TAKEN under the
        # purity-only gate (pure reference, no support leg),
        # exactly as the graded purity candidate abstained on
        # these rows; both graded release gates blocked it.
        self.assertTrue(decision["abstained"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertFalse(decision["abstention_disarmed_by_purity"])
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
        self.assertTrue(decision["abstained"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertEqual(decision["branch"], "abstained")

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

    def test_abstention_blocked_by_purity_leg_alone(self):
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
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertIsNone(decision["support_threshold"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        old = GradedPurityMemory()
        for r in ABSTENTION_UNGATED_ROWS:
            old.observe(r)
        self.assertEqual(old.selection()[0]["branch"], "abstained")

    def test_abstention_taken_with_zero_supporting_events(self):
        # DISCRIMINATING for this experiment's single changed
        # element: ABSTAIN_ROWS - pure reference (purity 1.0, leg
        # P armed), opposed pair, and NO supporting opposed event
        # among the preceding 6 acting-window events. Both graded
        # release gates blocked this abstention by leg S alone;
        # the purity-only gate takes it, as the graded purity
        # candidate (no abstention gate) did on the same rows.
        m = fed(ABSTAIN_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["minority_discordant_count"], 0)
        self.assertFalse(decision["minority_armed"])
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["reference_purity"], 1.0)
        self.assertTrue(decision["purity_armed"])
        self.assertEqual(decision["acting_opposed_count"], 2)
        self.assertEqual(decision["supporting_opposed_count"], 0)
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
        for r in ABSTAIN_ROWS:
            old.observe(r)
        self.assertEqual(old.selection()[0]["branch"], "abstained")
        graded = GradedHigherMemory()
        for r in ABSTAIN_ROWS:
            graded.observe(r)
        self.assertEqual(graded.selection()[0]["branch"], "recent8")
        self.assertTrue(
            graded.selection()[0]["abstention_disarmed_by_support"])

    def test_partial_abstention_disarmed_by_preceding_pair(self):
        # DISCRIMINATING for this experiment's single changed
        # element: opposed_count exactly 1 (partial), pure
        # reference (leg P armed), authority armed, no recovery
        # or minority trigger - but the preceding pair carries NO
        # opposed event (both progress, concordant), so leg R
        # alone disarms the partial abstention and the learner
        # acts on recent8. The graded partial candidate, which
        # has no leg R, TAKES the abstention on the same rows;
        # the graded purity-only candidate acts on recent8
        # because its trigger requires the full pair.
        m = fed(PARTIAL_ABSTAIN_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["abstention_trigger_kind"], "partial")
        self.assertTrue(decision["abstention_would_fire"])
        self.assertEqual(decision["joint_count"], 0)
        self.assertEqual(decision["minority_joint_count"], 0)
        self.assertEqual(decision["reference_purity"], 1.0)
        self.assertTrue(decision["purity_armed"])
        self.assertEqual(decision["preceding_pair_events"], [
            {"span": 5, "reported_class": "progress",
             "reference_count": 50, "reference_majority": "progress",
             "matched": True, "opposed": False},
            {"span": 5, "reported_class": "progress",
             "reference_count": 50, "reference_majority": "progress",
             "matched": True, "opposed": False},
        ])
        self.assertEqual(decision["preceding_pair_matched_count"], 2)
        self.assertEqual(decision["preceding_pair_opposed_count"], 0)
        self.assertFalse(decision["preceding_pair_armed"])
        self.assertEqual(decision["preceding_pair_threshold"], 1)
        self.assertFalse(decision["abstention_gate_armed"])
        self.assertFalse(decision["abstention_disarmed_by_purity"])
        self.assertTrue(
            decision["abstention_disarmed_by_preceding_pair"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "abstention_disarmed_by_preceding_pair")
        self.assertEqual(decision["gate_opposed_threshold"], 1)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNotNone(m.choose(frame))
        graded = GradedPartialMemory()
        for r in PARTIAL_ABSTAIN_ROWS:
            graded.observe(r)
        graded_decision = graded.selection()[0]
        self.assertEqual(graded_decision["opposed_count"], 1)
        self.assertTrue(graded_decision["abstained"])
        self.assertEqual(graded_decision["branch"], "abstained")
        purity_only = GradedPurityOnlyMemory()
        for r in PARTIAL_ABSTAIN_ROWS:
            purity_only.observe(r)
        self.assertEqual(purity_only.selection()[0]["branch"], "recent8")

    def test_partial_abstention_retained_when_preceding_pair_opposed(self):
        # DISCRIMINATING, retained side: the same partial newest
        # pair as PARTIAL_ABSTAIN_ROWS, but the preceding pair
        # carries one opposed event, so leg R is armed and the
        # composite gate (leg P AND leg R) takes the abstention,
        # exactly as the graded partial candidate does; the
        # graded purity-only candidate acts on recent8.
        m = fed(RETAINED_PARTIAL_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["abstention_trigger_kind"], "partial")
        self.assertTrue(decision["abstention_would_fire"])
        self.assertEqual(decision["preceding_pair_opposed_count"], 1)
        self.assertEqual(decision["preceding_pair_matched_count"], 2)
        self.assertTrue(decision["preceding_pair_armed"])
        self.assertAlmostEqual(decision["reference_purity"], 0.98)
        self.assertTrue(decision["purity_armed"])
        self.assertTrue(decision["abstention_gate_armed"])
        self.assertFalse(decision["abstention_disarmed_by_purity"])
        self.assertFalse(
            decision["abstention_disarmed_by_preceding_pair"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertTrue(decision["abstained"])
        self.assertEqual(decision["branch"], "abstained")
        self.assertEqual(decision["reason"],
                         "evidence_opposition_gate_abstain_armed")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(m.choose(frame))
        graded = GradedPartialMemory()
        for r in RETAINED_PARTIAL_ROWS:
            graded.observe(r)
        self.assertEqual(graded.selection()[0]["branch"], "abstained")
        purity_only = GradedPurityOnlyMemory()
        for r in RETAINED_PARTIAL_ROWS:
            purity_only.observe(r)
        self.assertEqual(purity_only.selection()[0]["branch"], "recent8")

    def test_full_abstention_ignores_preceding_pair(self):
        # A FULL trigger (opposed_count 2) fires behind leg P
        # alone, whatever the preceding pair says: on
        # ABSTAIN_ROWS the preceding pair is fully concordant
        # (preceding_pair_armed false) yet the abstention is
        # TAKEN and no preceding-pair disarming is recorded.
        decision, _ = fed(ABSTAIN_ROWS).selection()
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["abstention_trigger_kind"], "full")
        self.assertEqual(decision["preceding_pair_opposed_count"], 0)
        self.assertFalse(decision["preceding_pair_armed"])
        self.assertTrue(decision["purity_armed"])
        self.assertTrue(decision["abstention_gate_armed"])
        self.assertFalse(
            decision["abstention_disarmed_by_preceding_pair"])
        self.assertTrue(decision["abstained"])
        self.assertEqual(decision["branch"], "abstained")

    def test_trigger_kind_full_partial_and_none(self):
        full, _ = fed(ABSTAIN_ROWS).selection()
        self.assertEqual(full["opposed_count"], 2)
        self.assertEqual(full["abstention_trigger_kind"], "full")
        partial, _ = fed(PARTIAL_ABSTAIN_ROWS).selection()
        self.assertEqual(partial["abstention_trigger_kind"], "partial")
        # Composite gate: full and none record purity_armed.
        self.assertTrue(full["purity_armed"])
        self.assertTrue(full["abstention_gate_armed"])
        rows = [row("progress") for _ in range(60)]
        none_decision, _ = fed(rows).selection()
        self.assertEqual(none_decision["opposed_count"], 0)
        self.assertEqual(none_decision["abstention_trigger_kind"], "none")
        self.assertFalse(none_decision["abstention_would_fire"])
        self.assertEqual(none_decision["branch"], "recent8")
        self.assertEqual(none_decision["abstention_gate_armed"],
                         none_decision["purity_armed"])

    def test_partial_abstention_blocked_by_purity_leg_alone(self):
        # Leg R is ARMED here (preceding_pair_opposed_count 1),
        # so the block is leg P's alone: by_purity true,
        # by_preceding_pair false.
        decision, _ = fed(PARTIAL_PURITY_ONLY_BLOCKED_ROWS).selection()
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["abstention_trigger_kind"], "partial")
        self.assertTrue(decision["abstention_would_fire"])
        self.assertAlmostEqual(decision["reference_purity"], 0.62)
        self.assertFalse(decision["purity_armed"])
        self.assertEqual(decision["preceding_pair_opposed_count"], 1)
        self.assertTrue(decision["preceding_pair_armed"])
        self.assertTrue(decision["abstention_armed"])
        self.assertFalse(decision["abstention_gate_armed"])
        self.assertTrue(decision["abstention_disarmed_by_purity"])
        self.assertFalse(
            decision["abstention_disarmed_by_preceding_pair"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")

    def test_partial_abstention_blocked_by_both_legs(self):
        # The unmodified multi-span construction: purity 0.64
        # (leg P disarmed) AND a fully concordant preceding pair
        # (leg R disarmed) - a partial blocked by both legs is
        # recorded under BOTH flags.
        decision, _ = fed(PARTIAL_PURITY_BLOCKED_ROWS).selection()
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["abstention_trigger_kind"], "partial")
        self.assertTrue(decision["abstention_would_fire"])
        self.assertAlmostEqual(decision["reference_purity"], 0.64)
        self.assertFalse(decision["purity_armed"])
        self.assertEqual(decision["preceding_pair_opposed_count"], 0)
        self.assertFalse(decision["preceding_pair_armed"])
        self.assertFalse(decision["abstention_gate_armed"])
        self.assertTrue(decision["abstention_disarmed_by_purity"])
        self.assertTrue(
            decision["abstention_disarmed_by_preceding_pair"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")

    def test_minority_recovery_precedes_partial_abstention(self):
        decision, _ = fed(MINORITY_PARTIAL_ROWS).selection()
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["abstention_trigger_kind"], "partial")
        self.assertEqual(decision["minority_joint_count"], 1)
        self.assertTrue(decision["minority_armed"])
        self.assertTrue(decision["minority_fired"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "minority_archive")

    def test_replay_reproduces_partial_abstention(self):
        m = fed(RETAINED_PARTIAL_ROWS)
        saved = m.record()
        restored = PrecedingPairPartialAbstentionRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "abstained")
        self.assertEqual(
            restored.selection()[0]["abstention_trigger_kind"], "partial")
        self.assertEqual(restored.selection()[0]["opposed_count"], 1)
        self.assertEqual(
            restored.selection()[0]["preceding_pair_opposed_count"], 1)
        self.assertTrue(restored.selection()[0]["preceding_pair_armed"])

    def test_replay_reproduces_preceding_disarmed_partial(self):
        m = fed(PARTIAL_ABSTAIN_ROWS)
        saved = m.record()
        restored = PrecedingPairPartialAbstentionRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "recent8")
        self.assertTrue(
            restored.selection()[0][
                "abstention_disarmed_by_preceding_pair"])
        self.assertEqual(
            restored.selection()[0]["preceding_pair_opposed_count"], 0)

    def test_abstention_blocked_by_purity_with_support_present(self):
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

    def test_single_support_abstention_taken_without_support_leg(self):
        # DISCRIMINATING for this experiment's single changed
        # element: one supporting opposed event (acting opposed
        # count exactly 3, records only) satisfied the graded
        # release gate (>= 3) but NOT the graded higher bar
        # (>= 4). With leg S removed the purity-only gate takes
        # the abstention on leg P alone, exactly as the graded
        # release candidate does; the graded higher-corroboration
        # candidate blocks it by leg S alone.
        decision, _ = fed(SINGLE_SUPPORT_ABSTAIN_ROWS).selection()
        self.assertEqual(decision["reference_concordant_count"], 49)
        self.assertAlmostEqual(decision["reference_purity"], 0.98)
        self.assertTrue(decision["purity_armed"])
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["acting_opposed_count"], 3)
        self.assertEqual(decision["supporting_opposed_count"], 1)
        self.assertIsNone(decision["support_threshold"])
        self.assertTrue(decision["abstention_gate_armed"])
        self.assertFalse(decision["abstention_disarmed_by_purity"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertTrue(decision["abstained"])
        self.assertEqual(decision["branch"], "abstained")
        self.assertEqual(decision["reason"],
                         "evidence_opposition_gate_abstain_armed")
        graded = GradedReleaseMemory()
        for r in SINGLE_SUPPORT_ABSTAIN_ROWS:
            graded.observe(r)
        graded_decision = graded.selection()[0]
        self.assertEqual(graded_decision["support_threshold"], 3)
        self.assertTrue(graded_decision["abstention_gate_armed"])
        self.assertEqual(graded_decision["branch"], "abstained")
        higher = GradedHigherMemory()
        for r in SINGLE_SUPPORT_ABSTAIN_ROWS:
            higher.observe(r)
        higher_decision = higher.selection()[0]
        self.assertEqual(higher_decision["support_threshold"], 4)
        self.assertFalse(higher_decision["abstention_gate_armed"])
        self.assertTrue(
            higher_decision["abstention_disarmed_by_support"])
        self.assertEqual(higher_decision["branch"], "recent8")

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
        self.assertEqual(len(decision["preceding_pair_events"]), 2)
        for rec in decision["preceding_pair_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class", "reference_count",
                              "reference_majority", "matched", "opposed"})
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
        restored = PrecedingPairPartialAbstentionRecoveryMemory.restore(
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
        restored = PrecedingPairPartialAbstentionRecoveryMemory.restore(
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
        restored = PrecedingPairPartialAbstentionRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "recent8")
        self.assertTrue(
            restored.selection()[0]["recovery_disarmed_by_purity"])
        self.assertAlmostEqual(
            restored.selection()[0]["reference_purity"], 0.64)

    def test_replay_reproduces_gate_blocked_abstention(self):
        m = fed(ABSTENTION_UNGATED_ROWS)
        saved = m.record()
        restored = PrecedingPairPartialAbstentionRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "recent8")
        self.assertTrue(
            restored.selection()[0]["abstention_disarmed_by_purity"])
        self.assertFalse(
            restored.selection()[0]["abstention_disarmed_by_support"])
        self.assertIsNone(restored.selection()[0]["support_threshold"])
        self.assertEqual(
            restored.selection()[0]["acting_opposed_count"], 2)

    def test_replay_reproduces_zero_support_abstention(self):
        m = fed(ABSTAIN_ROWS)
        saved = m.record()
        restored = PrecedingPairPartialAbstentionRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "abstained")
        self.assertTrue(restored.selection()[0]["abstention_gate_armed"])
        self.assertEqual(
            restored.selection()[0]["supporting_opposed_count"], 0)

    def test_replay_reproduces_gate_armed_abstention(self):
        m = fed(GATE_ARMED_ABSTAIN_ROWS)
        saved = m.record()
        restored = PrecedingPairPartialAbstentionRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "abstained")
        self.assertTrue(restored.selection()[0]["abstention_gate_armed"])
        self.assertEqual(
            restored.selection()[0]["supporting_opposed_count"], 2)

    def test_replay_reproduces_single_support_abstention(self):
        m = fed(SINGLE_SUPPORT_ABSTAIN_ROWS)
        saved = m.record()
        restored = PrecedingPairPartialAbstentionRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "abstained")
        self.assertTrue(restored.selection()[0]["abstention_gate_armed"])
        self.assertEqual(
            restored.selection()[0]["acting_opposed_count"], 3)

    def test_reject_invalid_events_without_partial_write(self):
        m = PrecedingPairPartialAbstentionRecoveryMemory()
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
            PrecedingPairPartialAbstentionRecoveryMemory.restore(bad)
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            PrecedingPairPartialAbstentionRecoveryMemory.restore(bad)
        bad2 = copy.deepcopy(saved)
        bad2["state"]["schema"] = "developmental-ai.other/v1"
        bad2["sha256"] = digest(bad2["state"])
        with self.assertRaises(ValueError):
            PrecedingPairPartialAbstentionRecoveryMemory.restore(bad2)

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
