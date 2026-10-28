"""Precommitted adaptive-horizon comparisons with identical public A-B-A schemas.

Training: externally sourced random first-action episodes, no learner action
acquisition. All methods receive identical history at each checkpoint.
Test score is read-only and uses disjoint test indices; repeated across
checkpoints intentionally, so checkpoint metrics are not independent.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.adaptive_horizon_memory import AdaptiveHorizonMemory
from developmental_ai.fast_shock_memory import FastShockMemory
from developmental_ai.same_schema_switch_memory import SameSchemaSwitchMemory
from benchmarks.fast_shock_benchmark import _trained, eval_trial as prior_trial
from benchmarks.same_schema_switch_benchmark import STAGES, training, eval_episode
from benchmarks.relation_transfer_benchmark import relation_model, summarize

SCHEMA = "developmental-ai.adaptive-memory-horizon-benchmark/v1"
DEV = (192003, 192021, 192039)
ADDITIONAL = (193001, 193017, 193041)
TEST_N = 30
TEST_START = {"B": 110000, "return_A": 120000}
CHECKPOINTS = {
    "B": (0, 2, 4, 6, 8, 12, 16, 24, 32, 48, 64),
    "return_A": (0, 2, 4, 6, 8, 12, 16, 24, 48),
}
METHODS = (
    "adaptive_horizon", "fast_shock", "legacy_disjoint_12plus4",
    "recent8", "recent32", "frozen_A", "cumulative_range",
    "untrained_random", "always_abstain", "privileged_oracle",
)


def build_models(history):
    return {
        "adaptive_horizon": _trained(history, AdaptiveHorizonMemory),
        "fast_shock": _trained(history, FastShockMemory),
        "legacy_disjoint_12plus4": _trained(history, SameSchemaSwitchMemory),
        "recent8": relation_model(history[-8:]),
        "recent32": relation_model(history[-32:]),
        "frozen_A": relation_model(history[:192]),
        "cumulative_range": relation_model(history),
    }


def eval_trial(seed, physics, index, method, policies):
    if method not in METHODS:
        raise ValueError("method outside frozen adaptive-horizon comparison")
    if method == "adaptive_horizon":
        return eval_episode(
            seed, physics, index, "adaptive_same_schema",
            {"adaptive_same_schema": policies[method]},
        )
    return prior_trial(seed, physics, index, method, policies)


def measure(seeds=DEV):
    if type(seeds) not in (list, tuple) or tuple(seeds) not in (DEV, ADDITIONAL):
        raise ValueError("not a precommitted adaptive-horizon seed cohort")
    report = {
        "schema": SCHEMA,
        "protocol": "benchmarks/adaptive_horizon_protocol.json",
        "blind": False,
        "learner_training_actions": 0,
        "test_episodes_per_checkpoint_seed": TEST_N,
        "reused_test_indices_across_checkpoints": True,
        "rows": [],
    }
    for seed in seeds:
        archive = []
        stage_scores = {}
        actor_costs = {}
        for stage, physics, first, length in STAGES:
            examples = training(seed, physics, first, length)
            actor_costs[stage] = {
                "observations": len(examples),
                "harmful": sum(int(x["damage"]) for x in examples),
                "productive": sum(int(x["progress"]) for x in examples),
                "neutral": sum(int(not x["progress"] and not x["damage"])
                               for x in examples),
            }
            if stage == "A":
                archive.extend(examples)
                continue
            checkpoints = {}
            for count in CHECKPOINTS[stage]:
                history = archive + examples[:count]
                policies = build_models(history)
                checkpoints_before = {
                    name: model.record() for name, model in policies.items()
                }
                decisions = {
                    "adaptive": policies["adaptive_horizon"].selection()[0],
                    "fast": policies["fast_shock"].selection()[0],
                    "legacy": policies["legacy_disjoint_12plus4"].selection()[0],
                }
                metrics = {
                    name: summarize([
                        eval_trial(seed, physics, TEST_START[stage] + i,
                                   name, policies)
                        for i in range(TEST_N)
                    ])
                    for name in METHODS
                }
                if any(policies[name].record() != state
                       for name, state in checkpoints_before.items()):
                    raise AssertionError("evaluation changed a trained policy")
                checkpoints[str(count)] = {
                    "observations_since_switch": count,
                    "total_training_events": len(history),
                    "decisions": decisions,
                    "memory_sha256": checkpoints_before[
                        "adaptive_horizon"]["sha256"],
                    "scores": metrics,
                }
            stage_scores[stage] = checkpoints
            archive.extend(examples)
        report["rows"].append({
            "seed": seed, "training_actor_costs": actor_costs,
            "stages": stage_scores, "total_events": len(archive)
        })
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cohort", choices=("development", "additional"),
                   default="development")
    selection = p.parse_args()
    cohorts = DEV if selection.cohort == "development" else ADDITIONAL
    print(json.dumps(measure(cohorts), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
