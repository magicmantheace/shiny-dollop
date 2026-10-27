"""Frozen A->B->A passive-observation retrieval comparison.

Only the TEST oracle can see the simulator's true action rules. The learner
receives public numeric action outcomes from a separate random simulator actor.
All collections may cause simulator damage, which is counted distinctly.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.observable_affordances import (
    ObservableWorld, NumericOutcomeMemory, RegimeRetrievalMemory, digest, outcome,
)
from benchmarks.observable_affordance_benchmark import summary

SCHEMA = "developmental-ai.regime-retrieval-benchmark/v1"
DEV = (112003, 112021, 112039)
ADDITIONAL = (113001, 113017, 113041)
STAGES = (
    ("A", "route", 40000, 160, 50000),
    ("B", "route-reversed", 41000, 160, 51000),
    ("return_A", "route", 42000, 12, 52000),
)
METHODS = (
    "retrieved_bank", "cumulative_knn", "recent_32_knn", "frozen_A_knn",
    "untrained_random", "always_abstain", "privileged_oracle",
)
TEST_N = 60
WINDOW = 32


def actor_event(seed, domain, index):
    world = ObservableWorld(seed, "train", index, domain)
    before = world.frame()
    # Separate deterministic random observer; not a learner action.
    rng = random.Random(int(digest(["regime-external-actor", world.episode])[:16], 16))
    action = rng.choice(before["actions"])["id"]
    after = world.step(action, before["tick"])
    return outcome(before, action, after)


def fit_numeric(events):
    memory = NumericOutcomeMemory()
    for event in events:
        memory.add(event)
    return memory


def test_episode(seed, domain, index, method, bank, history):
    if method not in METHODS:
        raise ValueError("unknown evaluation baseline")
    world = ObservableWorld(seed, "test", index, domain)
    memory = (fit_numeric(history) if method == "cumulative_knn"
              else fit_numeric(history[-WINDOW:]) if method == "recent_32_knn"
              else fit_numeric(history[:STAGES[0][3]]) if method == "frozen_A_knn"
              else None)
    rng = random.Random(int(world.episode[16:32], 16) ^ 0x831a)
    hurt = 0
    abstained = False
    for _ in range(world.budget):
        before = world.frame()
        if before["done"]:
            break
        if method == "retrieved_bank":
            action = bank.choose(before)
        elif method in ("cumulative_knn", "recent_32_knn", "frozen_A_knn"):
            action = memory.choose(before)
        elif method == "always_abstain":
            action = None
        elif method == "untrained_random":
            action = rng.choice(before["actions"])["id"]
        else:
            # Privileged ceiling: explicitly forbidden to the learner.
            actions = before["actions"]
            good = []
            for row in actions:
                x, y = row["features"]
                if domain == "route-reversed":
                    x, y = y, x
                if y >= x + 2:
                    good.append(row["id"])
            action = good[0] if good else None
        if action is None:
            abstained = True
            break
        after = world.step(action, before["tick"])
        hurt += int(outcome(before, action, after)["damage"])
    return {"success": int(world.success()), "hurt": hurt,
            "stalled": int(not world.success()),
            "attempts": world.tick, "abstained": int(abstained)}


def measure(seeds=DEV):
    if type(seeds) not in (tuple, list) or tuple(seeds) not in (DEV, ADDITIONAL):
        raise ValueError("evaluation cohort not frozen in protocol")
    result = {"schema": SCHEMA, "protocol": "benchmarks/regime_retrieval_protocol.json",
              "blind": False, "learner_training_actions": 0,
              "numeric_features_engineered": True, "rows": []}
    for seed in seeds:
        bank = RegimeRetrievalMemory()
        stage_results = {}
        actor_totals = {"observations": 0, "harmful": 0,
                        "productive": 0, "neutral": 0}
        for label, domain, start, count, test_start in STAGES:
            actor_cost = {"observations": count, "harmful": 0,
                          "productive": 0, "neutral": 0}
            for index in range(start, start + count):
                event = actor_event(seed, domain, index)
                bank.observe(event)
                actor_cost["harmful"] += int(event["damage"])
                actor_cost["productive"] += int(event["progress"])
                actor_cost["neutral"] += int(not event["progress"] and not event["damage"])
            for key, n in actor_cost.items():
                actor_totals[key] += n
            checkpoint = bank.record()
            # Even the regime-selecting caches must be reconstructible from
            # public outcomes after an ordinary shutdown.
            bank = RegimeRetrievalMemory.restore(checkpoint)
            selected = bank.selection()
            history = list(bank.events)
            stage_scores = {}
            for method in METHODS:
                runs = [test_episode(seed, domain, test_start + i,
                                     method, bank, history) for i in range(TEST_N)]
                stage_scores[method] = {**summary(runs),
                                        "abstained": sum(r["abstained"] for r in runs)}
            if bank.record() != checkpoint:
                raise AssertionError("held-out test changed learned history")
            stage_results[label] = {"scores": stage_scores, "retrieval": selected,
                                    "trained_events": len(history),
                                    "actor_cost": actor_cost,
                                    "checkpoint_sha256": checkpoint["sha256"]}
        result["rows"].append({"seed": seed, "stages": stage_results,
                               "actor_total": actor_totals,
                               "final_sha256": bank.record()["sha256"]})
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
