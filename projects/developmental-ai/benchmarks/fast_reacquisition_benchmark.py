"""Precommitted read-only TEST checkpoints after A->B->A feedback.

A separate random simulator actor supplies public first-action outcomes.
Actor harm is real in this simulation and counted ONCE (not per test policy).
No phase labels, hidden rule or TEST feedback are passed to the learners.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.observable_affordances import (
    ObservableWorld, NumericOutcomeMemory, RegimeRetrievalMemory,
    FastRegimeMemory, outcome,
)
from benchmarks.regime_retrieval_benchmark import actor_event
from benchmarks.observable_affordance_benchmark import summary

SCHEMA = "developmental-ai.fast-reacquisition-benchmark/v1"
DEV = (122003, 122021, 122039)
ADDITIONAL = (123001, 123017, 123041)
METHODS = (
    "fast_retrieval", "fixed_12_retrieval", "recent_8_knn",
    "recent_32_knn", "cumulative_knn", "frozen_A_knn",
    "untrained_random", "always_abstain", "privileged_oracle",
)
STAGES = (
    ("A", "route", 60000, 160),
    ("B", "route-reversed", 61000, 160),
    ("return_A", "route", 62000, 48),
)
EVAL_START = {"B": 70000, "return_A": 71000}
CHECKPOINTS = {"B": (0, 4, 8, 12, 24, 48, 160),
               "return_A": (0, 4, 8, 12, 24, 48)}
TEST_N = 30


def freeze_numeric(rows):
    model = NumericOutcomeMemory()
    for row in rows:
        model.add(row)
    return model


def build_controllers(fast, fixed, frozen_A):
    events = fast.events
    return {
        "fast_retrieval": fast,
        "fixed_12_retrieval": fixed,
        "recent_8_knn": freeze_numeric(events[-8:]),
        "recent_32_knn": freeze_numeric(events[-32:]),
        "cumulative_knn": freeze_numeric(events),
        "frozen_A_knn": frozen_A,
    }


def eval_episode(seed, domain, index, method, controllers):
    if method not in METHODS:
        raise ValueError("unknown frozen evaluation method")
    world = ObservableWorld(seed, "test", index, domain)
    rng = random.Random(int(world.episode[16:32], 16) ^ 0x831a)
    harm = 0
    abstained = False
    for _ in range(world.budget):
        before = world.frame()
        if before["done"]:
            break
        if method in controllers:
            selected = controllers[method].choose(before)
        elif method == "always_abstain":
            selected = None
        elif method == "untrained_random":
            selected = rng.choice(before["actions"])["id"]
        else:
            # Privileged TEST-only ceiling, never a learner input.
            productive = []
            for row in before["actions"]:
                x, y = row["features"]
                if domain == "route-reversed":
                    x, y = y, x
                if y >= x + 2:
                    productive.append(row["id"])
            selected = productive[0] if productive else None
        if selected is None:
            abstained = True
            break
        after = world.step(selected, before["tick"])
        harm += int(outcome(before, selected, after)["damage"])
    return {"success": int(world.success()), "hurt": harm,
            "stalled": int(not world.success()),
            "attempts": world.tick, "abstained": int(abstained)}


def measure(seeds=DEV):
    if type(seeds) not in (tuple, list) or tuple(seeds) not in (DEV, ADDITIONAL):
        raise ValueError("not a precommitted cohort")
    result = {"schema": SCHEMA, "blind": False,
              "protocol": "benchmarks/fast_reacquisition_protocol.json",
              "learner_data_collection_actions": 0,
              "public_engineered_numeric_features": True,
              "test_episodes_per_checkpoint_per_seed": TEST_N, "rows": []}
    for seed in seeds:
        fast, fixed = FastRegimeMemory(), RegimeRetrievalMemory()
        actor_counts = {"observations": 0, "harmful": 0,
                        "productive": 0, "neutral": 0}
        per_stage_cost = {}
        evaluations = {}
        for label, domain, start, count in STAGES:
            added = 0
            stage_cost = {"observations": 0, "harmful": 0,
                          "productive": 0, "neutral": 0}
            checkpoints = CHECKPOINTS.get(label, ())
            for checkpoint in checkpoints:
                while added < checkpoint:
                    event = actor_event(seed, domain, start + added)
                    fast.observe(event)
                    fixed.observe(event)
                    added += 1
                    stage_cost["observations"] += 1
                    stage_cost["harmful"] += int(event["damage"])
                    stage_cost["productive"] += int(event["progress"])
                    stage_cost["neutral"] += int(not event["progress"] and not event["damage"])
                # Immutable replay-verified checkpoint; evaluate on a fresh
                # learner instance so no warmed candidate caches are inherited.
                f_record, x_record = fast.record(), fixed.record()
                restored_fast = FastRegimeMemory.restore(f_record)
                restored_fixed = RegimeRetrievalMemory.restore(x_record)
                if restored_fast.record() != f_record or restored_fixed.record() != x_record:
                    raise AssertionError("checkpoint reconstruction changed experience")
                frozen_A = freeze_numeric(fast.events[:STAGES[0][3]])
                controllers = build_controllers(restored_fast, restored_fixed, frozen_A)
                assert label in EVAL_START
                scores = {}
                for method in METHODS:
                    episodes = [eval_episode(seed, domain,
                                             EVAL_START[label] + i, method,
                                             controllers) for i in range(TEST_N)]
                    scores[method] = {**summary(episodes),
                                      "abstained": sum(e["abstained"] for e in episodes)}
                if restored_fast.record() != f_record or restored_fixed.record() != x_record:
                    raise AssertionError("held-out evaluation modified training evidence")
                evaluations[f"{label}_{checkpoint}"] = {
                    "stage": label, "new_observations": checkpoint,
                    "trained_events": len(fast.events),
                    "fast_selection": restored_fast.selection(),
                    "fixed_selection": restored_fixed.selection(),
                    "checkpoint_sha256": f_record["sha256"],
                    "scores": scores,
                }
            while added < count:
                event = actor_event(seed, domain, start + added)
                fast.observe(event)
                fixed.observe(event)
                added += 1
                stage_cost["observations"] += 1
                stage_cost["harmful"] += int(event["damage"])
                stage_cost["productive"] += int(event["progress"])
                stage_cost["neutral"] += int(not event["progress"] and not event["damage"])
            per_stage_cost[label] = stage_cost
            for key in actor_counts:
                actor_counts[key] += stage_cost[key]
            if fast.events != fixed.events:
                raise AssertionError("learner training budgets differ")
        result["rows"].append({
            "seed": seed, "evaluation": evaluations,
            "actor_by_stage": per_stage_cost, "actor_total": actor_counts,
            "final_fast_sha256": fast.record()["sha256"],
            "final_fixed_sha256": fixed.record()["sha256"],
        })
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", choices=("development", "additional"),
                        default="development")
    args = parser.parse_args()
    print(json.dumps(measure(DEV if args.cohort == "development" else ADDITIONAL),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
