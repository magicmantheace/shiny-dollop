"""Frozen evidence-opposition onset guard benchmark; simulation-only.

Protocol: benchmarks/evidence_opposition_onset_guard_protocol.json
(frozen 2026-10-28 BEFORE candidate implementation). This harness
reuses StochasticWorld and public_train from
benchmarks/stochastic_prequential_benchmark.py unchanged: the
StochasticWorld A->B1->return-A->B2 schedule plus a stationary
A->A control arm, exactly as registered. Both cohorts become
INSPECTED once evaluated here; no parameter, threshold, seed, or
checkpoint in the protocol may be revised against these results.

Per seed, per stage, per checkpoint, per method the harness records
successes, harmful TEST actions, failed-by-abstention count, and
attempted tasks (criterion 6 full accounting), plus the candidate's
recorded signal record (per newest-window event: span, reported
class, reference count, reference majority, matched/opposed flags;
plus opposed_count, matched_count, gate fired / abstained flag,
gate-evaluable flag), checkpoint SHA256, and restore-replay
identity. TRAIN actor accounting (actual harm / productive /
neutral, reported harm, label flips) is counted once per seed,
never per checkpoint or method. Learner acquisition actions are
frozen at 0. TEST is read-only: every learner method's checkpoint
record is verified unchanged after TEST evaluation.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.evidence_opposition_onset_guard import (
    EvidenceOppositionGuardMemory,
)
from developmental_ai.first_contact_onset_guard import (
    FirstContactGuardMemory,
)
from developmental_ai.gated_archive_prequential_memory import (
    GatedArchivePrequentialMemory,
)
from developmental_ai.observable_affordances import digest
from benchmarks.relation_transfer_benchmark import relation_model, summarize
from benchmarks.stochastic_prequential_benchmark import (
    StochasticWorld, public_train,
)
from benchmarks.variable_affordance_benchmark import public_outcome

SCHEMA = "developmental-ai.evidence-opposition-onset-guard-benchmark/v1"
DEV = (312003, 312021, 312039)
ADDITIONAL = (313001, 313017, 313041)
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
    "candidate", "recent8", "recent32", "first_contact_onset_guard",
    "gated_archive_prequential", "frozen_A", "cumulative",
    "always_abstain", "untrained_random", "privileged_expected_oracle",
)
LEARNER_METHODS = (
    "candidate", "recent8", "recent32", "first_contact_onset_guard",
    "gated_archive_prequential", "frozen_A", "cumulative",
)


def evaluate(seed, physics, index, method, models):
    """Identical TEST play to stochastic_prequential_benchmark.evaluate,
    extended to this protocol's method names. The privileged oracle knows
    only the expected hidden rule, never the realized stochastic flip."""
    if method not in METHODS:
        raise ValueError("unsupported evidence-opposition benchmark policy")
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
        "candidate": fitted(EvidenceOppositionGuardMemory, history),
        "recent8": relation_model(history[-8:]),
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
    restored = EvidenceOppositionGuardMemory.restore(
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
    return {
        "observations_in_stage": None,  # filled by caller
        "total_observed": len(observed),
        "candidate_selection": decision["selection"],
        "candidate_source": decision["source"],
        "candidate_decision": decision,
        "candidate_signal_record": {
            "signal_events": decision["signal_events"],
            "opposed_count": decision["opposed_count"],
            "matched_count": decision["matched_count"],
            "gate_fired": decision["gate_fired"],
            "abstained": decision["abstained"],
            "gate_evaluable": decision["gate_evaluable"],
            "acting_model_source": decision["source"],
        },
        # Alias matching protocol wording (gate record)
        "candidate_gate_record": {
            "signal_events": decision["signal_events"],
            "opposed_count": decision["opposed_count"],
            "matched_count": decision["matched_count"],
            "gate_fired": decision["gate_fired"],
            "abstained": decision["abstained"],
            "gate_evaluable": decision["gate_evaluable"],
            "acting_model_source": decision["source"],
        },
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
        "protocol": "benchmarks/evidence_opposition_onset_guard_protocol.json",
        "experiment": "evidence_opposition_onset_guard",
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
