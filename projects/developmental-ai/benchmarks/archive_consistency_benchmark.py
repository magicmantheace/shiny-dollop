"""Frozen independent-seed comparison of cross-half memory screening.

This cannot validate real-world safety, source provenance or new families.
Only a separate random synthetic actor takes TRAIN actions; no phase labels
or oracle physics are provided to any compared learner.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.observable_affordances import (
    ConsistentRegimeMemory, FastRegimeMemory, RegimeRetrievalMemory
)
from benchmarks.fast_reacquisition_benchmark import (
    METHODS as HISTORIC_METHODS, TEST_N, build_controllers, eval_episode,
    freeze_numeric
)
from benchmarks.regime_retrieval_benchmark import actor_event
from benchmarks.observable_affordance_benchmark import summary

SCHEMA = "developmental-ai.archive-consistency-benchmark/v1"
DEV = (132003, 132021, 132039)
ADDITIONAL = (133001, 133017, 133041)
METHODS = ("consistent_retrieval",) + HISTORIC_METHODS
STAGES = (
    ("A", "route", 80000, 160),
    ("B", "route-reversed", 81000, 160),
    ("return_A", "route", 82000, 48),
)
CHECKPOINTS = {"B": (0, 4, 8, 12, 24, 48, 160),
               "return_A": (0, 4, 8, 12, 24, 48)}
TEST_START = {"B": 90000, "return_A": 91000}


def measure(seeds=DEV):
    if type(seeds) not in (tuple, list) or tuple(seeds) not in (DEV, ADDITIONAL):
        raise ValueError("not a frozen archive-consistency cohort")
    report = {"schema": SCHEMA, "blind": False,
              "protocol": "benchmarks/archive_consistency_protocol.json",
              "learner_training_actions": 0,
              "test_episodes_per_checkpoint_per_seed": TEST_N, "rows": []}
    for seed in seeds:
        consistent = ConsistentRegimeMemory()
        fast = FastRegimeMemory()
        fixed = RegimeRetrievalMemory()
        costs = {"observations": 0, "harmful": 0,
                 "productive": 0, "neutral": 0}
        scores_by_checkpoint = {}
        for label, domain, start, count in STAGES:
            added = 0
            for checkpoint in CHECKPOINTS.get(label, ()):
                while added < checkpoint:
                    event = actor_event(seed, domain, start + added)
                    for model in (consistent, fast, fixed):
                        model.observe(event)
                    added += 1
                    costs["observations"] += 1
                    costs["harmful"] += int(event["damage"])
                    costs["productive"] += int(event["progress"])
                    costs["neutral"] += int(not event["damage"] and not event["progress"])
                snapshots = [model.record() for model in (consistent, fast, fixed)]
                rebuilt = [
                    ConsistentRegimeMemory.restore(snapshots[0]),
                    FastRegimeMemory.restore(snapshots[1]),
                    RegimeRetrievalMemory.restore(snapshots[2]),
                ]
                if any(model.record() != saved for model, saved in zip(rebuilt, snapshots)):
                    raise AssertionError("inconsistent replay at checkpoint")
                stable, oldfast, oldfixed = rebuilt
                controls = build_controllers(oldfast, oldfixed,
                                             freeze_numeric(consistent.events[:160]))
                scores = {}
                for method in METHODS:
                    # The old evaluator is fixed and unchanged. Inject the new
                    # optional policy only under its old simulation-only slot.
                    action_method = ("fast_retrieval" if method == "consistent_retrieval"
                                     else method)
                    policies = ({"fast_retrieval": stable} if method == "consistent_retrieval"
                                else controls)
                    episodes = [eval_episode(seed, domain,
                        TEST_START[label] + i, action_method, policies)
                        for i in range(TEST_N)]
                    scores[method] = {**summary(episodes),
                                      "abstained": sum(x["abstained"] for x in episodes)}
                if any(model.record() != saved for model, saved in zip(rebuilt, snapshots)):
                    raise AssertionError("test changed learner observations")
                scores_by_checkpoint[f"{label}_{checkpoint}"] = {
                    "stage": label, "new_observations": checkpoint,
                    "trained_events": len(consistent.events),
                    "consistency": stable.selection(),
                    "fast_selection": oldfast.selection(),
                    "fixed_selection": oldfixed.selection(),
                    "scores": scores,
                    "checkpoint_sha256": snapshots[0]["sha256"],
                }
            while added < count:
                event = actor_event(seed, domain, start + added)
                for model in (consistent, fast, fixed):
                    model.observe(event)
                added += 1
                costs["observations"] += 1
                costs["harmful"] += int(event["damage"])
                costs["productive"] += int(event["progress"])
                costs["neutral"] += int(not event["damage"] and not event["progress"])
        if not (consistent.events == fast.events == fixed.events):
            raise AssertionError("training budgets mismatch")
        report["rows"].append({"seed": seed, "checkpoints": scores_by_checkpoint,
                               "actor_totals": costs,
                               "final_checkpoint_sha256": consistent.record()["sha256"]})
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", choices=("development", "additional"),
                        default="development")
    args = parser.parse_args()
    print(json.dumps(measure(DEV if args.cohort == "development" else ADDITIONAL),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
