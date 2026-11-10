"""Frozen-protocol unit tests for CompanionConcordancePartialRecoveryMemory.

Protocol: benchmarks/companion_concordance_partial_recovery_protocol.json
(frozen 2026-11-10 at af1fc1b, BEFORE implementation).
These tests use only handcrafted synthetic events and the ALREADY
INSPECTED stochastic cohort seed 212003 (frame/source shape only).
The frozen cohorts of this experiment (492003-family / 493001-family)
are never touched here: no cohort scores are viewed or run before or
during implementation.
"""
from __future__ import annotations

import copy
import unittest

from developmental_ai.companion_concordance_partial_recovery import (
    CompanionConcordancePartialRecoveryMemory, SCHEMA, ACTING_WINDOW,
    NEWEST_WINDOW, REFERENCE_WINDOW, LEGACY_REFERENCE_WINDOW,
    ARCHIVE_PARTITION, LOCAL_WINDOW, PRECEDING_WINDOW,
    MINIMUM_EVENTS, GATE_OPPOSED_COUNT, RECOVERY_JOINT_COUNT,
    RECENT_CONCORDANT_THRESHOLD, MINORITY_FRACTION_THRESHOLD,
    MINORITY_DISCORDANT_MINIMUM, MINORITY_JOINT_THRESHOLD,
    PURITY_THRESHOLD, SUPPORT_THRESHOLD, PRECEDING_PAIR_THRESHOLD,
    WIDENED_THRESHOLD, STALE_WINDOW, STALENESS_PAIR_THRESHOLD,
    COMPANION_THRESHOLD,
)
from developmental_ai.pre_acting_joint_release_recovery import (
    PreActingJointReleaseRecoveryMemory as GradedPreActingMemory,
)
from developmental_ai.widened_window_abstention_recovery import (
    WidenedWindowAbstentionRecoveryMemory as GradedWidenedMemory,
)
from developmental_ai.widened_class_removal_recovery import (
    WidenedClassRemovalRecoveryMemory as GradedRemovalMemory,
)
from developmental_ai.inverted_archive_minority_recovery import (
    InvertedArchiveMinorityRecoveryMemory as GradedInvertedMemory,
)
from developmental_ai.preceding_pair_partial_abstention_recovery import (
    PrecedingPairPartialAbstentionRecoveryMemory as GradedPrecedingMemory,
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
    m = CompanionConcordancePartialRecoveryMemory()
    for r in rows:
        m.observe(r)
    return m


def plain_model(rows):
    m = RelationOutcomeMemory()
    for r in rows:
        m.observe(r)
    return m


def swapped(row_):
    return {"features": dict(row_["features"]),
            "progress": row_["damage"], "damage": row_["progress"]}


def inverted_model(rows):
    return plain_model([swapped(r) for r in rows])


STALE_KEYS = {"stale_joint_events", "stale_minority_joint_events",
              "stale_joint_pair_count", "stale_minority_joint_pair_count",
              "staleness_pair_threshold", "recovery_disarmed_by_staleness",
              "minority_disarmed_by_staleness"}

COMPANION_KEYS = {"companion_matched", "companion_concordant",
                  "companion_armed", "companion_threshold",
                  "abstention_disarmed_by_companion"}


def stripped_stale(decision):
    return {k: v for k, v in decision.items()
            if k not in STALE_KEYS and k not in COMPANION_KEYS}


def stripped_companion(decision):
    return {k: v for k, v in decision.items()
            if k not in COMPANION_KEYS}


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

# WIDENED-ARMED, silent newest four (DISCRIMINATING for this
# experiment's single changed element): pure progress base; the
# last 8 are D,D,D,P,P,P,P,P - the newest pair and its
# predecessor are both fully concordant (newest4_opposed_count
# 0, opposed_count 0) but the older four of the acting window
# carry 3 opposed damage events (acting_opposed_count 3), so
# widened_armed is True records-only (purity 0.94). The graded
# inverted-archive candidate ABSTAINS as kind widened on these
# rows; this candidate, the widened class being removed, ACTS
# on recent8, exactly as the graded preceding-pair candidate does.
WIDENED_SILENT_ROWS = (
    [row("progress") for _ in range(60)]
    + [row("damage"), row("damage"), row("damage"),
       row("progress"), row("progress"), row("progress"),
       row("progress"), row("progress")])

# WIDENED-ARMED, split / partial configuration: newest pair is
# damage+progress (opposed_count 1), preceding pair is fully
# concordant (preceding_pair_opposed_count 0, newest4 total 1),
# and the older acting events bring acting_opposed_count to 3.
# The graded inverted-archive candidate records this as kind
# 'widened' and TAKES it behind leg P alone; this candidate
# records it as a partial DISARMED by leg R, exactly as the
# graded preceding-pair candidate does (purity 0.96).
WIDENED_SPLIT_ROWS = (
    [row("progress") for _ in range(60)]
    + [row("damage"), row("damage"), row("progress"),
       row("progress"), row("progress"), row("progress"),
       row("damage"), row("progress")])

# Widened NOT armed at acting_opposed_count 2: same silent
# shape with only 2 opposed events in the older acting window -
# below the frozen threshold 3, so kind is 'none' and the
# learner acts on recent8, exactly as the graded
# preceding-pair candidate does.
WIDENED_BELOW_THRESHOLD_ROWS = (
    [row("progress") for _ in range(60)]
    + [row("damage"), row("damage"), row("progress"),
       row("progress"), row("progress"), row("progress"),
       row("progress"), row("progress")])

# Widened NOT armed when newest4 >= 2: newest pair silent
# (opposed 0) but the preceding pair is fully opposed
# (preceding 2, newest4 2) and acting_opposed_count is 3 - the
# population bound <= 1 fails, so kind is 'none' and the
# learner acts on recent8.
WIDENED_NEWEST4_TOO_HIGH_ROWS = (
    [row("progress") for _ in range(60)]
    + [row("damage"), row("progress"), row("progress"),
       row("progress"), row("damage"), row("damage"),
       row("progress"), row("progress")])

# Widened-ARMED, purity low: interleaved reference
# (purity 32/50 = 0.64) with the same silent widened shape as
# WIDENED_SILENT_ROWS at its tail (newest4 0, acting 3).
# widened_armed is True records-only, but there is no trigger
# of any remaining class (opposed 0), so kind is 'none', no
# abstention disarming is recorded, and the learner acts on
# recent8. The graded inverted-archive candidate records this
# state as kind widened disarmed by purity.
WIDENED_PURITY_BLOCKED_ROWS = (
    [row("progress") for _ in range(60)]
    + [row("damage") if i % 3 == 0 else row("progress")
       for i in range(44)]
    + [row("damage"), row("damage"), row("damage"),
       row("progress"), row("progress"), row("progress")]
    + [row("progress"), row("progress")])


# REGULAR branch stale-disarmed (DISCRIMINATING for leg T):
# archive 60 progress + 40 damage (majority progress); the
# reference is damage-majority (purity 0.92). The stale window
# opens with FOUR progress events - archive-concordant AND
# reference-opposed, i.e. joint - forming TWO full joint pairs
# (stale_joint_pair_count 2), and the newest pair is progress /
# progress (joint_count 2), so the graded widened-removal
# candidate FIRES retained_archive while leg T stands this
# candidate down to recent8 (the abstention branch is
# authority-disarmed by the local damage majority).
REGULAR_STALE_DISARMED_ROWS = (
    [row("progress") for _ in range(60)]
    + [row("damage") for _ in range(40)]
    + [row("progress") for _ in range(4)]
    + [row("damage") for _ in range(14)]
    + [row("damage") for _ in range(6)]
    + [row("progress"), row("progress")])

# Same construction with only ONE full stale joint pair (the
# stale window opens progress / progress then damage): leg T
# does not stand the branch down and both candidates fire
# retained_archive identically (stale_joint_pair_count 1).
REGULAR_STALE_ONE_PAIR_ROWS = (
    [row("progress") for _ in range(60)]
    + [row("damage") for _ in range(40)]
    + [row("progress") for _ in range(2)]
    + [row("damage") for _ in range(16)]
    + [row("damage") for _ in range(6)]
    + [row("progress"), row("progress")])

# MINORITY branch stale-disarmed (DISCRIMINATING for leg T):
# archive 30 damage + 60 progress (minority set = the 30 damage
# events, fraction 1/3, armed); the reference is
# progress-majority (purity 0.92). The stale window opens with
# FOUR damage events - minority-concordant AND reference-opposed,
# i.e. minority-joint - forming TWO full minority joint pairs
# (stale_minority_joint_pair_count 2; the regular stale count is
# 0), and the newest pair is damage / damage (minority_joint 2,
# regular joint 0), so the graded widened-removal candidate
# FIRES minority_archive while leg T stands this candidate's
# minority branch down and the decision falls through to the
# full abstention trigger (taken behind leg P).
MINORITY_STALE_DISARMED_ROWS = (
    [row("damage") for _ in range(30)]
    + [row("progress") for _ in range(60)]
    + [row("damage") for _ in range(4)]
    + [row("progress") for _ in range(14)]
    + [row("progress") for _ in range(6)]
    + [row("damage"), row("damage")])

# Same construction with only ONE full stale minority joint
# pair: leg T does not stand the branch down and both candidates
# fire minority_archive identically
# (stale_minority_joint_pair_count 1).
MINORITY_STALE_ONE_PAIR_ROWS = (
    [row("damage") for _ in range(30)]
    + [row("progress") for _ in range(60)]
    + [row("damage") for _ in range(2)]
    + [row("progress") for _ in range(16)]
    + [row("progress") for _ in range(6)]
    + [row("damage"), row("damage")])


class CompanionConcordancePartialRecoveryTests(unittest.TestCase):
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
        self.assertEqual(WIDENED_THRESHOLD, 3)
        self.assertEqual(STALE_WINDOW, 18)
        self.assertIsNone(COMPANION_THRESHOLD)
        self.assertEqual(STALE_WINDOW, LOCAL_WINDOW - ACTING_WINDOW)
        self.assertEqual(STALENESS_PAIR_THRESHOLD, 2)

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
        self.assertEqual(decision["minority_model_archive_count"], 0)
        self.assertTrue(decision["minority_model_inverted"])
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
        self.assertFalse(decision["companion_matched"])
        self.assertFalse(decision["companion_concordant"])
        self.assertFalse(decision["companion_armed"])
        self.assertIsNone(decision["companion_threshold"])
        self.assertIsNone(COMPANION_THRESHOLD)
        self.assertFalse(decision["abstention_disarmed_by_companion"])
        self.assertEqual(decision["newest4_opposed_count"], 0)
        self.assertFalse(decision["widened_armed"])
        self.assertEqual(decision["widened_threshold"], 3)
        self.assertEqual(decision["stale_joint_events"], [])
        self.assertEqual(decision["stale_minority_joint_events"], [])
        self.assertEqual(decision["stale_joint_pair_count"], 0)
        self.assertEqual(decision["stale_minority_joint_pair_count"], 0)
        self.assertEqual(decision["staleness_pair_threshold"], 2)
        self.assertFalse(decision["recovery_disarmed_by_staleness"])
        self.assertFalse(decision["minority_disarmed_by_staleness"])
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
            CompanionConcordancePartialRecoveryMemory().selection()
        with self.assertRaises(ValueError):
            CompanionConcordancePartialRecoveryMemory().record()

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
        # The minority model is the INVERTED archive model: all 90
        # archive events with progress/damage swapped (the graded
        # widened candidate's model held only the 30 discordant
        # events, unswapped).
        self.assertEqual(decision["minority_model_archive_count"], 90)
        self.assertEqual(decision["minority_model_archive_count"],
                         decision["archive_events_count"])
        self.assertTrue(decision["minority_model_inverted"])
        self.assertEqual(model.events,
                         [swapped(r)
                          for r in MINORITY_RECOVERY_ROWS[:90]])
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(
            m.choose(frame),
            inverted_model(MINORITY_RECOVERY_ROWS[:90]).choose(frame))

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
        # Carried discriminating state (leg R's disarming side in
        # the preceding-pair generation): opposed_count exactly 1
        # (partial), pure reference (leg P armed), authority
        # armed, no recovery or minority trigger - but the
        # preceding pair carries NO opposed event (both progress,
        # concordant), so leg R fails; in THIS candidate the
        # companion is also concordant, so leg C fails too and
        # the partial abstention is still disarmed, the learner
        # acting on recent8 exactly as the decisive baseline
        # (the graded pre-acting candidate) does. The graded
        # partial candidate, which has no leg R, TAKES the
        # abstention on the same rows; the graded purity-only
        # candidate acts on recent8 because its trigger requires
        # the full pair.
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
        # The companion (the newest pair's progress event) is
        # matched and concordant, so leg C is disarmed too: the
        # corroboration condition (leg R OR leg C) failed with
        # both legs failing, recorded under BOTH flags.
        self.assertTrue(decision["companion_matched"])
        self.assertTrue(decision["companion_concordant"])
        self.assertFalse(decision["companion_armed"])
        self.assertIsNone(decision["companion_threshold"])
        self.assertTrue(decision["abstention_disarmed_by_companion"])
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

    def test_widened_silent_abstention_taken(self):
        # DISCRIMINATING for this experiment's single changed
        # element: silent newest four, acting count 3. The
        # widened class is removed, so this candidate ACTS on
        # recent8 where the graded inverted-archive candidate
        # ABSTAINS as kind widened on the same rows.
        m = fed(WIDENED_SILENT_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["opposed_count"], 0)
        self.assertEqual(decision["preceding_pair_opposed_count"], 0)
        self.assertEqual(decision["newest4_opposed_count"], 0)
        self.assertEqual(
            decision["newest4_opposed_count"],
            decision["opposed_count"]
            + decision["preceding_pair_opposed_count"])
        self.assertEqual(decision["acting_opposed_count"], 3)
        self.assertTrue(decision["widened_armed"])
        self.assertEqual(decision["widened_threshold"], 3)
        self.assertEqual(decision["abstention_trigger_kind"], "none")
        self.assertFalse(decision["abstention_would_fire"])
        self.assertAlmostEqual(decision["reference_purity"], 0.94)
        self.assertTrue(decision["purity_armed"])
        self.assertTrue(decision["abstention_gate_armed"])
        self.assertEqual(decision["abstention_gate_armed"],
                         decision["purity_armed"])
        self.assertFalse(decision["abstention_disarmed_by_purity"])
        self.assertFalse(
            decision["abstention_disarmed_by_preceding_pair"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertIsNone(decision["support_threshold"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNotNone(m.choose(frame))
        graded = GradedInvertedMemory()
        for r in WIDENED_SILENT_ROWS:
            graded.observe(r)
        graded_decision = graded.selection()[0]
        self.assertEqual(graded_decision["abstention_trigger_kind"],
                         "widened")
        self.assertTrue(graded_decision["abstained"])
        self.assertEqual(graded_decision["branch"], "abstained")
        self.assertIsNone(graded.choose(frame))
        preceding = GradedPrecedingMemory()
        for r in WIDENED_SILENT_ROWS:
            preceding.observe(r)
        self.assertEqual(preceding.selection()[0]["branch"], "recent8")

    def test_widened_split_abstention_taken_as_widened(self):
        # A partial configuration (opposed 1, preceding 0) with
        # acting 3: the graded inverted-archive candidate credits
        # this to the widened class and TAKES it; this candidate
        # records kind partial, disarmed by the corroboration
        # condition (leg R fails and the companion is concordant,
        # so leg C fails too), and acts on recent8, exactly as
        # the graded preceding-pair candidate and the decisive
        # pre-acting baseline do.
        m = fed(WIDENED_SPLIT_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["preceding_pair_opposed_count"], 0)
        self.assertEqual(decision["newest4_opposed_count"], 1)
        self.assertEqual(decision["acting_opposed_count"], 3)
        self.assertTrue(decision["widened_armed"])
        self.assertEqual(decision["abstention_trigger_kind"], "partial")
        self.assertTrue(decision["abstention_would_fire"])
        self.assertAlmostEqual(decision["reference_purity"], 0.96)
        self.assertTrue(decision["purity_armed"])
        self.assertFalse(decision["preceding_pair_armed"])
        self.assertTrue(decision["companion_matched"])
        self.assertTrue(decision["companion_concordant"])
        self.assertFalse(decision["companion_armed"])
        self.assertFalse(decision["abstention_gate_armed"])
        self.assertTrue(
            decision["abstention_disarmed_by_preceding_pair"])
        self.assertTrue(decision["abstention_disarmed_by_companion"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNotNone(m.choose(frame))
        graded = GradedInvertedMemory()
        for r in WIDENED_SPLIT_ROWS:
            graded.observe(r)
        graded_decision = graded.selection()[0]
        self.assertEqual(graded_decision["abstention_trigger_kind"],
                         "widened")
        self.assertTrue(graded_decision["abstained"])
        self.assertEqual(graded_decision["branch"], "abstained")
        preceding = GradedPrecedingMemory()
        for r in WIDENED_SPLIT_ROWS:
            preceding.observe(r)
        graded_decision = preceding.selection()[0]
        self.assertEqual(graded_decision["abstention_trigger_kind"],
                         "partial")
        self.assertTrue(
            graded_decision["abstention_disarmed_by_preceding_pair"])
        self.assertEqual(graded_decision["branch"], "recent8")

    def test_widened_below_acting_threshold_not_armed(self):
        decision, _ = fed(WIDENED_BELOW_THRESHOLD_ROWS).selection()
        self.assertEqual(decision["opposed_count"], 0)
        self.assertEqual(decision["newest4_opposed_count"], 0)
        self.assertEqual(decision["acting_opposed_count"], 2)
        self.assertFalse(decision["widened_armed"])
        self.assertEqual(decision["abstention_trigger_kind"], "none")
        self.assertFalse(decision["abstention_would_fire"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")

    def test_widened_newest4_bound_blocks_class(self):
        decision, _ = fed(WIDENED_NEWEST4_TOO_HIGH_ROWS).selection()
        self.assertEqual(decision["opposed_count"], 0)
        self.assertEqual(decision["preceding_pair_opposed_count"], 2)
        self.assertEqual(decision["newest4_opposed_count"], 2)
        self.assertEqual(decision["acting_opposed_count"], 3)
        self.assertFalse(decision["widened_armed"])
        self.assertEqual(decision["abstention_trigger_kind"], "none")
        self.assertFalse(decision["abstention_would_fire"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")

    def test_widened_abstention_blocked_by_purity_leg_alone(self):
        # Renamed in substance for this candidate: widened_armed
        # is records-only and opposed is 0, so there is no trigger
        # to disarm; kind is none and no disarming flag is set.
        decision, _ = fed(WIDENED_PURITY_BLOCKED_ROWS).selection()
        self.assertEqual(decision["opposed_count"], 0)
        self.assertEqual(decision["newest4_opposed_count"], 0)
        self.assertEqual(decision["acting_opposed_count"], 3)
        self.assertTrue(decision["widened_armed"])
        self.assertEqual(decision["abstention_trigger_kind"], "none")
        self.assertFalse(decision["abstention_would_fire"])
        self.assertAlmostEqual(decision["reference_purity"], 0.64)
        self.assertFalse(decision["purity_armed"])
        self.assertTrue(decision["abstention_armed"])
        self.assertFalse(decision["abstention_gate_armed"])
        self.assertFalse(decision["abstention_disarmed_by_purity"])
        self.assertFalse(
            decision["abstention_disarmed_by_preceding_pair"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "evidence_opposition_gate_pass")

    def test_replay_reproduces_widened_abstention(self):
        # Replay reproduces the widened-armed records-only state
        # and the recent8 choice identically.
        m = fed(WIDENED_SILENT_ROWS)
        saved = m.record()
        restored = CompanionConcordancePartialRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "recent8")
        self.assertEqual(
            restored.selection()[0]["abstention_trigger_kind"],
            "none")
        self.assertEqual(
            restored.selection()[0]["newest4_opposed_count"], 0)
        self.assertTrue(restored.selection()[0]["widened_armed"])
        self.assertEqual(
            restored.selection()[0]["acting_opposed_count"], 3)

    def test_replay_reproduces_widened_split_abstention(self):
        m = fed(WIDENED_SPLIT_ROWS)
        saved = m.record()
        restored = CompanionConcordancePartialRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(
            restored.selection()[0]["abstention_trigger_kind"],
            "partial")
        self.assertEqual(
            restored.selection()[0]["newest4_opposed_count"], 1)

    def test_trigger_kind_never_widened_anywhere(self):
        row_sets = [
            MINORITY_RECOVERY_ROWS, MINORITY_BELOW_FRACTION_ROWS,
            MINORITY_BELOW_COUNT_ROWS, PRECEDENCE_ROWS,
            EXTENDED_RECOVERY_ROWS, ABSTAIN_ROWS, PARTIAL_ABSTAIN_ROWS,
            MINORITY_PARTIAL_ROWS, RETAINED_PARTIAL_ROWS,
            PARTIAL_PURITY_BLOCKED_ROWS, WIDENED_SILENT_ROWS,
            WIDENED_SPLIT_ROWS, WIDENED_BELOW_THRESHOLD_ROWS,
            WIDENED_NEWEST4_TOO_HIGH_ROWS, WIDENED_PURITY_BLOCKED_ROWS,
            GATE_ARMED_ABSTAIN_ROWS, SINGLE_SUPPORT_ABSTAIN_ROWS,
            DISCRIMINATING_INVERTED_ROWS,
        ]
        for rows in row_sets:
            decision, _ = fed(rows).selection()
            self.assertIn(decision["abstention_trigger_kind"],
                          ("full", "partial", "none"))
            self.assertNotEqual(decision["abstention_trigger_kind"],
                                "widened")

    def test_branch_identical_to_inverted_on_no_widened_armed_rows(self):
        row_sets = [
            MINORITY_RECOVERY_ROWS, MINORITY_BELOW_FRACTION_ROWS,
            MINORITY_BELOW_COUNT_ROWS, PRECEDENCE_ROWS,
            EXTENDED_RECOVERY_ROWS, ABSTAIN_ROWS, PARTIAL_ABSTAIN_ROWS,
            MINORITY_PARTIAL_ROWS, RETAINED_PARTIAL_ROWS,
            WIDENED_BELOW_THRESHOLD_ROWS, DISCRIMINATING_INVERTED_ROWS,
        ]
        for rows in row_sets:
            candidate = fed(rows)
            graded = GradedInvertedMemory()
            for r in rows:
                graded.observe(r)
            cand_decision, _ = candidate.selection()
            graded_decision, _ = graded.selection()
            self.assertFalse(cand_decision["widened_armed"])
            self.assertFalse(
                cand_decision["recovery_disarmed_by_staleness"])
            self.assertFalse(
                cand_decision["minority_disarmed_by_staleness"])
            stripped = {k: v for k, v in cand_decision.items()
                        if k not in STALE_KEYS
                        and k not in COMPANION_KEYS}
            self.assertEqual(stripped, graded_decision)

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
        # so the corroboration condition (leg R OR leg C) holds
        # and the block is leg P's alone: by_purity true,
        # by_preceding_pair and by_companion both false (the
        # companion is concordant here, but leg C's failure does
        # not block a state leg R already corroborates).
        decision, _ = fed(PARTIAL_PURITY_ONLY_BLOCKED_ROWS).selection()
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["abstention_trigger_kind"], "partial")
        self.assertTrue(decision["abstention_would_fire"])
        self.assertAlmostEqual(decision["reference_purity"], 0.62)
        self.assertFalse(decision["purity_armed"])
        self.assertEqual(decision["preceding_pair_opposed_count"], 1)
        self.assertTrue(decision["preceding_pair_armed"])
        self.assertTrue(decision["companion_matched"])
        self.assertTrue(decision["companion_concordant"])
        self.assertFalse(decision["companion_armed"])
        self.assertTrue(decision["abstention_armed"])
        self.assertFalse(decision["abstention_gate_armed"])
        self.assertTrue(decision["abstention_disarmed_by_purity"])
        self.assertFalse(
            decision["abstention_disarmed_by_preceding_pair"])
        self.assertFalse(decision["abstention_disarmed_by_companion"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")

    def test_partial_abstention_blocked_by_both_legs(self):
        # The unmodified multi-span construction: purity 0.64
        # (leg P disarmed) AND a fully concordant preceding pair
        # (leg R disarmed) AND a concordant companion (leg C
        # disarmed) - a partial blocked by leg P and by the
        # corroboration condition is recorded under the purity
        # flag AND both corroboration flags.
        decision, _ = fed(PARTIAL_PURITY_BLOCKED_ROWS).selection()
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["abstention_trigger_kind"], "partial")
        self.assertTrue(decision["abstention_would_fire"])
        self.assertAlmostEqual(decision["reference_purity"], 0.64)
        self.assertFalse(decision["purity_armed"])
        self.assertEqual(decision["preceding_pair_opposed_count"], 0)
        self.assertFalse(decision["preceding_pair_armed"])
        self.assertTrue(decision["companion_matched"])
        self.assertTrue(decision["companion_concordant"])
        self.assertFalse(decision["companion_armed"])
        self.assertFalse(decision["abstention_gate_armed"])
        self.assertTrue(decision["abstention_disarmed_by_purity"])
        self.assertTrue(
            decision["abstention_disarmed_by_preceding_pair"])
        self.assertTrue(decision["abstention_disarmed_by_companion"])
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
        restored = CompanionConcordancePartialRecoveryMemory.restore(
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
        restored = CompanionConcordancePartialRecoveryMemory.restore(
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
        self.assertEqual(len(decision["stale_joint_events"]),
                         STALE_WINDOW)
        for rec in decision["stale_joint_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class", "reference_count",
                              "reference_majority", "matched", "opposed",
                              "archive_count", "archive_majority",
                              "archive_matched", "archive_concordant",
                              "joint"})
        self.assertEqual(len(decision["stale_minority_joint_events"]),
                         STALE_WINDOW)
        for rec in decision["stale_minority_joint_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class", "reference_count",
                              "reference_majority", "matched", "opposed",
                              "minority_count", "minority_majority",
                              "minority_matched", "minority_concordant",
                              "minority_joint", "joint"})
        self.assertEqual(decision["staleness_pair_threshold"], 2)

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
        restored = CompanionConcordancePartialRecoveryMemory.restore(
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
        restored = CompanionConcordancePartialRecoveryMemory.restore(
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
        restored = CompanionConcordancePartialRecoveryMemory.restore(
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
        restored = CompanionConcordancePartialRecoveryMemory.restore(
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
        restored = CompanionConcordancePartialRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "abstained")
        self.assertTrue(restored.selection()[0]["abstention_gate_armed"])
        self.assertEqual(
            restored.selection()[0]["supporting_opposed_count"], 0)

    def test_replay_reproduces_gate_armed_abstention(self):
        m = fed(GATE_ARMED_ABSTAIN_ROWS)
        saved = m.record()
        restored = CompanionConcordancePartialRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "abstained")
        self.assertTrue(restored.selection()[0]["abstention_gate_armed"])
        self.assertEqual(
            restored.selection()[0]["supporting_opposed_count"], 2)

    def test_replay_reproduces_single_support_abstention(self):
        m = fed(SINGLE_SUPPORT_ABSTAIN_ROWS)
        saved = m.record()
        restored = CompanionConcordancePartialRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "abstained")
        self.assertTrue(restored.selection()[0]["abstention_gate_armed"])
        self.assertEqual(
            restored.selection()[0]["acting_opposed_count"], 3)

    def test_reject_invalid_events_without_partial_write(self):
        m = CompanionConcordancePartialRecoveryMemory()
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
            CompanionConcordancePartialRecoveryMemory.restore(bad)
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            CompanionConcordancePartialRecoveryMemory.restore(bad)
        bad2 = copy.deepcopy(saved)
        bad2["state"]["schema"] = "developmental-ai.other/v1"
        bad2["sha256"] = digest(bad2["state"])
        with self.assertRaises(ValueError):
            CompanionConcordancePartialRecoveryMemory.restore(bad2)

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


# DISCRIMINATING rows for the single changed element: the archive
# carries two extra spans whose minority-set and inverted models
# rank oppositely. Span 3: 51 damage + 49 progress (minority =
# 49 progress, a large minority fraction); span 8: 99 damage +
# 1 progress (minority = 1 progress, a tiny fraction). The
# minority-set model scores span 3 by its pure 49-progress bucket
# (high) and span 8 by its single progress event (moderate),
# while the inverted model scores span 3 by the swapped archive
# fraction 51 progress / 49 damage (negative under the harm
# weighting) and span 8 by 99 progress / 1 damage (high). The
# newest pair is the classic span-5 minority trigger, so the
# minority branch fires and the two models CHOOSE DIFFERENTLY
# on the inspected 212003 test frame (its actions include span-3
# and span-8 actions and no span-7 action).
DISCRIMINATING_INVERTED_ROWS = (
    [row("damage", span=3) for _ in range(51)]
    + [row("progress", span=3) for _ in range(49)]
    + [row("damage", span=8) for _ in range(99)]
    + [row("progress", span=8) for _ in range(1)]
    + [row("damage", span=5) for _ in range(30)]
    + [row("progress", span=5) for _ in range(60)]
    + [row("progress", span=5) for _ in range(24)]
    + [row("damage", span=5), row("damage", span=5)])


class CompanionConcordanceMinorityModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = STOCHASTIC_DEV[0]

    def test_discriminating_inverted_choice_differs(self):
        m = fed(DISCRIMINATING_INVERTED_ROWS)
        decision, model = m.selection()
        self.assertEqual(decision["branch"], "minority_archive")
        self.assertTrue(decision["minority_fired"])
        self.assertEqual(decision["minority_discordant_count"], 80)
        self.assertAlmostEqual(decision["minority_fraction"], 80 / 290)
        self.assertTrue(decision["minority_armed"])
        self.assertEqual(decision["minority_model_archive_count"], 290)
        self.assertEqual(decision["minority_model_archive_count"],
                         decision["archive_events_count"])
        self.assertTrue(decision["minority_model_inverted"])
        archive = DISCRIMINATING_INVERTED_ROWS[:290]
        self.assertEqual(model.events, [swapped(r) for r in archive])
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        candidate_choice = m.choose(frame)
        inverted_choice = inverted_model(archive).choose(frame)
        # Minority set, in chronological order: span-3 progress
        # events, the span-8 progress event, span-5 damage events.
        minority_set = (DISCRIMINATING_INVERTED_ROWS[51:100]
                        + DISCRIMINATING_INVERTED_ROWS[199:200]
                        + DISCRIMINATING_INVERTED_ROWS[200:230])
        minority_choice = plain_model(minority_set).choose(frame)
        self.assertEqual(candidate_choice, inverted_choice)
        self.assertNotEqual(candidate_choice, minority_choice)
        widened = GradedWidenedMemory()
        for r in DISCRIMINATING_INVERTED_ROWS:
            widened.observe(r)
        self.assertEqual(widened.selection()[0]["branch"],
                         "minority_archive")
        self.assertEqual(widened.choose(frame), minority_choice)
        self.assertNotEqual(candidate_choice, widened.choose(frame))

    def test_branch_selection_identical_to_widened_candidate(self):
        # On row sets with no widened-armed state, branch selection
        # is identical to the graded widened candidate after
        # stripping this candidate's two minority-model fields;
        # the widened-armed sets are excluded here because the
        # widened candidate abstains there through its widened
        # class while this candidate's removal changes the branch
        # (covered by the discriminating widened tests above).
        row_sets = [
            MINORITY_RECOVERY_ROWS, MINORITY_BELOW_FRACTION_ROWS,
            MINORITY_BELOW_COUNT_ROWS, PRECEDENCE_ROWS,
            EXTENDED_RECOVERY_ROWS, ABSTAIN_ROWS, PARTIAL_ABSTAIN_ROWS,
            MINORITY_PARTIAL_ROWS, RETAINED_PARTIAL_ROWS,
            WIDENED_BELOW_THRESHOLD_ROWS, DISCRIMINATING_INVERTED_ROWS,
        ]
        for rows in row_sets:
            candidate = fed(rows)
            widened = GradedWidenedMemory()
            for r in rows:
                widened.observe(r)
            cand_decision, _ = candidate.selection()
            wide_decision, _ = widened.selection()
            self.assertFalse(cand_decision["widened_armed"])
            self.assertEqual(cand_decision["branch"],
                             wide_decision["branch"])
            stripped = {k: v for k, v in cand_decision.items()
                        if k not in ("minority_model_archive_count",
                                     "minority_model_inverted")
                        and k not in STALE_KEYS
                        and k not in COMPANION_KEYS}
            self.assertEqual(stripped, wide_decision)
            self.assertEqual(
                cand_decision["minority_model_archive_count"],
                cand_decision["archive_events_count"])
            self.assertTrue(cand_decision["minority_model_inverted"])

    def test_replay_reproduces_inverted_minority_state(self):
        m = fed(DISCRIMINATING_INVERTED_ROWS)
        saved = m.record()
        self.assertEqual(saved["state"]["schema"], SCHEMA)
        restored = CompanionConcordancePartialRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(
            restored.selection()[0]["minority_model_archive_count"], 290)
        self.assertTrue(
            restored.selection()[0]["minority_model_inverted"])
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(restored.choose(frame), m.choose(frame))

    def test_neutral_events_unchanged_by_swap(self):
        rows = ([row("damage") for _ in range(30)]
                + [row("progress") for _ in range(60)]
                + [{"features": {"inlet": 0, "outlet": 5},
                    "progress": False, "damage": False}
                   for _ in range(10)]
                + [row("progress") for _ in range(14)]
                + [row("damage"), row("damage")])
        # Archive is the first 90 rows (30 damage + 60 progress);
        # the neutral events sit outside it here, so this checks
        # the swap helper directly as well as the branch records.
        self.assertEqual(swapped(rows[-1]),
                         {"features": {"inlet": 0, "outlet": 5},
                          "progress": True, "damage": False})
        neutral = {"features": {"inlet": 0, "outlet": 5},
                   "progress": False, "damage": False}
        self.assertEqual(swapped(neutral), neutral)
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["branch"], "minority_archive")
        self.assertEqual(decision["minority_model_archive_count"], 90)


class CompanionConcordanceLegTTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = STOCHASTIC_DEV[0]

    def fed_base(self, rows):
        m = GradedRemovalMemory()
        for r in rows:
            m.observe(r)
        return m

    def test_regular_recovery_disarmed_by_staleness(self):
        # DISCRIMINATING: the decisive baseline fires
        # retained_archive on these rows; leg T stands the
        # regular branch down (stale count 2) and the candidate
        # falls through to recent8.
        m = fed(REGULAR_STALE_DISARMED_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["joint_count"], 2)
        self.assertTrue(decision["recovery_would_fire"])
        self.assertTrue(decision["recovery_armed"])
        self.assertAlmostEqual(decision["reference_purity"], 0.92)
        self.assertTrue(decision["purity_armed"])
        self.assertFalse(decision["recovery_disarmed_by_purity"])
        self.assertEqual(decision["stale_joint_pair_count"], 2)
        self.assertEqual(decision["stale_minority_joint_pair_count"], 0)
        self.assertEqual(decision["staleness_pair_threshold"], 2)
        self.assertTrue(decision["recovery_disarmed_by_staleness"])
        self.assertFalse(decision["minority_disarmed_by_staleness"])
        self.assertFalse(decision["recovery_fired"])
        self.assertFalse(decision["minority_fired"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["branch"], "recent8")
        self.assertEqual(decision["reason"],
                         "recovery_disarmed_by_staleness")
        self.assertEqual(len(decision["stale_joint_events"]), 18)
        self.assertEqual(
            [r["joint"] for r in decision["stale_joint_events"][:4]],
            [True, True, True, True])
        base_decision, _ = self.fed_base(
            REGULAR_STALE_DISARMED_ROWS).selection()
        self.assertTrue(base_decision["recovery_fired"])
        self.assertEqual(base_decision["branch"], "retained_archive")

    def test_regular_recovery_fires_with_one_stale_pair(self):
        # Below the threshold (stale count 1) both candidates
        # fire identically: full decision record equal after
        # stripping this candidate's stale fields.
        m = fed(REGULAR_STALE_ONE_PAIR_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["stale_joint_pair_count"], 1)
        self.assertFalse(decision["recovery_disarmed_by_staleness"])
        self.assertTrue(decision["recovery_fired"])
        self.assertEqual(decision["branch"], "retained_archive")
        base = self.fed_base(REGULAR_STALE_ONE_PAIR_ROWS)
        base_decision, _ = base.selection()
        self.assertEqual(stripped_stale(decision), base_decision)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(m.choose(frame), base.choose(frame))

    def test_minority_recovery_disarmed_by_staleness(self):
        # DISCRIMINATING: the decisive baseline fires
        # minority_archive on these rows; leg T stands the
        # minority branch down (stale minority count 2, regular
        # stale count 0) and the decision falls through to the
        # full abstention trigger, taken behind leg P.
        m = fed(MINORITY_STALE_DISARMED_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["joint_count"], 0)
        self.assertEqual(decision["minority_joint_count"], 2)
        self.assertTrue(decision["minority_would_fire"])
        self.assertTrue(decision["minority_armed"])
        self.assertAlmostEqual(decision["reference_purity"], 0.92)
        self.assertTrue(decision["purity_armed"])
        self.assertFalse(decision["minority_disarmed_by_purity"])
        self.assertEqual(decision["stale_joint_pair_count"], 0)
        self.assertEqual(decision["stale_minority_joint_pair_count"], 2)
        self.assertTrue(decision["minority_disarmed_by_staleness"])
        self.assertFalse(decision["recovery_disarmed_by_staleness"])
        self.assertFalse(decision["minority_fired"])
        self.assertTrue(decision["abstained"])
        self.assertEqual(decision["branch"], "abstained")
        self.assertEqual(
            [r["joint"] for r in decision["stale_minority_joint_events"][:4]],
            [True, True, True, True])
        self.assertEqual(
            [r["joint"] for r in decision["stale_joint_events"][:4]],
            [False, False, False, False])
        base_decision, _ = self.fed_base(
            MINORITY_STALE_DISARMED_ROWS).selection()
        self.assertTrue(base_decision["minority_fired"])
        self.assertEqual(base_decision["branch"], "minority_archive")

    def test_minority_recovery_fires_with_one_stale_pair(self):
        m = fed(MINORITY_STALE_ONE_PAIR_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["stale_minority_joint_pair_count"], 1)
        self.assertFalse(decision["minority_disarmed_by_staleness"])
        self.assertTrue(decision["minority_fired"])
        self.assertEqual(decision["branch"], "minority_archive")
        base = self.fed_base(MINORITY_STALE_ONE_PAIR_ROWS)
        base_decision, _ = base.selection()
        self.assertEqual(stripped_stale(decision), base_decision)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(m.choose(frame), base.choose(frame))

    def test_stale_pair_counts_recomputable_from_records(self):
        row_sets = [
            MINORITY_RECOVERY_ROWS, MINORITY_BELOW_FRACTION_ROWS,
            MINORITY_BELOW_COUNT_ROWS, PRECEDENCE_ROWS,
            EXTENDED_RECOVERY_ROWS, ABSTAIN_ROWS, PARTIAL_ABSTAIN_ROWS,
            MINORITY_PARTIAL_ROWS, RETAINED_PARTIAL_ROWS,
            PARTIAL_PURITY_BLOCKED_ROWS, WIDENED_SILENT_ROWS,
            WIDENED_SPLIT_ROWS, WIDENED_BELOW_THRESHOLD_ROWS,
            WIDENED_NEWEST4_TOO_HIGH_ROWS, WIDENED_PURITY_BLOCKED_ROWS,
            GATE_ARMED_ABSTAIN_ROWS, SINGLE_SUPPORT_ABSTAIN_ROWS,
            DISCRIMINATING_INVERTED_ROWS, REGULAR_STALE_DISARMED_ROWS,
            REGULAR_STALE_ONE_PAIR_ROWS, MINORITY_STALE_DISARMED_ROWS,
            MINORITY_STALE_ONE_PAIR_ROWS,
        ]
        for rows in row_sets:
            decision, _ = fed(rows).selection()
            for events_key, count_key in (
                    ("stale_joint_events", "stale_joint_pair_count"),
                    ("stale_minority_joint_events",
                     "stale_minority_joint_pair_count")):
                records = decision[events_key]
                self.assertEqual(len(records), STALE_WINDOW)
                recomputed = sum(
                    int(records[i]["joint"] and records[i + 1]["joint"])
                    for i in range(0, len(records) - 1, 2))
                self.assertEqual(decision[count_key], recomputed)
            self.assertEqual(decision["staleness_pair_threshold"],
                             STALENESS_PAIR_THRESHOLD)

    def test_identical_to_decisive_baseline_without_staleness(self):
        # On every row set where leg T disarms nothing, the full
        # decision record is the decisive baseline's after
        # stripping the stale fields - branch and record alike.
        # (The purity-disarmed sets carry stale counts of 6 and 9:
        # leg T's flag requires leg P to pass, so a branch blocked
        # by purity is NOT recorded as disarmed by staleness.)
        row_sets = [
            MINORITY_RECOVERY_ROWS, MINORITY_BELOW_FRACTION_ROWS,
            MINORITY_BELOW_COUNT_ROWS, PRECEDENCE_ROWS,
            EXTENDED_RECOVERY_ROWS, ABSTAIN_ROWS, PARTIAL_ABSTAIN_ROWS,
            MINORITY_PARTIAL_ROWS, RETAINED_PARTIAL_ROWS,
            PARTIAL_PURITY_BLOCKED_ROWS, PARTIAL_PURITY_ONLY_BLOCKED_ROWS,
            REGULAR_PURITY_DISARMED_ROWS, MINORITY_PURITY_DISARMED_ROWS,
            ABSTENTION_UNGATED_ROWS, PURITY_ALONE_BLOCKED_ROWS,
            PURITY_ARMED_RECOVERY_ROWS, PURITY_BOUNDARY_ROWS,
            GATE_ARMED_ABSTAIN_ROWS, SINGLE_SUPPORT_ABSTAIN_ROWS,
            AUTHORITY_DISARMED_ABSTAIN_ROWS, DISARMED_RECOVERY_ROWS,
            WIDENED_SILENT_ROWS, WIDENED_SPLIT_ROWS,
            WIDENED_BELOW_THRESHOLD_ROWS, WIDENED_NEWEST4_TOO_HIGH_ROWS,
            WIDENED_PURITY_BLOCKED_ROWS, DISCRIMINATING_INVERTED_ROWS,
            REGULAR_STALE_ONE_PAIR_ROWS, MINORITY_STALE_ONE_PAIR_ROWS,
        ]
        for rows in row_sets:
            candidate = fed(rows)
            cand_decision, _ = candidate.selection()
            self.assertFalse(
                cand_decision["recovery_disarmed_by_staleness"])
            self.assertFalse(
                cand_decision["minority_disarmed_by_staleness"])
            base_decision, _ = self.fed_base(rows).selection()
            self.assertEqual(stripped_stale(cand_decision),
                             base_decision)

    def test_replay_reproduces_stale_disarmed_state(self):
        m = fed(REGULAR_STALE_DISARMED_ROWS)
        saved = m.record()
        restored = CompanionConcordancePartialRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "recent8")
        self.assertTrue(
            restored.selection()[0]["recovery_disarmed_by_staleness"])
        self.assertEqual(
            restored.selection()[0]["stale_joint_pair_count"], 2)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(restored.choose(frame), m.choose(frame))

    def test_replay_reproduces_minority_stale_disarmed_state(self):
        m = fed(MINORITY_STALE_DISARMED_ROWS)
        saved = m.record()
        restored = CompanionConcordancePartialRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "abstained")
        self.assertTrue(
            restored.selection()[0]["minority_disarmed_by_staleness"])
        self.assertEqual(
            restored.selection()[0]["stale_minority_joint_pair_count"], 2)


# DISCRIMINATING rows for this experiment's single changed
# element, leg C. The newest pair carries exactly one opposed
# event (damage vs the pure progress reference, purity 1.0); the
# preceding pair is fully concordant, so leg R fails. In
# COMPANION_UNMATCHED_ROWS the companion is a NEUTRAL event
# (unmatched: no matched support for the reference rule), and in
# COMPANION_UNMATCHED_SPAN_ROWS it is a progress event on a span
# with NO reference majority (also unmatched). In both, leg C is
# armed and the candidate takes the retained-partial abstention
# where the decisive baseline (graded pre-acting candidate) is
# disarmed by leg R and acts on recent8.
COMPANION_UNMATCHED_ROWS = ([row("progress") for _ in range(10)]
                            + [row("progress") for _ in range(50)]
                            + [row("damage"), row("neutral")])

COMPANION_UNMATCHED_SPAN_ROWS = ([row("progress") for _ in range(10)]
                                 + [row("progress") for _ in range(50)]
                                 + [row("damage"),
                                    row("progress", span=9)])

# Both corroboration legs armed: the preceding pair carries one
# opposed event (leg R armed) AND the companion is neutral
# (leg C armed). Both candidates take the abstention, with the
# full decision record equal after stripping the companion
# fields.
COMPANION_BOTH_ARMED_ROWS = ([row("progress") for _ in range(58)]
                             + [row("damage"), row("progress")]
                             + [row("damage"), row("neutral")])


class CompanionConcordanceLegCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = STOCHASTIC_DEV[0]

    def fed_base(self, rows):
        m = GradedPreActingMemory()
        for r in rows:
            m.observe(r)
        return m

    def test_partial_taken_through_leg_c_neutral_companion(self):
        # DISCRIMINATING: leg R fails (preceding pair concordant),
        # the companion is neutral hence unmatched, leg C arms,
        # and the candidate abstains as kind partial; the
        # decisive baseline acts on recent8 on the same rows.
        m = fed(COMPANION_UNMATCHED_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["abstention_trigger_kind"], "partial")
        self.assertTrue(decision["abstention_would_fire"])
        self.assertEqual(decision["joint_count"], 0)
        self.assertEqual(decision["minority_joint_count"], 0)
        self.assertEqual(decision["reference_purity"], 1.0)
        self.assertTrue(decision["purity_armed"])
        self.assertEqual(decision["preceding_pair_opposed_count"], 0)
        self.assertFalse(decision["preceding_pair_armed"])
        self.assertFalse(decision["companion_matched"])
        self.assertFalse(decision["companion_concordant"])
        self.assertTrue(decision["companion_armed"])
        self.assertIsNone(decision["companion_threshold"])
        self.assertTrue(decision["abstention_gate_armed"])
        self.assertFalse(decision["abstention_disarmed_by_purity"])
        self.assertFalse(
            decision["abstention_disarmed_by_preceding_pair"])
        self.assertFalse(decision["abstention_disarmed_by_companion"])
        self.assertFalse(decision["abstention_disarmed_by_support"])
        self.assertTrue(decision["abstained"])
        self.assertEqual(decision["branch"], "abstained")
        self.assertEqual(decision["reason"],
                         "evidence_opposition_gate_abstain_armed")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(m.choose(frame))
        base = self.fed_base(COMPANION_UNMATCHED_ROWS)
        base_decision, _ = base.selection()
        self.assertEqual(base_decision["branch"], "recent8")
        self.assertFalse(base_decision["abstention_gate_armed"])
        self.assertTrue(
            base_decision["abstention_disarmed_by_preceding_pair"])
        self.assertIsNotNone(base.choose(frame))

    def test_partial_taken_through_leg_c_majority_less_companion(self):
        # DISCRIMINATING, second unmatched form: the companion's
        # span has no reference majority at all (reference_count
        # 0), so it is unmatched and leg C arms identically.
        m = fed(COMPANION_UNMATCHED_SPAN_ROWS)
        decision, _ = m.selection()
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["abstention_trigger_kind"], "partial")
        self.assertEqual(decision["signal_events"][1]["span"], 9)
        self.assertEqual(decision["signal_events"][1]["reference_count"], 0)
        self.assertIsNone(decision["signal_events"][1]["reference_majority"])
        self.assertFalse(decision["signal_events"][1]["matched"])
        self.assertFalse(decision["signal_events"][1]["opposed"])
        self.assertFalse(decision["companion_matched"])
        self.assertFalse(decision["companion_concordant"])
        self.assertTrue(decision["companion_armed"])
        self.assertEqual(decision["preceding_pair_opposed_count"], 0)
        self.assertFalse(decision["preceding_pair_armed"])
        self.assertTrue(decision["abstention_gate_armed"])
        self.assertTrue(decision["abstained"])
        self.assertEqual(decision["branch"], "abstained")
        base_decision, _ = self.fed_base(
            COMPANION_UNMATCHED_SPAN_ROWS).selection()
        self.assertEqual(base_decision["branch"], "recent8")

    def test_concordant_companion_both_act_on_recent8(self):
        # The campaign's second discriminating state: the SAME
        # leg-R-disarmed partial shape with a CONCORDANT companion
        # (PARTIAL_ABSTAIN_ROWS) -- leg C fails too, both the
        # candidate and the decisive baseline act on recent8, and
        # the full decision record is the baseline's after
        # stripping the companion fields.
        candidate = fed(PARTIAL_ABSTAIN_ROWS)
        cand_decision, _ = candidate.selection()
        self.assertTrue(cand_decision["companion_matched"])
        self.assertTrue(cand_decision["companion_concordant"])
        self.assertFalse(cand_decision["companion_armed"])
        self.assertEqual(cand_decision["branch"], "recent8")
        base = self.fed_base(PARTIAL_ABSTAIN_ROWS)
        base_decision, _ = base.selection()
        self.assertEqual(base_decision["branch"], "recent8")
        self.assertEqual(stripped_companion(cand_decision),
                         base_decision)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(candidate.choose(frame), base.choose(frame))

    def test_leg_r_armed_partial_fires_identically(self):
        # One-pair leg-R-armed variant: RETAINED_PARTIAL_ROWS
        # fires through leg R in both candidates (the companion
        # is concordant, leg C disarmed); full record equal
        # after stripping the companion fields.
        candidate = fed(RETAINED_PARTIAL_ROWS)
        cand_decision, _ = candidate.selection()
        self.assertTrue(cand_decision["preceding_pair_armed"])
        self.assertFalse(cand_decision["companion_armed"])
        self.assertTrue(cand_decision["abstained"])
        self.assertEqual(cand_decision["branch"], "abstained")
        base = self.fed_base(RETAINED_PARTIAL_ROWS)
        base_decision, _ = base.selection()
        self.assertEqual(base_decision["branch"], "abstained")
        self.assertEqual(stripped_companion(cand_decision),
                         base_decision)

    def test_both_legs_armed_partial_fires_identically(self):
        # Leg R armed AND leg C armed at the same state: both
        # candidates take the abstention and the records agree
        # after stripping the companion fields.
        candidate = fed(COMPANION_BOTH_ARMED_ROWS)
        cand_decision, _ = candidate.selection()
        self.assertEqual(cand_decision["opposed_count"], 1)
        self.assertTrue(cand_decision["preceding_pair_armed"])
        self.assertTrue(cand_decision["companion_armed"])
        self.assertFalse(cand_decision["companion_matched"])
        self.assertAlmostEqual(cand_decision["reference_purity"], 0.98)
        self.assertTrue(cand_decision["abstention_gate_armed"])
        self.assertTrue(cand_decision["abstained"])
        self.assertEqual(cand_decision["branch"], "abstained")
        base = self.fed_base(COMPANION_BOTH_ARMED_ROWS)
        base_decision, _ = base.selection()
        self.assertEqual(base_decision["branch"], "abstained")
        self.assertEqual(stripped_companion(cand_decision),
                         base_decision)

    def test_companion_fields_fallback_outside_partial(self):
        # A full trigger has no companion event: the fields take
        # their fallback form and leg C cannot arm (the full
        # trigger fires behind leg P alone, as carried).
        decision, _ = fed(ABSTAIN_ROWS).selection()
        self.assertEqual(decision["abstention_trigger_kind"], "full")
        self.assertFalse(decision["companion_matched"])
        self.assertFalse(decision["companion_concordant"])
        self.assertFalse(decision["companion_armed"])
        self.assertIsNone(decision["companion_threshold"])
        self.assertFalse(decision["abstention_disarmed_by_companion"])
        self.assertTrue(decision["abstained"])
        # A no-trigger state records the same fallback form.
        rows = [row("progress") for _ in range(60)]
        none_decision, _ = fed(rows).selection()
        self.assertEqual(none_decision["abstention_trigger_kind"], "none")
        self.assertFalse(none_decision["companion_armed"])
        self.assertFalse(
            none_decision["abstention_disarmed_by_companion"])

    def test_companion_fields_recomputable_from_signal_records(self):
        row_sets = [
            MINORITY_RECOVERY_ROWS, ABSTAIN_ROWS, PARTIAL_ABSTAIN_ROWS,
            RETAINED_PARTIAL_ROWS, PARTIAL_PURITY_BLOCKED_ROWS,
            PARTIAL_PURITY_ONLY_BLOCKED_ROWS, WIDENED_SPLIT_ROWS,
            MINORITY_PARTIAL_ROWS, COMPANION_UNMATCHED_ROWS,
            COMPANION_UNMATCHED_SPAN_ROWS, COMPANION_BOTH_ARMED_ROWS,
            REGULAR_STALE_DISARMED_ROWS, MINORITY_STALE_DISARMED_ROWS,
        ]
        for rows in row_sets:
            decision, _ = fed(rows).selection()
            if decision["opposed_count"] == 1:
                companion = next(
                    r for r in decision["signal_events"]
                    if not r["opposed"])
                self.assertEqual(decision["companion_matched"],
                                 bool(companion["matched"]))
                self.assertEqual(
                    decision["companion_concordant"],
                    bool(companion["matched"]
                         and not companion["opposed"]))
                self.assertEqual(decision["companion_armed"],
                                 not decision["companion_concordant"])
            else:
                self.assertFalse(decision["companion_matched"])
                self.assertFalse(decision["companion_concordant"])
                self.assertFalse(decision["companion_armed"])
            self.assertIsNone(decision["companion_threshold"])
            # Gate recomputable from the recorded legs.
            if decision["abstention_trigger_kind"] == "partial":
                self.assertEqual(
                    decision["abstention_gate_armed"],
                    bool(decision["purity_armed"]
                         and (decision["preceding_pair_armed"]
                              or decision["companion_armed"])))
            else:
                self.assertEqual(decision["abstention_gate_armed"],
                                 decision["purity_armed"])

    def test_identical_to_decisive_baseline_without_leg_c(self):
        # On every row set where leg C arms at no partial state,
        # the full decision record is the decisive baseline's
        # after stripping the companion fields.
        row_sets = [
            MINORITY_RECOVERY_ROWS, MINORITY_BELOW_FRACTION_ROWS,
            MINORITY_BELOW_COUNT_ROWS, PRECEDENCE_ROWS,
            EXTENDED_RECOVERY_ROWS, ABSTAIN_ROWS, PARTIAL_ABSTAIN_ROWS,
            MINORITY_PARTIAL_ROWS, RETAINED_PARTIAL_ROWS,
            PARTIAL_PURITY_BLOCKED_ROWS, PARTIAL_PURITY_ONLY_BLOCKED_ROWS,
            REGULAR_PURITY_DISARMED_ROWS, MINORITY_PURITY_DISARMED_ROWS,
            ABSTENTION_UNGATED_ROWS, PURITY_ALONE_BLOCKED_ROWS,
            PURITY_ARMED_RECOVERY_ROWS, PURITY_BOUNDARY_ROWS,
            GATE_ARMED_ABSTAIN_ROWS, SINGLE_SUPPORT_ABSTAIN_ROWS,
            AUTHORITY_DISARMED_ABSTAIN_ROWS, DISARMED_RECOVERY_ROWS,
            WIDENED_SILENT_ROWS, WIDENED_SPLIT_ROWS,
            WIDENED_BELOW_THRESHOLD_ROWS, WIDENED_NEWEST4_TOO_HIGH_ROWS,
            WIDENED_PURITY_BLOCKED_ROWS, DISCRIMINATING_INVERTED_ROWS,
            REGULAR_STALE_DISARMED_ROWS, REGULAR_STALE_ONE_PAIR_ROWS,
            MINORITY_STALE_DISARMED_ROWS, MINORITY_STALE_ONE_PAIR_ROWS,
        ]
        for rows in row_sets:
            candidate = fed(rows)
            cand_decision, _ = candidate.selection()
            self.assertFalse(cand_decision["companion_armed"])
            base_decision, _ = self.fed_base(rows).selection()
            self.assertEqual(cand_decision["branch"],
                             base_decision["branch"])
            self.assertEqual(stripped_companion(cand_decision),
                             base_decision)

    def test_replay_reproduces_leg_c_firing(self):
        # Replay reproducing a leg-C firing identically: the
        # restored checkpoint's full decision record (including
        # the companion fields) and its abstention agree.
        m = fed(COMPANION_UNMATCHED_ROWS)
        saved = m.record()
        restored = CompanionConcordancePartialRecoveryMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertEqual(restored.selection()[0]["branch"], "abstained")
        self.assertEqual(
            restored.selection()[0]["abstention_trigger_kind"], "partial")
        self.assertTrue(restored.selection()[0]["companion_armed"])
        self.assertFalse(restored.selection()[0]["companion_matched"])
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(restored.choose(frame))
        self.assertEqual(restored.choose(frame), m.choose(frame))

    def test_smoke_on_inspected_212003_matches_baseline(self):
        # Smoke on already-inspected 212003 (source/frame shape
        # only): companion fields recomputable, threshold null,
        # and the candidate's branch is the decisive baseline's
        # unless leg C is armed at a partial state.
        source, _cost = public_train(self.seed, "original", 1000, 240)
        candidate = fed(source)
        cand_decision, _ = candidate.selection()
        base_decision, _ = self.fed_base(source).selection()
        self.assertIsNone(cand_decision["companion_threshold"])
        self.assertIsNone(cand_decision["support_threshold"])
        self.assertEqual(cand_decision["minority_model_archive_count"],
                         cand_decision["archive_events_count"])
        self.assertTrue(cand_decision["minority_model_inverted"])
        self.assertNotEqual(cand_decision["abstention_trigger_kind"],
                            "widened")
        if cand_decision["opposed_count"] == 1:
            companion = next(
                r for r in cand_decision["signal_events"]
                if not r["opposed"])
            self.assertEqual(cand_decision["companion_matched"],
                             bool(companion["matched"]))
            self.assertEqual(cand_decision["companion_armed"],
                             not cand_decision["companion_concordant"])
        if not cand_decision["companion_armed"]:
            self.assertEqual(stripped_companion(cand_decision),
                             base_decision)
        replayed = CompanionConcordancePartialRecoveryMemory.restore(
            copy.deepcopy(candidate.record()))
        self.assertEqual(replayed.selection()[0], cand_decision)
