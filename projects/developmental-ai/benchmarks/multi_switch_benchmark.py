"""Frozen noisy-reports and repeated A->B->A->B regime evaluation.

Observed TRAIN progress/damage may flip labels on an authored 10% of
non-neutral events. The learner sees ONLY reported public outcomes; actor
TRUE harm is counted separately. TEST outcomes follow deterministic hidden
physics and never train the learner. The same observation keys persist.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.multi_switch_memory import MultiSwitchContrastMemory
from developmental_ai.adaptive_horizon_memory import AdaptiveHorizonMemory
from developmental_ai.fast_shock_memory import FastShockMemory
from developmental_ai.same_schema_switch_memory import SameSchemaSwitchMemory
from developmental_ai.observable_affordances import digest
from benchmarks.same_schema_switch_benchmark import (
    training, eval_episode
)
from benchmarks.relation_transfer_benchmark import relation_model, summarize

SCHEMA = "developmental-ai.multi-switch-noisy-benchmark/v1"
DEV = (202003, 202021, 202039)
ADDITIONAL = (203001, 203017, 203041)
STAGES = (
    ("A", "original", 1000, 240),
    ("B1", "reversed", 2000, 64),
    ("return_A", "original", 3000, 48),
    ("B2", "reversed", 4000, 64),
)
CHECKPOINTS = {
    "B1": (0, 2, 4, 8, 12, 16, 24, 32, 48, 64),
    "return_A": (0, 2, 4, 8, 12, 24, 48),
    "B2": (0, 2, 4, 8, 12, 16, 24, 32, 64),
}
START = {"B1": 130000, "return_A": 140000, "B2": 150000}
TEST_N = 20
METHODS = (
    "contrastive_multi", "adaptive_horizon", "fast_shock",
    "legacy_disjoint", "recent8", "recent32", "frozen_A",
    "untrained_random", "always_abstain", "privileged_oracle",
)


def public_train(seed, physics, start, n):
    actual = training(seed, physics, start, n)
    reported = []
    flips = 0
    for i, event in enumerate(actual):
        copied = {"features": dict(event["features"]),
                  "progress": event["progress"], "damage": event["damage"]}
        # Stable seed-independent-of-evaluator report-noise draw.
        flip = (int(digest(["noisy-actor-public-report/v1", seed, start + i])
                    [:12], 16) % 10 == 0)
        if flip and (copied["progress"] or copied["damage"]):
            copied["progress"], copied["damage"] = (
                copied["damage"], copied["progress"])
            flips += 1
        reported.append(copied)
    counts = {
        "observations": n,
        "actual_harmful": sum(int(e["damage"]) for e in actual),
        "reported_harmful": sum(int(e["damage"]) for e in reported),
        "actual_productive": sum(int(e["progress"]) for e in actual),
        "label_flips": flips,
        "actual_neutral": sum(int(not e["progress"] and not e["damage"])
                              for e in actual),
    }
    return reported, counts


def model(cls, events):
    obj = cls()
    for e in events:
        obj.observe(e)
    return cls.restore(obj.record())


def policies(history):
    return {
        "contrastive_multi": model(MultiSwitchContrastMemory, history),
        "adaptive_horizon": model(AdaptiveHorizonMemory, history),
        "fast_shock": model(FastShockMemory, history),
        "legacy_disjoint": model(SameSchemaSwitchMemory, history),
        "recent8": relation_model(history[-8:]),
        "recent32": relation_model(history[-32:]),
        "frozen_A": relation_model(history[:192]),
    }


def play(seed, physics, index, name, trained):
    if name not in METHODS:
        raise ValueError("not a precommitted comparison policy")
    if name in trained:
        return eval_episode(
            seed, physics, index, "adaptive_same_schema",
            {"adaptive_same_schema": trained[name]}
        )
    return eval_episode(seed, physics, index, name, {})


def measure(seeds=DEV):
    if type(seeds) not in (list, tuple) or tuple(seeds) not in (DEV, ADDITIONAL):
        raise ValueError("wrong frozen multi-switch cohort")
    output = {
        "schema": SCHEMA,
        "protocol": "benchmarks/multi_switch_protocol.json",
        "blind": False,
        "learner_training_actions": 0,
        "repeated_test_indices_across_checkpoints": True,
        "episodes_per_seed_checkpoint": TEST_N,
        "rows": [],
    }
    for seed in seeds:
        history = []
        actor_costs = {}
        phase_scores = {}
        for stage, physics, first, length in STAGES:
            observed, cost = public_train(seed, physics, first, length)
            actor_costs[stage] = cost
            if stage == "A":
                history.extend(observed)
                continue
            checkpoints = {}
            for n in CHECKPOINTS[stage]:
                events = history + observed[:n]
                fitted = policies(events)
                saved = {name: p.record() for name, p in fitted.items()}
                selection = fitted["contrastive_multi"].selection()[0]
                score = {
                    method: summarize([
                        play(seed, physics, START[stage] + j, method, fitted)
                        for j in range(TEST_N)
                    ])
                    for method in METHODS
                }
                if any(fitted[name].record() != state
                       for name, state in saved.items()):
                    raise AssertionError("TEST outcomes contaminated training")
                checkpoints[str(n)] = {
                    "observed_in_stage": n,
                    "total_public_events": len(events),
                    "contrasting_decision": selection,
                    "checkpoint_sha256": saved["contrastive_multi"]["sha256"],
                    "scores": score,
                }
            phase_scores[stage] = checkpoints
            history.extend(observed)
        output["rows"].append({
            "seed": seed, "actor_actual_and_reported": actor_costs,
            "stages": phase_scores, "final_events": len(history),
        })
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", choices=("development", "additional"),
                        default="development")
    a = parser.parse_args()
    print(json.dumps(measure(DEV if a.cohort == "development" else ADDITIONAL),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
