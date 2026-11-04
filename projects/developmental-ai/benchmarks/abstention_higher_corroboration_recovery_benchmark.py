"""Frozen abstention higher corroboration recovery benchmark; simulation-only.

Protocol: benchmarks/abstention_higher_corroboration_recovery_protocol.json
(frozen 2026-11-03 BEFORE candidate implementation). This harness
reuses StochasticWorld and public_train from
benchmarks/stochastic_prequential_benchmark.py unchanged: the
StochasticWorld A->B1->return-A->B2 schedule plus a stationary
A->A control arm, exactly as registered. Both cohorts become
INSPECTED once evaluated here; no parameter, threshold, seed, or
checkpoint in the protocol may be revised against these results.

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
threshold, abstention_gate_armed, and both abstention-disarmed flags,
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
candidate's recorded counts alone, whether the graded abstention-release candidate's rule (this candidate's full
rule with the abstention release gate's leg-S support threshold at
its graded value 3 instead of 4), whether the graded reference-purity candidate's rule (this candidate's full
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

SCHEMA = "developmental-ai.abstention-higher-corroboration-recovery-benchmark/v1"
DEV = (412003, 412021, 412039)
ADDITIONAL = (413001, 413017, 413041)
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
    "candidate", "recent8", "abstention_release_gated_recovery",
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
    "candidate", "recent8", "abstention_release_gated_recovery",
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
        raise ValueError("unsupported abstention-higher-corroboration benchmark policy")
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
        "candidate": fitted(AbstentionHigherCorroborationRecoveryMemory, history),
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
    restored = AbstentionHigherCorroborationRecoveryMemory.restore(
        json.loads(json.dumps(saved["candidate"])))
    replay_ok = (
        restored.record() == saved["candidate"]
        and restored.selection()[0] == decision
    )
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
    # abstention-release candidate's rule is this candidate's full
    # rule with the abstention release gate's leg-S support
    # threshold at its graded value 3 instead of 4: regular recovery
    # (purity-gated), then minority recovery (purity-gated), then
    # abstention iff opposed_count == 2, abstention authority armed,
    # purity armed, and acting_opposed_count >= 3.
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
        "concordant_count": decision["concordant_count"],
        "archive_matched_count": decision["archive_matched_count"],
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
        "abstention_release_rule_branch": release_rule_branch,
        "abstention_release_rule_would_fire": release_rule_would_fire,
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
            "purity_armed": decision["purity_armed"],
            "reference_purity": decision["reference_purity"],
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
        "abstention_release_rule_branch": release_rule_branch,
        "abstention_release_rule_would_fire": release_rule_would_fire,
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
        "scores": scores,
    }


def measure(seeds=DEV):
    if type(seeds) not in (tuple, list) or tuple(seeds) not in (DEV, ADDITIONAL):
        raise ValueError("cohort not precommitted")
    cohort = "development" if tuple(seeds) == DEV else "additional"
    report = {
        "schema": SCHEMA,
        "protocol": "benchmarks/abstention_higher_corroboration_recovery_protocol.json",
        "experiment": "abstention_higher_corroboration_recovery",
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
