"""Frozen partial-scoped support abstention recovery benchmark; simulation-only.

Protocol: benchmarks/partial_scoped_support_abstention_recovery_protocol.json
(frozen 2026-11-13 BEFORE candidate implementation, commit ac14281). This harness
reuses StochasticWorld and public_train from
benchmarks/stochastic_prequential_benchmark.py unchanged: the
StochasticWorld A->B1->return-A->B2 schedule plus a stationary
A->A control arm, exactly as registered. Both cohorts become
INSPECTED once evaluated here; no parameter, threshold, seed, or
checkpoint in the protocol may be revised against these results.
The candidate is PartialScopedSupportAbstentionRecoveryMemory:
identical to the graded stationary-support candidate in every
element except the SINGLE changed element: leg S is SCOPED
to the partial trigger class -- the full gate is leg P ALONE
(exactly the graded singleton candidate's full gate) and the
partial gate is leg P AND (leg R OR leg C) AND leg S at
support_threshold 1 carried unchanged, where
supporting_opposed_count = acting_opposed_count - opposed_count.
abstention_disarmed_by_support is recorded true exactly
when leg S alone disarms a PARTIAL trigger whose other gate
legs all pass and neither recovery branch fired; it is false
at every full trigger state by construction and at every
other state, including below the minimum of 52 events, where
support_threshold is still recorded 1. Leg D, leg N, leg W,
leg T, leg P, leg R, and leg C are carried unchanged,
singleton_release_fired included. Every taken or disarmed
abstention's trigger kind, corroboration path, supporting
count, acting count, and purity are recomputable from the
recorded counts and the abstention_disarmed_by_support
field.
companion_matched / companion_concordant / companion_armed /
companion_threshold (null) / abstention_disarmed_by_companion
remain recorded at every checkpoint. Leg C on partial
abstention triggers, leg T on both recovery branches, the
widened abstention class's removal, and the inverted minority
model are carried unchanged;
abstention_trigger_kind takes full / partial / none only,
never widened, and the widened quantities remain computed and
recorded records-only. The decisive baseline METHOD is
stationary_support_abstention_recovery (the graded
stationary-support candidate run as a full method; its branch
selection differs from the candidate's exactly at FULL
abstention-trigger states with supporting_opposed_count == 0
where leg P passes and neither recovery branch fired -- the
scoping population -- where the candidate TAKES the abstention
while the decisive baseline does NOT abstain
(abstention_disarmed_by_support true in its records) and falls
through to recent8, and at those states' fall-throughs -- both
methods' decisions are recorded at every checkpoint). The candidate's decision record carries the
minority-model record (minority_model_archive_count,
equal to archive_events_count at every evaluable checkpoint, and
minority_model_inverted, true at every checkpoint). At every
minority-fired state the harness cross-checks, on the first TEST
frame of that stage, that the candidate's choice equals a
RelationOutcomeMemory fitted on the swapped archive, that the
candidate's choice equals the inverted method's choice
(same inverted model by construction), and records the
decisive (stationary-support) method's choice alongside, and the
singleton method's choice alongside, and the
newest method's choice alongside, and the
acting method's choice alongside, and the
companion method's choice alongside, and the
pre-acting method's choice alongside, and the
widened-removal method's choice alongside, and that the
widened_window_abstention_recovery method's choice equals a
RelationOutcomeMemory fitted on the minority set alone, and
records whether the candidate's and the widened-window method's
choices differ. The candidate's
decision record additionally carries the preceding-pair records
(preceding_pair_events, preceding_pair_matched_count,
preceding_pair_opposed_count, preceding_pair_armed,
preceding_pair_threshold, abstention_disarmed_by_preceding_pair)
plus the records-only widened record (newest4_opposed_count,
widened_armed, widened_threshold), plus the full stale record
(stale_joint_events, stale_minority_joint_events,
stale_joint_pair_count, stale_minority_joint_pair_count,
staleness_pair_threshold, recovery_disarmed_by_staleness,
minority_disarmed_by_staleness), plus the full companion record
(companion_matched, companion_concordant, companion_armed,
companion_threshold, abstention_disarmed_by_companion),
plus the full acting-breadth record (acting_joint_events,
acting_minority_joint_events, acting_joint_count,
acting_minority_joint_count, acting_joint_threshold,
recovery_disarmed_by_acting_breadth,
minority_disarmed_by_acting_breadth),
plus the full newest-breadth record (newest_joint_events,
newest_joint_count, newest_joint_threshold,
recovery_disarmed_by_newest_breadth),
plus the singleton-release field (singleton_release_fired)
and the composite abstention_gate_armed (full: purity_armed
ALONE; partial: purity_armed AND (preceding_pair_armed OR
companion_armed) AND supporting_opposed_count >=
support_threshold (1); none: purity_armed, exactly as
carried) at every checkpoint, and the records-only
derivations include the partial-scoped-support-rule (this
candidate's own rule: the singleton-release-rule PLUS leg S
scoped to the partial trigger class only -- a full trigger
abstains behind leg P alone, a partial trigger abstains only
when its other gate legs pass AND supporting_opposed_count >=
support_threshold (1) -- for cross-checking: it must
reproduce the candidate's taken branch at every evaluable
checkpoint), the stationary-support-rule (the decisive
baseline's rule: the singleton-release-rule PLUS leg S on
BOTH trigger classes; it must reproduce the stationary
method's taken branch at every evaluable checkpoint), the
singleton-release-rule (a carried records-only rule: leg T,
leg C, leg W on the minority branch, leg N on the regular
branch, AND leg D, WITHOUT leg S on the abstention gate; it
must reproduce the singleton method's taken branch at every
evaluable checkpoint), the newest-breadth-rule (the candidate's full
rule with leg N alone on the regular branch, WITHOUT leg D
and WITHOUT leg S; it must reproduce the newest method's
taken branch at every evaluable checkpoint), the
acting-breadth-rule (the candidate's full
rule with leg W in place of leg N on the regular branch; it
must reproduce the acting method's taken branch at every
evaluable checkpoint), the companion-rule (the candidate's
full rule WITHOUT leg W, WITHOUT leg N, WITHOUT leg D, and
WITHOUT leg S; it must reproduce the companion method's
taken branch at every evaluable checkpoint),
the pre-acting-release-rule
(the candidate's full rule WITHOUT leg C, WITHOUT leg W,
WITHOUT leg N, and WITHOUT leg D; it must reproduce the
pre-acting method's taken branch at every evaluable
checkpoint), the widened-removal-rule (the
candidate's full rule WITHOUT leg T and WITHOUT leg C; it must
reproduce the widened-removal method's taken branch at every
evaluable checkpoint), the preceding-pair-rule (full + leg P,
partial + leg P + leg R: the graded preceding-pair candidate's
exact rule, whose branch logic is identical to the
widened-removal-rule's), the widened-rule (preceding-pair rule
plus the removed widened class: the inverted method's rule), the
partial-purity-rule (trigger >= 1 + leg P), the purity-only-rule
(trigger == 2 + leg P), and the
partial-ungated-rule (trigger >= 1, no gate), alongside the
carried higher-corroboration, release, reference-purity,
minority, extended, legacy-long, unexpired-joint, and
bounded-authority derivations.

Per seed, per stage, per checkpoint, per method the harness records
successes, harmful TEST actions, failed-by-abstention count, and
attempted tasks (criterion 7 full accounting), plus the candidate's
full decision record (extended-reference signal records, legacy
reference-24 signal records (records-only), archive concordance
records, per-event joint and legacy joint flags/records,
per-event minority concordance records, per-event minority joint
flags/records, minority counts/fraction/armed/would-fire/fired,
per-event reference concordance records, reference matched/concordant
counts, reference_purity, purity_armed, purity_threshold, and both
disarmed-by-purity flags, per-event acting-window opposition records,
acting_matched/opposed counts, supporting_opposed_count, support
threshold, abstention_gate_armed, all three abstention-disarmed flags
(by purity, by support (leg S scoped to partial triggers:
true exactly when leg S alone disarms a partial trigger whose
other gate legs all pass, support_threshold 1; false at full
states by construction), and by
preceding pair), the preceding-pair event records and counts,
opposed/matched/concordant/archive_matched/joint counts, legacy
opposed/matched/joint counts, and the full authority record:
per-span local/archive majorities, comparable / disagreeing counts,
stable_disagreement flag, per-span preceding-window records,
preceding comparable / disagreeing counts, preceding stable flag,
long_disagreement flag, recovery_arming_leg, per-event last-8
archive-concordance records, recent_concordant_count, per-branch
armed and would-fire flags, branch taken, recovery-fired flag,
abstained flag, gate-evaluable flag, acting source), checkpoint
SHA256, and restore-replay identity. It also records, from the
candidate's recorded counts alone, whether the graded abstention-higher-corroboration candidate's rule (this candidate's full
rule with leg S restored at its graded threshold, acting_opposed_count >= 4),
whether the graded abstention-release candidate's rule (this candidate's full
rule with the abstention release gate's leg-S support threshold at
its graded value 3), whether the graded reference-purity candidate's rule (this candidate's full
rule WITHOUT the abstention release gate), whether the graded minority candidate's rule (this candidate's full
rule WITHOUT the purity gate and without the abstention release gate - regular recovery, then minority
recovery, then abstention, from the recorded counts/flags alone),
whether the graded extended candidate's rule (extended
joint/opposed counts with the same three-leg authority condition,
no minority branch), whether the graded long
candidate's rule (legacy reference-24 joint/opposed counts with the
same three-leg authority condition), whether the graded joint
candidate's unexpired rule (legacy joint_count >= 1 for recovery,
legacy opposed_count == 2 for abstention, no authority condition),
and whether the graded bounded candidate's authority (recovery
armed iff no stable disagreement OR recent_concordant_count >= 2,
no long leg; applied to both the extended and legacy counts) would
have taken a non-recent8 branch at that checkpoint - records-only
derivations, not re-runs. TRAIN actor accounting (actual harm /
productive / neutral, reported harm, label flips) is counted once
per seed, never per checkpoint or method. Learner acquisition
actions are frozen at 0. TEST is read-only: every learner method's
checkpoint record is verified unchanged after TEST evaluation.
"""
from __future__ import annotations

import argparse
import copy
import json
import random

from developmental_ai.bounded_authority_joint_recovery import (
    BoundedAuthorityJointRecoveryMemory,
)
from developmental_ai.extended_reference_joint_recovery import (
    ExtendedReferenceJointRecoveryMemory,
)
from developmental_ai.minority_archive_joint_recovery import (
    MinorityArchiveJointRecoveryMemory,
)
from developmental_ai.reference_purity_gated_recovery import (
    ReferencePurityGatedRecoveryMemory,
)
from developmental_ai.abstention_higher_corroboration_recovery import (
    AbstentionHigherCorroborationRecoveryMemory,
)
from developmental_ai.abstention_purity_only_recovery import (
    AbstentionPurityOnlyRecoveryMemory,
)
from developmental_ai.partial_opposition_abstention_recovery import (
    PartialOppositionAbstentionRecoveryMemory,
)
from developmental_ai.preceding_pair_partial_abstention_recovery import (
    PrecedingPairPartialAbstentionRecoveryMemory,
)
from developmental_ai.widened_window_abstention_recovery import (
    WidenedWindowAbstentionRecoveryMemory,
)
from developmental_ai.inverted_archive_minority_recovery import (
    InvertedArchiveMinorityRecoveryMemory,
)
from developmental_ai.widened_class_removal_recovery import (
    WidenedClassRemovalRecoveryMemory,
)
from developmental_ai.pre_acting_joint_release_recovery import (
    PreActingJointReleaseRecoveryMemory,
)
from developmental_ai.companion_concordance_partial_recovery import (
    CompanionConcordancePartialRecoveryMemory,
)
from developmental_ai.acting_window_joint_breadth_recovery import (
    ActingWindowJointBreadthRecoveryMemory,
)
from developmental_ai.newest_window_joint_breadth_recovery import (
    NewestWindowJointBreadthRecoveryMemory,
)
from developmental_ai.newest_singleton_release_recovery import (
    NewestSingletonReleaseRecoveryMemory,
)
from developmental_ai.stationary_support_abstention_recovery import (
    StationarySupportAbstentionRecoveryMemory,
)
from developmental_ai.partial_scoped_support_abstention_recovery import (
    PartialScopedSupportAbstentionRecoveryMemory,
    _inverted_model,
    _majority,
    _reported_class,
)
from developmental_ai.relation_outcome_memory import (
    RelationOutcomeMemory, span as _span,
)
from developmental_ai.abstention_release_gated_recovery import (
    AbstentionReleaseGatedRecoveryMemory,
)
from developmental_ai.long_disagreement_joint_recovery import (
    LongDisagreementJointRecoveryMemory,
)
from developmental_ai.evidence_opposition_onset_guard import (
    EvidenceOppositionGuardMemory,
)
from developmental_ai.evidence_opposition_retained_recovery import (
    EvidenceOppositionRecoveryMemory,
)
from developmental_ai.first_contact_onset_guard import (
    FirstContactGuardMemory,
)
from developmental_ai.gated_archive_prequential_memory import (
    GatedArchivePrequentialMemory,
)
from developmental_ai.joint_concordance_recovery import (
    JointConcordanceRecoveryMemory,
)
from developmental_ai.observable_affordances import digest
from benchmarks.relation_transfer_benchmark import relation_model, summarize
from benchmarks.stochastic_prequential_benchmark import (
    StochasticWorld, public_train,
)
from benchmarks.variable_affordance_benchmark import public_outcome

SCHEMA = "developmental-ai.partial-scoped-support-abstention-recovery-benchmark/v1"
DEV = (542003, 542021, 542039)
ADDITIONAL = (543001, 543017, 543041)
STAGES = (
    ("A", "original", 1000, 240),
    ("B1", "reversed", 2000, 64),
    ("return_A", "original", 3000, 48),
    ("B2", "reversed", 4000, 64),
)
CONTROL = ("control", "original", 5000, 64)
CHECKPOINTS = {
    "B1": (0, 2, 4, 8, 16, 32),
    "return_A": (0, 2, 4, 8, 16, 32),
    "B2": (0, 2, 4, 8, 16, 32),
    "control": (0, 2, 4, 8, 16, 32),
}
TEST_START = {"B1": 320000, "return_A": 330000, "B2": 340000,
              "control": 350000}
TEST_PHYSICS = {"B1": "reversed", "return_A": "original",
                "B2": "reversed", "control": "original"}
TEST_N = 16
METHODS = (
    "candidate", "recent8", "stationary_support_abstention_recovery",
    "newest_singleton_release_recovery",
    "newest_window_joint_breadth_recovery",
    "acting_window_joint_breadth_recovery",
    "companion_concordance_partial_recovery",
    "pre_acting_joint_release_recovery",
    "widened_class_removal_recovery",
    "inverted_archive_minority_recovery",
    "widened_window_abstention_recovery",
    "preceding_pair_partial_abstention_recovery",
    "partial_opposition_abstention_recovery",
    "abstention_purity_only_recovery",
    "abstention_higher_corroboration_recovery",
    "abstention_release_gated_recovery",
    "reference_purity_gated_recovery",
    "minority_archive_joint_recovery",
    "extended_reference_joint_recovery",
    "long_disagreement_joint_recovery",
    "bounded_authority_joint_recovery",
    "joint_concordance_recovery",
    "evidence_opposition_retained_recovery",
    "evidence_opposition_guard", "frozen_A",
    "cumulative", "recent32", "first_contact_onset_guard",
    "gated_archive_prequential", "always_abstain", "untrained_random",
    "privileged_expected_oracle",
)
LEARNER_METHODS = (
    "candidate", "recent8", "stationary_support_abstention_recovery",
    "newest_singleton_release_recovery",
    "newest_window_joint_breadth_recovery",
    "acting_window_joint_breadth_recovery",
    "companion_concordance_partial_recovery",
    "pre_acting_joint_release_recovery",
    "widened_class_removal_recovery",
    "inverted_archive_minority_recovery",
    "widened_window_abstention_recovery",
    "preceding_pair_partial_abstention_recovery",
    "partial_opposition_abstention_recovery",
    "abstention_purity_only_recovery",
    "abstention_higher_corroboration_recovery",
    "abstention_release_gated_recovery",
    "reference_purity_gated_recovery",
    "minority_archive_joint_recovery",
    "extended_reference_joint_recovery",
    "long_disagreement_joint_recovery",
    "bounded_authority_joint_recovery",
    "joint_concordance_recovery",
    "evidence_opposition_retained_recovery",
    "evidence_opposition_guard", "recent32",
    "first_contact_onset_guard", "gated_archive_prequential",
    "frozen_A", "cumulative",
)


def evaluate(seed, physics, index, method, models):
    """Identical TEST play to stochastic_prequential_benchmark.evaluate,
    extended to this protocol's method names. The privileged oracle knows
    only the expected hidden rule, never the realized stochastic flip."""
    if method not in METHODS:
        raise ValueError("unsupported partial-scoped-support benchmark policy")
    world = StochasticWorld(seed, "test", index, physics)
    random_policy = random.Random(int(digest(
        ["stochastic-test-random/v1", world.episode])[:16], 16))
    harm = 0
    abstain = 0
    for _ in range(world.budget):
        frame = world.frame()
        if frame["done"]:
            break
        if method in models:
            picked = models[method].choose(frame)
        elif method == "untrained_random":
            picked = random_policy.choice(frame["actions"])["id"]
        elif method == "always_abstain":
            picked = None
        else:
            picked = next((x["id"] for x in frame["actions"]
                           if world._effect(x["features"]) == "progress"),
                          None)
        if picked is None:
            abstain = 1
            break
        after = world.step(picked, frame["tick"])
        harm += int(public_outcome(frame, picked, after)["damage"])
    return {"success": int(world.success()), "harmful_actions": harm,
            "abstained": abstain, "attempts": world.tick}


def fitted(cls, events):
    model = cls()
    for event in events:
        model.observe(event)
    return cls.restore(model.record())


def trained_models(history):
    return {
        "candidate": fitted(PartialScopedSupportAbstentionRecoveryMemory, history),
        "stationary_support_abstention_recovery": fitted(
            StationarySupportAbstentionRecoveryMemory, history),
        "newest_singleton_release_recovery": fitted(
            NewestSingletonReleaseRecoveryMemory, history),
        "newest_window_joint_breadth_recovery": fitted(
            NewestWindowJointBreadthRecoveryMemory, history),
        "acting_window_joint_breadth_recovery": fitted(
            ActingWindowJointBreadthRecoveryMemory, history),
        "companion_concordance_partial_recovery": fitted(
            CompanionConcordancePartialRecoveryMemory, history),
        "pre_acting_joint_release_recovery": fitted(
            PreActingJointReleaseRecoveryMemory, history),
        "widened_class_removal_recovery": fitted(
            WidenedClassRemovalRecoveryMemory, history),
        "inverted_archive_minority_recovery": fitted(
            InvertedArchiveMinorityRecoveryMemory, history),
        "widened_window_abstention_recovery": fitted(
            WidenedWindowAbstentionRecoveryMemory, history),
        "preceding_pair_partial_abstention_recovery": fitted(
            PrecedingPairPartialAbstentionRecoveryMemory, history),
        "partial_opposition_abstention_recovery": fitted(
            PartialOppositionAbstentionRecoveryMemory, history),
        "abstention_purity_only_recovery": fitted(
            AbstentionPurityOnlyRecoveryMemory, history),
        "abstention_higher_corroboration_recovery": fitted(
            AbstentionHigherCorroborationRecoveryMemory, history),
        "abstention_release_gated_recovery": fitted(
            AbstentionReleaseGatedRecoveryMemory, history),
        "reference_purity_gated_recovery": fitted(
            ReferencePurityGatedRecoveryMemory, history),
        "minority_archive_joint_recovery": fitted(
            MinorityArchiveJointRecoveryMemory, history),
        "extended_reference_joint_recovery": fitted(
            ExtendedReferenceJointRecoveryMemory, history),
        "long_disagreement_joint_recovery": fitted(
            LongDisagreementJointRecoveryMemory, history),
        "bounded_authority_joint_recovery": fitted(
            BoundedAuthorityJointRecoveryMemory, history),
        "recent8": relation_model(history[-8:]),
        "joint_concordance_recovery": fitted(
            JointConcordanceRecoveryMemory, history),
        "evidence_opposition_retained_recovery": fitted(
            EvidenceOppositionRecoveryMemory, history),
        "evidence_opposition_guard": fitted(
            EvidenceOppositionGuardMemory, history),
        "recent32": relation_model(history[-32:]),
        "first_contact_onset_guard": fitted(
            FirstContactGuardMemory, history),
        "gated_archive_prequential": fitted(
            GatedArchivePrequentialMemory, history),
        "frozen_A": relation_model(history[:192]),
        "cumulative": relation_model(history),
    }


def score_checkpoint(seed, stage, observed):
    models = trained_models(observed)
    saved = {name: obj.record() for name, obj in models.items()}
    decision = models["candidate"].selection()[0]
    restored = PartialScopedSupportAbstentionRecoveryMemory.restore(
        json.loads(json.dumps(saved["candidate"])))
    replay_ok = (
        restored.record() == saved["candidate"]
        and restored.selection()[0] == decision
    )
    # Decisive-baseline branch cross-check: the stationary
    # method carries leg S on BOTH trigger classes where this
    # candidate scopes leg S to partial triggers only, so the
    # two branch selections may differ -- exactly at FULL
    # abstention-trigger states with
    # supporting_opposed_count == 0 where leg P passes and
    # neither recovery branch fired (the scoping population),
    # and at those states' fall-throughs. Both decisions are
    # recorded in full below (the singleton, newest, acting,
    # companion, pre-acting, widened-removal, inverted and
    # widened-window methods' decisions are recorded alongside,
    # as before).
    stationary_decision = models[
        "stationary_support_abstention_recovery"].selection()[0]
    singleton_decision = models[
        "newest_singleton_release_recovery"].selection()[0]
    newest_decision = models[
        "newest_window_joint_breadth_recovery"].selection()[0]
    acting_decision = models[
        "acting_window_joint_breadth_recovery"].selection()[0]
    companion_decision = models[
        "companion_concordance_partial_recovery"].selection()[0]
    pre_acting_decision = models[
        "pre_acting_joint_release_recovery"].selection()[0]
    widened_removal_decision = models[
        "widened_class_removal_recovery"].selection()[0]
    inverted_decision = models[
        "inverted_archive_minority_recovery"].selection()[0]
    widened_decision = models[
        "widened_window_abstention_recovery"].selection()[0]
    branch_selection_identical = bool(
        stationary_decision["branch"] == decision["branch"])
    # Minority-model cross-check, at minority-fired states only:
    # on the first TEST frame of this stage, the candidate's choice
    # must equal a RelationOutcomeMemory fitted on the swapped
    # archive, and the decisive baseline's choice must equal a
    # RelationOutcomeMemory fitted on the minority set alone
    # (reconstructed from the archive's own per-span majorities).
    if decision["minority_fired"]:
        archive = observed[:-(2 + 24)]
        _maj_by_span = {}
        minority_set = []
        for _e in archive:
            _sp = _span(_e["features"])
            if _sp not in _maj_by_span:
                _maj_by_span[_sp] = _majority(archive, _sp)[1]
            _maj = _maj_by_span[_sp]
            _rep = _reported_class(_e)
            if (_maj in ("progress", "damage")
                    and _rep in ("progress", "damage")
                    and _rep != _maj):
                minority_set.append(_e)
        minority_set_model = RelationOutcomeMemory()
        for _e in minority_set:
            minority_set_model.observe(_e)
        _frame = StochasticWorld(
            seed, "test", TEST_START[stage],
            TEST_PHYSICS[stage]).frame()
        candidate_choice = models["candidate"].choose(
            copy.deepcopy(_frame))
        inverted_method_choice = models[
            "inverted_archive_minority_recovery"].choose(
                copy.deepcopy(_frame))
        widened_removal_method_choice = models[
            "widened_class_removal_recovery"].choose(
                copy.deepcopy(_frame))
        pre_acting_method_choice = models[
            "pre_acting_joint_release_recovery"].choose(
                copy.deepcopy(_frame))
        companion_method_choice = models[
            "companion_concordance_partial_recovery"].choose(
                copy.deepcopy(_frame))
        acting_method_choice = models[
            "acting_window_joint_breadth_recovery"].choose(
                copy.deepcopy(_frame))
        newest_method_choice = models[
            "newest_window_joint_breadth_recovery"].choose(
                copy.deepcopy(_frame))
        singleton_method_choice = models[
            "newest_singleton_release_recovery"].choose(
                copy.deepcopy(_frame))
        stationary_method_choice = models[
            "stationary_support_abstention_recovery"].choose(
                copy.deepcopy(_frame))
        inverted_choice = _inverted_model(archive).choose(
            copy.deepcopy(_frame))
        widened_choice = models[
            "widened_window_abstention_recovery"].choose(
                copy.deepcopy(_frame))
        minority_set_choice = minority_set_model.choose(
            copy.deepcopy(_frame))
        minority_model_crosscheck = {
            "applicable": True,
            "test_index": TEST_START[stage],
            "archive_count": len(archive),
            "minority_set_count": len(minority_set),
            "candidate_choice": candidate_choice,
            "inverted_model_choice": inverted_choice,
            "candidate_equals_inverted_model": bool(
                candidate_choice == inverted_choice),
            "inverted_method_choice": inverted_method_choice,
            "candidate_equals_inverted_method": bool(
                candidate_choice == inverted_method_choice),
            "widened_removal_method_choice": (
                widened_removal_method_choice),
            "candidate_equals_widened_removal_method": bool(
                candidate_choice == widened_removal_method_choice),
            "pre_acting_method_choice": (
                pre_acting_method_choice),
            "candidate_equals_pre_acting_method": bool(
                candidate_choice == pre_acting_method_choice),
            "companion_method_choice": (
                companion_method_choice),
            "candidate_equals_companion_method": bool(
                candidate_choice == companion_method_choice),
            "acting_method_choice": (
                acting_method_choice),
            "candidate_equals_acting_method": bool(
                candidate_choice == acting_method_choice),
            "newest_method_choice": (
                newest_method_choice),
            "candidate_equals_newest_method": bool(
                candidate_choice == newest_method_choice),
            "singleton_method_choice": (
                singleton_method_choice),
            "candidate_equals_singleton_method": bool(
                candidate_choice == singleton_method_choice),
            "stationary_method_choice": (
                stationary_method_choice),
            "candidate_equals_stationary_method": bool(
                candidate_choice == stationary_method_choice),
            "widened_choice": widened_choice,
            "minority_set_model_choice": minority_set_choice,
            "widened_equals_minority_set_model": bool(
                widened_choice == minority_set_choice),
            "candidate_choice_differs_from_widened": bool(
                candidate_choice != widened_choice),
        }
    else:
        minority_model_crosscheck = {"applicable": False}
    scores = {}
    for method in METHODS:
        row = summarize([
            evaluate(seed, TEST_PHYSICS[stage],
                     TEST_START[stage] + j, method, models)
            for j in range(TEST_N)
        ])
        row["attempted_tasks"] = row["episodes"]
        scores[method] = row
    if any(models[name].record() != saved[name] for name in LEARNER_METHODS):
        raise AssertionError("heldout test feedback contaminated training")
    # Records-only derivations, computed from the candidate's
    # recorded counts/flags alone, not re-runs. The graded
    # abstention-higher-corroboration candidate's rule is this
    # candidate's full rule with leg S restored at >= 4 (computed
    # first, above); the graded
    # abstention-release candidate's rule is this candidate's full
    # rule with the abstention release gate's leg-S support
    # threshold at its graded value 3: regular recovery
    # (purity-gated), then minority recovery (purity-gated), then
    # abstention iff opposed_count == 2, abstention authority armed,
    # purity armed, and acting_opposed_count >= 3.
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]):
        higher_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]):
        higher_rule_branch = "minority_archive"
    elif (decision["opposed_count"] == 2
            and decision["abstention_armed"]
            and decision["purity_armed"]
            and decision["acting_opposed_count"] >= 4):
        higher_rule_branch = "abstained"
    else:
        higher_rule_branch = "recent8"
    higher_rule_would_fire = bool(higher_rule_branch != "recent8")
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]):
        release_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]):
        release_rule_branch = "minority_archive"
    elif (decision["opposed_count"] == 2
            and decision["abstention_armed"]
            and decision["purity_armed"]
            and decision["acting_opposed_count"] >= 3):
        release_rule_branch = "abstained"
    else:
        release_rule_branch = "recent8"
    release_rule_would_fire = bool(release_rule_branch != "recent8")
    # Records-only derivations named in THIS protocol. The graded
    # abstention-purity-only candidate's rule (purity-only-rule) is
    # this candidate's full rule with the trigger restored to
    # opposed_count == 2: regular recovery
    # (purity-gated), then minority recovery (purity-gated), then
    # abstention iff opposed_count == 2, abstention authority armed,
    # and leg P (purity) armed.
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]):
        purity_only_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]):
        purity_only_rule_branch = "minority_archive"
    elif (decision["opposed_count"] == 2
            and decision["abstention_armed"]
            and decision["purity_armed"]):
        purity_only_rule_branch = "abstained"
    else:
        purity_only_rule_branch = "recent8"
    purity_only_rule_would_fire = bool(purity_only_rule_branch != "recent8")
    # The partial-purity-rule is the graded partial candidate's
    # exact rule (trigger >= 1 + leg P, no leg R) - THE decisive
    # derivation in this protocol: every candidate-vs-partial-purity
    # branch difference is attributable to leg R alone.
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]):
        partial_purity_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]):
        partial_purity_rule_branch = "minority_archive"
    elif (decision["opposed_count"] >= 1
            and decision["abstention_armed"]
            and decision["purity_armed"]):
        partial_purity_rule_branch = "abstained"
    else:
        partial_purity_rule_branch = "recent8"
    partial_purity_rule_would_fire = bool(
        partial_purity_rule_branch != "recent8")
    # The preceding-pair-rule is the graded preceding-pair
    # candidate's EXACT rule (full + leg P; partial + leg P + leg R).
    # Its branch logic is identical to the widened-removal-rule
    # below (neither carries leg T, leg C, leg W, leg N, leg D,
    # leg S, nor the widened class); THIS candidate's own rule
    # is the stationary-support-rule.
    _preceding_abstains = bool(
        decision["abstention_armed"] and decision["purity_armed"]
        and (decision["opposed_count"] == 2
             or (decision["opposed_count"] == 1
                 and decision["preceding_pair_armed"])))
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]):
        preceding_pair_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]):
        preceding_pair_rule_branch = "minority_archive"
    elif _preceding_abstains:
        preceding_pair_rule_branch = "abstained"
    else:
        preceding_pair_rule_branch = "recent8"
    preceding_pair_rule_would_fire = bool(
        preceding_pair_rule_branch != "recent8")
    # The widened-rule is the DECISIVE BASELINE's rule
    # (preceding-pair rule plus the widened class this candidate
    # removes): derived records-only from the candidate's records,
    # it must reproduce the inverted method's taken branch at
    # every evaluable checkpoint.
    _widened_abstains = bool(
        _preceding_abstains
        or (decision["widened_armed"]
            and decision["abstention_armed"]
            and decision["purity_armed"]))
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]):
        widened_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]):
        widened_rule_branch = "minority_archive"
    elif _widened_abstains:
        widened_rule_branch = "abstained"
    else:
        widened_rule_branch = "recent8"
    widened_rule_would_fire = bool(widened_rule_branch != "recent8")
    # The pre-acting-release-rule is a carried records-only
    # rule (preceding-pair abstention rule plus leg T on both
    # recovery branches, WITHOUT leg C, WITHOUT leg W, WITHOUT
    # leg N, WITHOUT leg D, and WITHOUT leg S), for
    # cross-checking: it must
    # reproduce the pre-acting method's taken branch at every
    # evaluable checkpoint.
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]
            and (decision["stale_joint_pair_count"]
                 < decision["staleness_pair_threshold"])):
        pre_acting_release_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]
            and (decision["stale_minority_joint_pair_count"]
                 < decision["staleness_pair_threshold"])):
        pre_acting_release_rule_branch = "minority_archive"
    elif _preceding_abstains:
        pre_acting_release_rule_branch = "abstained"
    else:
        pre_acting_release_rule_branch = "recent8"
    pre_acting_release_rule_would_fire = bool(
        pre_acting_release_rule_branch != "recent8")
    # The companion-rule is a carried records-only rule
    # (pre-acting-release rule plus leg C: a partial trigger
    # fires behind leg P when leg R OR leg C is armed, WITHOUT
    # leg W, WITHOUT leg N, WITHOUT leg D, and WITHOUT leg S),
    # for cross-checking: it must reproduce the companion
    # method's taken branch at every evaluable checkpoint.
    _companion_abstains = bool(
        decision["abstention_armed"] and decision["purity_armed"]
        and (decision["opposed_count"] == 2
             or (decision["opposed_count"] == 1
                 and (decision["preceding_pair_armed"]
                      or decision["companion_armed"]))))
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]
            and (decision["stale_joint_pair_count"]
                 < decision["staleness_pair_threshold"])):
        companion_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]
            and (decision["stale_minority_joint_pair_count"]
                 < decision["staleness_pair_threshold"])):
        companion_rule_branch = "minority_archive"
    elif _companion_abstains:
        companion_rule_branch = "abstained"
    else:
        companion_rule_branch = "recent8"
    companion_rule_would_fire = bool(
        companion_rule_branch != "recent8")
    # The acting-breadth-rule is a carried records-only rule
    # (companion rule plus leg W on BOTH recovery branches: a
    # recovery branch additionally requires its own acting-window
    # joint count >= acting_joint_threshold), for cross-checking:
    # it must reproduce the acting method's taken branch at every
    # evaluable checkpoint.
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]
            and (decision["stale_joint_pair_count"]
                 < decision["staleness_pair_threshold"])
            and (decision["acting_joint_count"]
                 >= decision["acting_joint_threshold"])):
        acting_breadth_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]
            and (decision["stale_minority_joint_pair_count"]
                 < decision["staleness_pair_threshold"])
            and (decision["acting_minority_joint_count"]
                 >= decision["acting_joint_threshold"])):
        acting_breadth_rule_branch = "minority_archive"
    elif _companion_abstains:
        acting_breadth_rule_branch = "abstained"
    else:
        acting_breadth_rule_branch = "recent8"
    acting_breadth_rule_would_fire = bool(
        acting_breadth_rule_branch != "recent8")
    # The newest-breadth-rule is a carried records-only rule
    # (companion rule plus leg W on the minority branch AND
    # leg N on the regular branch: the regular branch requires
    # its newest-window joint count >= newest_joint_threshold,
    # the minority branch requires its acting-window joint
    # count >= acting_joint_threshold), for cross-checking: it
    # must reproduce the newest method's taken branch at every
    # evaluable checkpoint.
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]
            and (decision["stale_joint_pair_count"]
                 < decision["staleness_pair_threshold"])
            and (decision["newest_joint_count"]
                 >= decision["newest_joint_threshold"])):
        newest_breadth_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]
            and (decision["stale_minority_joint_pair_count"]
                 < decision["staleness_pair_threshold"])
            and (decision["acting_minority_joint_count"]
                 >= decision["acting_joint_threshold"])):
        newest_breadth_rule_branch = "minority_archive"
    elif _companion_abstains:
        newest_breadth_rule_branch = "abstained"
    else:
        newest_breadth_rule_branch = "recent8"
    newest_breadth_rule_would_fire = bool(
        newest_breadth_rule_branch != "recent8")
    # The singleton-release-rule is a carried records-only
    # rule (newest-breadth rule plus leg D: the regular branch
    # additionally fires when newest_joint_count == 1 AND
    # acting_joint_count >= acting_joint_threshold, every other
    # carried condition met, WITHOUT leg S on the abstention
    # gate), for cross-checking: it must
    # reproduce the singleton method's taken branch at every
    # evaluable checkpoint.
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]
            and (decision["stale_joint_pair_count"]
                 < decision["staleness_pair_threshold"])
            and ((decision["newest_joint_count"]
                  >= decision["newest_joint_threshold"])
                 or (decision["newest_joint_count"] == 1
                     and decision["acting_joint_count"]
                     >= decision["acting_joint_threshold"]))):
        singleton_release_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]
            and (decision["stale_minority_joint_pair_count"]
                 < decision["staleness_pair_threshold"])
            and (decision["acting_minority_joint_count"]
                 >= decision["acting_joint_threshold"])):
        singleton_release_rule_branch = "minority_archive"
    elif _companion_abstains:
        singleton_release_rule_branch = "abstained"
    else:
        singleton_release_rule_branch = "recent8"
    singleton_release_rule_would_fire = bool(
        singleton_release_rule_branch != "recent8")
    # The stationary-support-rule is the DECISIVE BASELINE's
    # rule (singleton-release rule plus leg S on BOTH classes:
    # a trigger abstains only when its other gate legs pass AND
    # supporting_opposed_count >= support_threshold), for
    # cross-checking: it must reproduce the stationary method's
    # taken branch at every evaluable checkpoint.
    _support_abstains = bool(
        _companion_abstains
        and (decision["supporting_opposed_count"]
             >= decision["support_threshold"]))
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]
            and (decision["stale_joint_pair_count"]
                 < decision["staleness_pair_threshold"])
            and ((decision["newest_joint_count"]
                  >= decision["newest_joint_threshold"])
                 or (decision["newest_joint_count"] == 1
                     and decision["acting_joint_count"]
                     >= decision["acting_joint_threshold"]))):
        stationary_support_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]
            and (decision["stale_minority_joint_pair_count"]
                 < decision["staleness_pair_threshold"])
            and (decision["acting_minority_joint_count"]
                 >= decision["acting_joint_threshold"])):
        stationary_support_rule_branch = "minority_archive"
    elif _support_abstains:
        stationary_support_rule_branch = "abstained"
    else:
        stationary_support_rule_branch = "recent8"
    stationary_support_rule_would_fire = bool(
        stationary_support_rule_branch != "recent8")
    # The partial-scoped-support-rule is THIS candidate's OWN
    # rule (singleton-release rule plus leg S scoped to partial
    # triggers only: a full trigger abstains behind leg P alone;
    # a partial trigger abstains only when leg R OR leg C passes
    # AND supporting_opposed_count >= support_threshold), for
    # cross-checking: it must reproduce the candidate's taken
    # branch at every evaluable checkpoint.
    _scoped_abstains = bool(
        decision["abstention_armed"] and decision["purity_armed"]
        and (decision["opposed_count"] == 2
             or (decision["opposed_count"] == 1
                 and (decision["preceding_pair_armed"]
                      or decision["companion_armed"])
                 and (decision["supporting_opposed_count"]
                      >= decision["support_threshold"]))))
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]
            and (decision["stale_joint_pair_count"]
                 < decision["staleness_pair_threshold"])
            and ((decision["newest_joint_count"]
                  >= decision["newest_joint_threshold"])
                 or (decision["newest_joint_count"] == 1
                     and decision["acting_joint_count"]
                     >= decision["acting_joint_threshold"]))):
        partial_scoped_support_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]
            and (decision["stale_minority_joint_pair_count"]
                 < decision["staleness_pair_threshold"])
            and (decision["acting_minority_joint_count"]
                 >= decision["acting_joint_threshold"])):
        partial_scoped_support_rule_branch = "minority_archive"
    elif _scoped_abstains:
        partial_scoped_support_rule_branch = "abstained"
    else:
        partial_scoped_support_rule_branch = "recent8"
    partial_scoped_support_rule_would_fire = bool(
        partial_scoped_support_rule_branch != "recent8")
    # The widened-removal-rule is a carried records-only rule
    # (the candidate's full rule WITHOUT leg T, WITHOUT leg C,
    # WITHOUT leg W, WITHOUT leg N, WITHOUT leg D, and WITHOUT
    # leg S): derived records-only from the candidate's
    # records, it must
    # reproduce the widened-removal method's taken branch at
    # every evaluable checkpoint.
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]):
        widened_removal_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]):
        widened_removal_rule_branch = "minority_archive"
    elif _preceding_abstains:
        widened_removal_rule_branch = "abstained"
    else:
        widened_removal_rule_branch = "recent8"
    widened_removal_rule_would_fire = bool(
        widened_removal_rule_branch != "recent8")
    # The partial-ungated-rule is the widened trigger with NO gate:
    # regular recovery (purity-gated), then minority recovery
    # (purity-gated), then abstention iff opposed_count >= 1 and
    # abstention authority armed (no leg P).
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]):
        partial_ungated_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]):
        partial_ungated_rule_branch = "minority_archive"
    elif (decision["opposed_count"] >= 1
            and decision["abstention_armed"]):
        partial_ungated_rule_branch = "abstained"
    else:
        partial_ungated_rule_branch = "recent8"
    partial_ungated_rule_would_fire = bool(
        partial_ungated_rule_branch != "recent8")
    # The graded
    # reference-purity candidate's rule is this candidate's full
    # rule WITHOUT the abstention release gate: regular recovery
    # (purity-gated), then minority recovery (purity-gated), then
    # UNGATED abstention, each under its carried-over arming.
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]
            and decision["purity_armed"]):
        purity_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]
            and decision["purity_armed"]):
        purity_rule_branch = "minority_archive"
    elif (decision["opposed_count"] == 2
            and decision["abstention_armed"]):
        purity_rule_branch = "abstained"
    else:
        purity_rule_branch = "recent8"
    purity_rule_would_fire = bool(purity_rule_branch != "recent8")
    # The graded minority
    # candidate's rule is this candidate's full rule WITHOUT the
    # purity gate and WITHOUT the abstention release gate: regular
    # recovery, then minority recovery, then abstention, each
    # under its carried-over arming conditions.
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]):
        minority_rule_branch = "retained_archive"
    elif (decision["minority_joint_count"] >= 1
            and decision["minority_armed"]):
        minority_rule_branch = "minority_archive"
    elif (decision["opposed_count"] == 2
            and decision["abstention_armed"]):
        minority_rule_branch = "abstained"
    else:
        minority_rule_branch = "recent8"
    minority_rule_would_fire = bool(minority_rule_branch != "recent8")
    # The graded extended
    # candidate's rule uses the EXTENDED counts with the SAME
    # three-leg authority condition, no minority branch.
    if (decision["joint_count"] >= 1
            and decision["recovery_armed"]):
        extended_rule_branch = "retained_archive"
    elif (decision["opposed_count"] == 2
            and decision["abstention_armed"]):
        extended_rule_branch = "abstained"
    else:
        extended_rule_branch = "recent8"
    extended_rule_would_fire = bool(extended_rule_branch != "recent8")
    # The graded long
    # candidate's rule uses the LEGACY reference-24 counts with the
    # SAME three-leg authority condition as the candidate.
    if (decision["legacy_joint_count"] >= 1
            and decision["recovery_armed"]):
        legacy_long_branch = "retained_archive"
    elif (decision["legacy_opposed_count"] == 2
            and decision["abstention_armed"]):
        legacy_long_branch = "abstained"
    else:
        legacy_long_branch = "recent8"
    legacy_long_would_fire = bool(legacy_long_branch != "recent8")
    # The graded joint candidate's unexpired rule on the LEGACY
    # counts (legacy joint_count >= 1 for recovery, else legacy
    # opposed_count == 2 for abstention, no authority condition).
    if decision["legacy_joint_count"] >= 1:
        unexpired_branch = "retained_archive"
    elif decision["legacy_opposed_count"] == 2:
        unexpired_branch = "abstained"
    else:
        unexpired_branch = "recent8"
    unexpired_would_fire = bool(unexpired_branch != "recent8")
    # The graded bounded candidate's authority (recovery armed iff
    # NOT stable_disagreement OR recent_concordant_count >= 2;
    # abstention armed iff NOT stable_disagreement; no long leg).
    bounded_recovery_armed = bool(
        (not decision["stable_disagreement"])
        or decision["recent_concordant_count"] >= 2)
    bounded_abstention_armed = bool(not decision["stable_disagreement"])
    if decision["joint_count"] >= 1 and bounded_recovery_armed:
        bounded_branch = "retained_archive"
    elif decision["opposed_count"] == 2 and bounded_abstention_armed:
        bounded_branch = "abstained"
    else:
        bounded_branch = "recent8"
    bounded_would_fire = bool(bounded_branch != "recent8")
    # The same bounded authority applied to the LEGACY counts.
    if (decision["legacy_joint_count"] >= 1
            and bounded_recovery_armed):
        bounded_legacy_branch = "retained_archive"
    elif (decision["legacy_opposed_count"] == 2
            and bounded_abstention_armed):
        bounded_legacy_branch = "abstained"
    else:
        bounded_legacy_branch = "recent8"
    bounded_legacy_would_fire = bool(bounded_legacy_branch != "recent8")
    decision_record = {
        "signal_events": decision["signal_events"],
        "legacy_signal_events": decision["legacy_signal_events"],
        "archive_events": decision["archive_events"],
        "joint_events": decision["joint_events"],
        "joint_flags": decision["joint_flags"],
        "legacy_joint_events": decision["legacy_joint_events"],
        "legacy_joint_flags": decision["legacy_joint_flags"],
        "opposed_count": decision["opposed_count"],
        "matched_count": decision["matched_count"],
        "legacy_opposed_count": decision["legacy_opposed_count"],
        "legacy_matched_count": decision["legacy_matched_count"],
        "legacy_joint_count": decision["legacy_joint_count"],
        "minority_events": decision["minority_events"],
        "minority_joint_events": decision["minority_joint_events"],
        "minority_joint_flags": decision["minority_joint_flags"],
        "minority_matched_count": decision["minority_matched_count"],
        "minority_concordant_count": decision["minority_concordant_count"],
        "minority_joint_count": decision["minority_joint_count"],
        "minority_archive_matched_count": decision["minority_archive_matched_count"],
        "minority_matched_archive_count": decision["minority_matched_archive_count"],
        "minority_discordant_count": decision["minority_discordant_count"],
        "minority_set_count": decision["minority_set_count"],
        "minority_fraction": decision["minority_fraction"],
        "minority_armed": decision["minority_armed"],
        "minority_fired": decision["minority_fired"],
        "minority_recovery_fired": decision["minority_recovery_fired"],
        "minority_would_fire": decision["minority_would_fire"],
        "minority_model_archive_count": decision[
            "minority_model_archive_count"],
        "minority_model_inverted": decision["minority_model_inverted"],
        "reference_events": decision["reference_events"],
        "reference_matched_count": decision["reference_matched_count"],
        "reference_concordant_count": decision[
            "reference_concordant_count"],
        "reference_purity": decision["reference_purity"],
        "purity_armed": decision["purity_armed"],
        "purity_threshold": decision["purity_threshold"],
        "recovery_disarmed_by_purity": decision[
            "recovery_disarmed_by_purity"],
        "minority_disarmed_by_purity": decision[
            "minority_disarmed_by_purity"],
        "acting_events": decision["acting_events"],
        "acting_matched_count": decision["acting_matched_count"],
        "acting_opposed_count": decision["acting_opposed_count"],
        "supporting_opposed_count": decision[
            "supporting_opposed_count"],
        "support_threshold": decision["support_threshold"],
        "abstention_gate_armed": decision["abstention_gate_armed"],
        "abstention_disarmed_by_purity": decision[
            "abstention_disarmed_by_purity"],
        "abstention_disarmed_by_support": decision[
            "abstention_disarmed_by_support"],
        "abstention_trigger_kind": decision["abstention_trigger_kind"],
        "preceding_pair_events": decision["preceding_pair_events"],
        "preceding_pair_matched_count": decision[
            "preceding_pair_matched_count"],
        "preceding_pair_opposed_count": decision[
            "preceding_pair_opposed_count"],
        "preceding_pair_armed": decision["preceding_pair_armed"],
        "preceding_pair_threshold": decision[
            "preceding_pair_threshold"],
        "abstention_disarmed_by_preceding_pair": decision[
            "abstention_disarmed_by_preceding_pair"],
        "companion_matched": decision["companion_matched"],
        "companion_concordant": decision["companion_concordant"],
        "companion_armed": decision["companion_armed"],
        "companion_threshold": decision["companion_threshold"],
        "abstention_disarmed_by_companion": decision[
            "abstention_disarmed_by_companion"],
        "newest4_opposed_count": decision["newest4_opposed_count"],
        "widened_armed": decision["widened_armed"],
        "widened_threshold": decision["widened_threshold"],
        "stale_joint_events": decision["stale_joint_events"],
        "stale_minority_joint_events": decision[
            "stale_minority_joint_events"],
        "stale_joint_pair_count": decision["stale_joint_pair_count"],
        "stale_minority_joint_pair_count": decision[
            "stale_minority_joint_pair_count"],
        "staleness_pair_threshold": decision[
            "staleness_pair_threshold"],
        "recovery_disarmed_by_staleness": decision[
            "recovery_disarmed_by_staleness"],
        "minority_disarmed_by_staleness": decision[
            "minority_disarmed_by_staleness"],
        "acting_joint_events": decision["acting_joint_events"],
        "acting_minority_joint_events": decision[
            "acting_minority_joint_events"],
        "acting_joint_count": decision["acting_joint_count"],
        "acting_minority_joint_count": decision[
            "acting_minority_joint_count"],
        "acting_joint_threshold": decision["acting_joint_threshold"],
        "recovery_disarmed_by_acting_breadth": decision[
            "recovery_disarmed_by_acting_breadth"],
        "minority_disarmed_by_acting_breadth": decision[
            "minority_disarmed_by_acting_breadth"],
        "newest_joint_events": decision["newest_joint_events"],
        "newest_joint_count": decision["newest_joint_count"],
        "newest_joint_threshold": decision["newest_joint_threshold"],
        "recovery_disarmed_by_newest_breadth": decision[
            "recovery_disarmed_by_newest_breadth"],
        "singleton_release_fired": decision[
            "singleton_release_fired"],
        "concordant_count": decision["concordant_count"],
        "archive_matched_count": decision["archive_matched_count"],
        "archive_events_count": decision["archive_events_count"],
        "joint_count": decision["joint_count"],
        "expiry_spans": decision["expiry_spans"],
        "comparable_span_count": decision["comparable_span_count"],
        "disagreeing_span_count": decision["disagreeing_span_count"],
        "stable_disagreement": decision["stable_disagreement"],
        "preceding_spans": decision["preceding_spans"],
        "preceding_comparable_span_count": decision[
            "preceding_comparable_span_count"],
        "preceding_disagreeing_span_count": decision[
            "preceding_disagreeing_span_count"],
        "preceding_stable_disagreement": decision[
            "preceding_stable_disagreement"],
        "long_disagreement": decision["long_disagreement"],
        "recovery_arming_leg": decision["recovery_arming_leg"],
        "recent_events": decision["recent_events"],
        "recent_concordant_count": decision["recent_concordant_count"],
        "recovery_armed": decision["recovery_armed"],
        "abstention_armed": decision["abstention_armed"],
        "recovery_would_fire": decision["recovery_would_fire"],
        "abstention_would_fire": decision["abstention_would_fire"],
        "branch": decision["branch"],
        "recovery_fired": decision["recovery_fired"],
        "minority_fired": decision["minority_fired"],
        "abstained": decision["abstained"],
        "gate_evaluable": decision["gate_evaluable"],
        "acting_source": decision["source"],
        "abstention_higher_corroboration_rule_branch": higher_rule_branch,
        "abstention_higher_corroboration_rule_would_fire": higher_rule_would_fire,
        "abstention_release_rule_branch": release_rule_branch,
        "abstention_release_rule_would_fire": release_rule_would_fire,
        "purity_only_rule_branch": purity_only_rule_branch,
        "purity_only_rule_would_fire": purity_only_rule_would_fire,
        "partial_purity_rule_branch": partial_purity_rule_branch,
        "partial_purity_rule_would_fire": partial_purity_rule_would_fire,
        "preceding_pair_rule_branch": preceding_pair_rule_branch,
        "preceding_pair_rule_would_fire": preceding_pair_rule_would_fire,
        "widened_rule_branch": widened_rule_branch,
        "widened_rule_would_fire": widened_rule_would_fire,
        "pre_acting_release_rule_branch": (
            pre_acting_release_rule_branch),
        "pre_acting_release_rule_would_fire": (
            pre_acting_release_rule_would_fire),
        "companion_rule_branch": companion_rule_branch,
        "companion_rule_would_fire": companion_rule_would_fire,
        "acting_breadth_rule_branch": acting_breadth_rule_branch,
        "acting_breadth_rule_would_fire": (
            acting_breadth_rule_would_fire),
        "newest_breadth_rule_branch": newest_breadth_rule_branch,
        "newest_breadth_rule_would_fire": (
            newest_breadth_rule_would_fire),
        "singleton_release_rule_branch": (
            singleton_release_rule_branch),
        "singleton_release_rule_would_fire": (
            singleton_release_rule_would_fire),
        "stationary_support_rule_branch": (
            stationary_support_rule_branch),
        "stationary_support_rule_would_fire": (
            stationary_support_rule_would_fire),
        "partial_scoped_support_rule_branch": (
            partial_scoped_support_rule_branch),
        "partial_scoped_support_rule_would_fire": (
            partial_scoped_support_rule_would_fire),
        "widened_removal_rule_branch": widened_removal_rule_branch,
        "widened_removal_rule_would_fire": (
            widened_removal_rule_would_fire),
        "partial_ungated_rule_branch": partial_ungated_rule_branch,
        "partial_ungated_rule_would_fire": partial_ungated_rule_would_fire,
        "reference_purity_rule_branch": purity_rule_branch,
        "reference_purity_rule_would_fire": purity_rule_would_fire,
        "extended_rule_branch": extended_rule_branch,
        "extended_rule_would_fire": extended_rule_would_fire,
        "minority_rule_branch": minority_rule_branch,
        "minority_rule_would_fire": minority_rule_would_fire,
        "unexpired_joint_rule_branch": unexpired_branch,
        "unexpired_joint_rule_would_fire": unexpired_would_fire,
        "bounded_authority_rule_branch": bounded_branch,
        "bounded_authority_rule_would_fire": bounded_would_fire,
        "bounded_recovery_armed": bounded_recovery_armed,
        "bounded_abstention_armed": bounded_abstention_armed,
        "legacy_long_rule_branch": legacy_long_branch,
        "legacy_long_rule_would_fire": legacy_long_would_fire,
        "bounded_authority_legacy_rule_branch": bounded_legacy_branch,
        "bounded_authority_legacy_rule_would_fire": (
            bounded_legacy_would_fire),
    }
    return {
        "observations_in_stage": None,  # filled by caller
        "total_observed": len(observed),
        "candidate_selection": decision["selection"],
        "candidate_source": decision["source"],
        "candidate_decision": decision,
        "candidate_decision_record": decision_record,
        # Aliases matching protocol wording
        "candidate_signal_record": {
            "signal_events": decision["signal_events"],
            "legacy_signal_events": decision["legacy_signal_events"],
            "opposed_count": decision["opposed_count"],
            "matched_count": decision["matched_count"],
            "legacy_opposed_count": decision["legacy_opposed_count"],
            "legacy_matched_count": decision["legacy_matched_count"],
            "gate_fired": decision["gate_fired"],
            "abstention_trigger_kind": decision["abstention_trigger_kind"],
            "abstained": decision["abstained"],
            "gate_evaluable": decision["gate_evaluable"],
            "acting_model_source": decision["source"],
        },
        "candidate_archive_record": {
            "archive_events": decision["archive_events"],
            "concordant_count": decision["concordant_count"],
            "archive_matched_count": decision["archive_matched_count"],
            "archive_events_count": decision["archive_events_count"],
            "recovery_fired": decision["recovery_fired"],
            "branch": decision["branch"],
        },
        "candidate_joint_record": {
            "joint_events": decision["joint_events"],
            "joint_flags": decision["joint_flags"],
            "joint_count": decision["joint_count"],
            "legacy_joint_events": decision["legacy_joint_events"],
            "legacy_joint_flags": decision["legacy_joint_flags"],
            "legacy_joint_count": decision["legacy_joint_count"],
            "recovery_fired": decision["recovery_fired"],
            "branch": decision["branch"],
        },
        "candidate_legacy_record": {
            "legacy_signal_events": decision["legacy_signal_events"],
            "legacy_opposed_count": decision["legacy_opposed_count"],
            "legacy_matched_count": decision["legacy_matched_count"],
            "legacy_joint_events": decision["legacy_joint_events"],
            "legacy_joint_flags": decision["legacy_joint_flags"],
            "legacy_joint_count": decision["legacy_joint_count"],
            "legacy_long_rule_branch": legacy_long_branch,
            "legacy_long_rule_would_fire": legacy_long_would_fire,
        },
        "candidate_expiry_record": {
            "expiry_spans": decision["expiry_spans"],
            "comparable_span_count": decision["comparable_span_count"],
            "disagreeing_span_count": decision["disagreeing_span_count"],
            "stable_disagreement": decision["stable_disagreement"],
            "preceding_spans": decision["preceding_spans"],
            "preceding_comparable_span_count": decision[
                "preceding_comparable_span_count"],
            "preceding_disagreeing_span_count": decision[
                "preceding_disagreeing_span_count"],
            "preceding_stable_disagreement": decision[
                "preceding_stable_disagreement"],
            "long_disagreement": decision["long_disagreement"],
            "recovery_arming_leg": decision["recovery_arming_leg"],
            "recent_events": decision["recent_events"],
            "recent_concordant_count": decision["recent_concordant_count"],
            "recovery_armed": decision["recovery_armed"],
            "abstention_armed": decision["abstention_armed"],
            "recovery_would_fire": decision["recovery_would_fire"],
            "abstention_would_fire": decision["abstention_would_fire"],
        },
        "candidate_minority_record": {
            "minority_events": decision["minority_events"],
            "minority_joint_events": decision["minority_joint_events"],
            "minority_joint_flags": decision["minority_joint_flags"],
            "minority_matched_count": decision["minority_matched_count"],
            "minority_concordant_count": decision["minority_concordant_count"],
            "minority_joint_count": decision["minority_joint_count"],
            "minority_archive_matched_count": decision["minority_archive_matched_count"],
            "minority_matched_archive_count": decision["minority_matched_archive_count"],
            "minority_discordant_count": decision["minority_discordant_count"],
            "minority_set_count": decision["minority_set_count"],
            "minority_fraction": decision["minority_fraction"],
            "minority_armed": decision["minority_armed"],
            "minority_fired": decision["minority_fired"],
            "minority_recovery_fired": decision["minority_recovery_fired"],
            "minority_would_fire": decision["minority_would_fire"],
            "minority_model_archive_count": decision[
                "minority_model_archive_count"],
            "minority_model_inverted": decision["minority_model_inverted"],
            "branch": decision["branch"],
        },
        "candidate_minority_model_record": {
            "minority_model_archive_count": decision[
                "minority_model_archive_count"],
            "minority_model_inverted": decision["minority_model_inverted"],
            "archive_events_count": decision["archive_events_count"],
            "branch": decision["branch"],
        },
        "candidate_purity_record": {
            "reference_events": decision["reference_events"],
            "reference_matched_count": decision["reference_matched_count"],
            "reference_concordant_count": decision[
                "reference_concordant_count"],
            "reference_purity": decision["reference_purity"],
            "purity_armed": decision["purity_armed"],
            "purity_threshold": decision["purity_threshold"],
            "recovery_disarmed_by_purity": decision[
                "recovery_disarmed_by_purity"],
            "minority_disarmed_by_purity": decision[
                "minority_disarmed_by_purity"],
            "branch": decision["branch"],
        },
        "candidate_abstention_gate_record": {
            "acting_events": decision["acting_events"],
            "acting_matched_count": decision["acting_matched_count"],
            "acting_opposed_count": decision["acting_opposed_count"],
            "supporting_opposed_count": decision[
                "supporting_opposed_count"],
            "support_threshold": decision["support_threshold"],
            "abstention_gate_armed": decision["abstention_gate_armed"],
            "abstention_disarmed_by_purity": decision[
                "abstention_disarmed_by_purity"],
            "abstention_disarmed_by_support": decision[
                "abstention_disarmed_by_support"],
            "abstention_trigger_kind": decision["abstention_trigger_kind"],
            "preceding_pair_events": decision["preceding_pair_events"],
            "preceding_pair_matched_count": decision[
                "preceding_pair_matched_count"],
            "preceding_pair_opposed_count": decision[
                "preceding_pair_opposed_count"],
            "preceding_pair_armed": decision["preceding_pair_armed"],
            "preceding_pair_threshold": decision[
                "preceding_pair_threshold"],
            "abstention_disarmed_by_preceding_pair": decision[
                "abstention_disarmed_by_preceding_pair"],
            "companion_matched": decision["companion_matched"],
            "companion_concordant": decision["companion_concordant"],
            "companion_armed": decision["companion_armed"],
            "companion_threshold": decision["companion_threshold"],
            "abstention_disarmed_by_companion": decision[
                "abstention_disarmed_by_companion"],
            "newest4_opposed_count": decision["newest4_opposed_count"],
            "widened_armed": decision["widened_armed"],
            "widened_threshold": decision["widened_threshold"],
            "purity_armed": decision["purity_armed"],
            "reference_purity": decision["reference_purity"],
            "branch": decision["branch"],
        },
        "candidate_stale_record": {
            "stale_joint_events": decision["stale_joint_events"],
            "stale_minority_joint_events": decision[
                "stale_minority_joint_events"],
            "stale_joint_pair_count": decision[
                "stale_joint_pair_count"],
            "stale_minority_joint_pair_count": decision[
                "stale_minority_joint_pair_count"],
            "staleness_pair_threshold": decision[
                "staleness_pair_threshold"],
            "recovery_disarmed_by_staleness": decision[
                "recovery_disarmed_by_staleness"],
            "minority_disarmed_by_staleness": decision[
                "minority_disarmed_by_staleness"],
            "branch": decision["branch"],
        },
        "candidate_companion_record": {
            "companion_matched": decision["companion_matched"],
            "companion_concordant": decision["companion_concordant"],
            "companion_armed": decision["companion_armed"],
            "companion_threshold": decision["companion_threshold"],
            "abstention_disarmed_by_companion": decision[
                "abstention_disarmed_by_companion"],
            "abstention_disarmed_by_preceding_pair": decision[
                "abstention_disarmed_by_preceding_pair"],
            "abstention_trigger_kind": decision[
                "abstention_trigger_kind"],
            "branch": decision["branch"],
        },
        "candidate_acting_breadth_record": {
            "acting_joint_events": decision["acting_joint_events"],
            "acting_minority_joint_events": decision[
                "acting_minority_joint_events"],
            "acting_joint_count": decision["acting_joint_count"],
            "acting_minority_joint_count": decision[
                "acting_minority_joint_count"],
            "acting_joint_threshold": decision[
                "acting_joint_threshold"],
            "recovery_disarmed_by_acting_breadth": decision[
                "recovery_disarmed_by_acting_breadth"],
            "minority_disarmed_by_acting_breadth": decision[
                "minority_disarmed_by_acting_breadth"],
            "branch": decision["branch"],
        },
        "candidate_newest_breadth_record": {
            "newest_joint_events": decision["newest_joint_events"],
            "newest_joint_count": decision["newest_joint_count"],
            "newest_joint_threshold": decision[
                "newest_joint_threshold"],
            "recovery_disarmed_by_newest_breadth": decision[
                "recovery_disarmed_by_newest_breadth"],
            "acting_joint_count": decision["acting_joint_count"],
            "recovery_disarmed_by_acting_breadth": decision[
                "recovery_disarmed_by_acting_breadth"],
            "branch": decision["branch"],
        },
        "candidate_singleton_release_record": {
            "singleton_release_fired": decision[
                "singleton_release_fired"],
            "newest_joint_count": decision["newest_joint_count"],
            "newest_joint_threshold": decision[
                "newest_joint_threshold"],
            "acting_joint_count": decision["acting_joint_count"],
            "acting_joint_threshold": decision[
                "acting_joint_threshold"],
            "recovery_disarmed_by_newest_breadth": decision[
                "recovery_disarmed_by_newest_breadth"],
            "recovery_fired": decision["recovery_fired"],
            "branch": decision["branch"],
        },
        "candidate_support_record": {
            "supporting_opposed_count": decision[
                "supporting_opposed_count"],
            "support_threshold": decision["support_threshold"],
            "abstention_disarmed_by_support": decision[
                "abstention_disarmed_by_support"],
            "abstention_gate_armed": decision[
                "abstention_gate_armed"],
            "abstention_trigger_kind": decision[
                "abstention_trigger_kind"],
            "singleton_release_fired": decision[
                "singleton_release_fired"],
            "branch": decision["branch"],
        },
        "candidate_authority_record": decision_record,
        "candidate_preceding_record": {
            "preceding_spans": decision["preceding_spans"],
            "preceding_comparable_span_count": decision[
                "preceding_comparable_span_count"],
            "preceding_disagreeing_span_count": decision[
                "preceding_disagreeing_span_count"],
            "preceding_stable_disagreement": decision[
                "preceding_stable_disagreement"],
            "long_disagreement": decision["long_disagreement"],
            "recovery_arming_leg": decision["recovery_arming_leg"],
            "recovery_armed": decision["recovery_armed"],
            "branch": decision["branch"],
        },
        "candidate_preceding_pair_record": {
            "preceding_pair_events": decision["preceding_pair_events"],
            "preceding_pair_matched_count": decision[
                "preceding_pair_matched_count"],
            "preceding_pair_opposed_count": decision[
                "preceding_pair_opposed_count"],
            "preceding_pair_armed": decision["preceding_pair_armed"],
            "preceding_pair_threshold": decision[
                "preceding_pair_threshold"],
            "abstention_disarmed_by_preceding_pair": decision[
                "abstention_disarmed_by_preceding_pair"],
            "abstention_gate_armed": decision["abstention_gate_armed"],
            "abstention_trigger_kind": decision[
                "abstention_trigger_kind"],
            "branch": decision["branch"],
        },
        "candidate_widened_record": {
            "newest4_opposed_count": decision["newest4_opposed_count"],
            "widened_armed": decision["widened_armed"],
            "widened_threshold": decision["widened_threshold"],
            "abstention_trigger_kind": decision[
                "abstention_trigger_kind"],
            "abstention_gate_armed": decision["abstention_gate_armed"],
            "branch": decision["branch"],
        },
        "widened_rule_branch": widened_rule_branch,
        "widened_rule_would_fire": widened_rule_would_fire,
        "abstention_higher_corroboration_rule_branch": higher_rule_branch,
        "abstention_higher_corroboration_rule_would_fire": higher_rule_would_fire,
        "abstention_release_rule_branch": release_rule_branch,
        "abstention_release_rule_would_fire": release_rule_would_fire,
        "purity_only_rule_branch": purity_only_rule_branch,
        "purity_only_rule_would_fire": purity_only_rule_would_fire,
        "partial_purity_rule_branch": partial_purity_rule_branch,
        "partial_purity_rule_would_fire": partial_purity_rule_would_fire,
        "preceding_pair_rule_branch": preceding_pair_rule_branch,
        "preceding_pair_rule_would_fire": preceding_pair_rule_would_fire,
        "partial_ungated_rule_branch": partial_ungated_rule_branch,
        "partial_ungated_rule_would_fire": partial_ungated_rule_would_fire,
        "reference_purity_rule_branch": purity_rule_branch,
        "reference_purity_rule_would_fire": purity_rule_would_fire,
        "extended_rule_branch": extended_rule_branch,
        "extended_rule_would_fire": extended_rule_would_fire,
        "minority_rule_branch": minority_rule_branch,
        "minority_rule_would_fire": minority_rule_would_fire,
        "unexpired_joint_rule_branch": unexpired_branch,
        "unexpired_joint_rule_would_fire": unexpired_would_fire,
        "bounded_authority_rule_branch": bounded_branch,
        "bounded_authority_rule_would_fire": bounded_would_fire,
        "bounded_recovery_armed": bounded_recovery_armed,
        "bounded_abstention_armed": bounded_abstention_armed,
        "legacy_long_rule_branch": legacy_long_branch,
        "legacy_long_rule_would_fire": legacy_long_would_fire,
        "bounded_authority_legacy_rule_branch": bounded_legacy_branch,
        "bounded_authority_legacy_rule_would_fire": (
            bounded_legacy_would_fire),
        "candidate_checkpoint_sha256": saved["candidate"]["sha256"],
        "candidate_restore_replay_identity": replay_ok,
        "widened_decision_branch": widened_decision["branch"],
        "stationary_decision_branch": (
            stationary_decision["branch"]),
        "stationary_decision_trigger_kind": (
            stationary_decision["abstention_trigger_kind"]),
        "stationary_decision_abstained": (
            stationary_decision["abstained"]),
        "singleton_decision_branch": (
            singleton_decision["branch"]),
        "singleton_decision_trigger_kind": (
            singleton_decision["abstention_trigger_kind"]),
        "singleton_decision_abstained": (
            singleton_decision["abstained"]),
        "newest_decision_branch": (
            newest_decision["branch"]),
        "newest_decision_trigger_kind": (
            newest_decision["abstention_trigger_kind"]),
        "newest_decision_abstained": (
            newest_decision["abstained"]),
        "acting_decision_branch": (
            acting_decision["branch"]),
        "acting_decision_trigger_kind": (
            acting_decision["abstention_trigger_kind"]),
        "acting_decision_abstained": (
            acting_decision["abstained"]),
        "companion_decision_branch": (
            companion_decision["branch"]),
        "companion_decision_trigger_kind": (
            companion_decision["abstention_trigger_kind"]),
        "companion_decision_abstained": (
            companion_decision["abstained"]),
        "pre_acting_decision_branch": (
            pre_acting_decision["branch"]),
        "pre_acting_decision_trigger_kind": (
            pre_acting_decision["abstention_trigger_kind"]),
        "pre_acting_decision_abstained": (
            pre_acting_decision["abstained"]),
        "widened_removal_decision_branch": (
            widened_removal_decision["branch"]),
        "widened_removal_decision_trigger_kind": (
            widened_removal_decision["abstention_trigger_kind"]),
        "widened_removal_decision_abstained": (
            widened_removal_decision["abstained"]),
        "pre_acting_release_rule_branch": (
            pre_acting_release_rule_branch),
        "pre_acting_release_rule_would_fire": (
            pre_acting_release_rule_would_fire),
        "companion_rule_branch": companion_rule_branch,
        "companion_rule_would_fire": companion_rule_would_fire,
        "acting_breadth_rule_branch": acting_breadth_rule_branch,
        "acting_breadth_rule_would_fire": (
            acting_breadth_rule_would_fire),
        "newest_breadth_rule_branch": newest_breadth_rule_branch,
        "newest_breadth_rule_would_fire": (
            newest_breadth_rule_would_fire),
        "singleton_release_rule_branch": (
            singleton_release_rule_branch),
        "singleton_release_rule_would_fire": (
            singleton_release_rule_would_fire),
        "stationary_support_rule_branch": (
            stationary_support_rule_branch),
        "stationary_support_rule_would_fire": (
            stationary_support_rule_would_fire),
        "partial_scoped_support_rule_branch": (
            partial_scoped_support_rule_branch),
        "partial_scoped_support_rule_would_fire": (
            partial_scoped_support_rule_would_fire),
        "widened_removal_rule_branch": widened_removal_rule_branch,
        "widened_removal_rule_would_fire": (
            widened_removal_rule_would_fire),
        "inverted_decision_branch": inverted_decision["branch"],
        "inverted_decision_trigger_kind": inverted_decision[
            "abstention_trigger_kind"],
        "inverted_decision_abstained": inverted_decision["abstained"],
        "branch_selection_identical_to_inverted": bool(
            inverted_decision["branch"] == decision["branch"]),
        "branch_selection_identical_to_stationary": (
            branch_selection_identical),
        "branch_selection_identical_to_singleton": bool(
            singleton_decision["branch"] == decision["branch"]),
        "branch_selection_identical_to_newest": bool(
            newest_decision["branch"] == decision["branch"]),
        "branch_selection_identical_to_acting": bool(
            acting_decision["branch"] == decision["branch"]),
        "branch_selection_identical_to_companion": bool(
            companion_decision["branch"] == decision["branch"]),
        "branch_selection_identical_to_pre_acting": bool(
            pre_acting_decision["branch"] == decision["branch"]),
        "branch_selection_identical_to_widened_removal": bool(
            widened_removal_decision["branch"] == decision["branch"]),
        "minority_model_crosscheck": minority_model_crosscheck,
        "scores": scores,
    }


def measure(seeds=DEV):
    if type(seeds) not in (tuple, list) or tuple(seeds) not in (DEV, ADDITIONAL):
        raise ValueError("cohort not precommitted")
    cohort = "development" if tuple(seeds) == DEV else "additional"
    report = {
        "schema": SCHEMA,
        "protocol": "benchmarks/partial_scoped_support_abstention_recovery_protocol.json",
        "experiment": "partial_scoped_support_abstention_recovery",
        "cohort": cohort,
        "seeds": list(seeds),
        "blind": False,
        "learner_training_actions": 0,
        "learner_information_acquisition_actions": 0,
        "additional_requested_observations": 0,
        "test_episodes_per_checkpoint_seed": TEST_N,
        "repeated_test_indices_across_checkpoints": True,
        "actual_outcomes_stochastic": True,
        "rows": [],
    }
    for seed in seeds:
        history = []
        actor_costs = {}
        stages = {}
        a_history = None
        for stage, physics, first, n in STAGES:
            train, cost = public_train(seed, physics, first, n)
            actor_costs[stage] = dict(cost, actor_actions=cost["observations"])
            if stage == "A":
                history.extend(train)
                a_history = list(history)
                continue
            phase = {}
            for k in CHECKPOINTS[stage]:
                observed = history + train[:k]
                entry = score_checkpoint(seed, stage, observed)
                entry["observations_in_stage"] = k
                phase[str(k)] = entry
            stages[stage] = phase
            history.extend(train)
        cont, cont_cost = public_train(seed, CONTROL[1], CONTROL[2], CONTROL[3])
        actor_costs["control_continuation"] = dict(
            cont_cost, actor_actions=cont_cost["observations"])
        phase = {}
        for k in CHECKPOINTS["control"]:
            observed = a_history + cont[:k]
            entry = score_checkpoint(seed, "control", observed)
            entry["observations_in_stage"] = k
            phase[str(k)] = entry
        stages["control"] = phase
        report["rows"].append({
            "seed": seed,
            "true_and_reported_training_costs": actor_costs,
            "stages": stages,
            "final_training_count": len(history),
        })
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cohort", choices=("development", "additional"),
                   default="development")
    a = p.parse_args()
    print(json.dumps(
        measure(DEV if a.cohort == "development" else ADDITIONAL),
        indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
